"""DB epoch - type-agnostic grouping engine over groupings/grouping_links.

Store layer for the unified taxonomy. No consumer is switched to this engine
yet; later phases cut workflows over and map GroupingHierarchyError to HTTP 422.
"""
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from neurodb.db.grouping_types import GroupingHierarchyError, require_known_type
from neurodb.schema import Grouping, GroupingLink


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _grouping_dict(grouping: Grouping) -> dict:
    return {
        "id": grouping.id,
        "type": grouping.type,
        "name": grouping.name,
        "parent_id": grouping.parent_id,
        "status": grouping.status,
        "description": grouping.description,
    }


def get_or_create_grouping(
    session: Session,
    gtype: str,
    name: str,
    *,
    description: str | None = None,
    status: str = "active",
) -> Grouping:
    """Fetch or create a grouping, deduped by (type, name)."""
    require_known_type(gtype)
    name = name.strip()
    existing = session.execute(
        select(Grouping).where(Grouping.type == gtype, Grouping.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = _now()
    grouping = Grouping(
        type=gtype,
        name=name,
        parent_id=None,
        status=status,
        description=description,
        created_at=now,
        updated_at=now,
    )
    session.add(grouping)
    session.flush()
    return grouping


def get_grouping(session: Session, grouping_id: int) -> Grouping | None:
    return session.get(Grouping, grouping_id)


def list_groupings(
    session: Session, *, gtype: str | None = None, status: str | None = None
) -> list[dict]:
    stmt = select(Grouping)
    if gtype is not None:
        require_known_type(gtype)
        stmt = stmt.where(Grouping.type == gtype)
    if status is not None:
        stmt = stmt.where(Grouping.status == status)
    rows = session.execute(stmt.order_by(Grouping.type, Grouping.name)).scalars().all()
    return [_grouping_dict(row) for row in rows]


def search_groupings(session: Session, gtype: str, query: str, limit: int = 10) -> list[dict]:
    require_known_type(gtype)
    q = f"%{query}%"
    rows = session.execute(
        select(Grouping)
        .where(Grouping.type == gtype)
        .where(or_(Grouping.name.ilike(q), Grouping.description.ilike(q)))
        .order_by(Grouping.name)
        .limit(limit)
    ).scalars().all()
    return [_grouping_dict(row) for row in rows]


def link_grouping(
    session: Session,
    grouping_id: int,
    anchor_type: str,
    anchor_id: int,
    *,
    status: str = "confirmed",
) -> None:
    """Create a grouping-anchor link idempotently."""
    exists = session.execute(
        select(GroupingLink).where(
            GroupingLink.grouping_id == grouping_id,
            GroupingLink.anchor_type == anchor_type,
            GroupingLink.anchor_id == anchor_id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        return
    session.add(
        GroupingLink(
            grouping_id=grouping_id,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            status=status,
            created_at=_now(),
        )
    )
    session.flush()


def update_link_status(
    session: Session, grouping_id: int, anchor_type: str, anchor_id: int, status: str
) -> bool:
    """Update status on an existing link. Returns True if a link was found."""
    row = session.execute(
        select(GroupingLink).where(
            GroupingLink.grouping_id == grouping_id,
            GroupingLink.anchor_type == anchor_type,
            GroupingLink.anchor_id == anchor_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = status
    session.flush()
    return True


def unlink_grouping(
    session: Session, grouping_id: int, anchor_type: str, anchor_id: int
) -> bool:
    """Delete a link. Returns True if a link was found."""
    row = session.execute(
        select(GroupingLink).where(
            GroupingLink.grouping_id == grouping_id,
            GroupingLink.anchor_type == anchor_type,
            GroupingLink.anchor_id == anchor_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def get_groupings_for_anchor(
    session: Session, anchor_type: str, anchor_id: int, *, status: str | None = None
) -> list[dict]:
    """Return groupings linked to an anchor, each carrying its link status."""
    stmt = (
        select(Grouping, GroupingLink.status)
        .join(GroupingLink, GroupingLink.grouping_id == Grouping.id)
        .where(GroupingLink.anchor_type == anchor_type, GroupingLink.anchor_id == anchor_id)
    )
    if status is not None:
        stmt = stmt.where(GroupingLink.status == status)
    rows = session.execute(stmt.order_by(Grouping.type, Grouping.name)).all()
    return [
        {
            "id": grouping.id,
            "type": grouping.type,
            "name": grouping.name,
            "parent_id": grouping.parent_id,
            "status": grouping.status,
            "grouping_status": grouping.status,
            "description": grouping.description,
            "link_status": link_status,
        }
        for grouping, link_status in rows
    ]


def get_children(session: Session, parent_id: int) -> list[Grouping]:
    return list(
        session.execute(
            select(Grouping).where(Grouping.parent_id == parent_id).order_by(Grouping.name)
        )
        .scalars()
        .all()
    )


def set_parent(session: Session, grouping_id: int, parent_id: int | None) -> Grouping:
    """Set or clear a grouping's parent, enforcing the single-level invariant."""
    child = session.get(Grouping, grouping_id)
    if child is None:
        raise GroupingHierarchyError(f"Grouping {grouping_id} not found")

    if parent_id is None:
        child.parent_id = None
        child.updated_at = _now()
        session.flush()
        return child

    if parent_id == grouping_id:
        raise GroupingHierarchyError("A grouping cannot be its own parent")

    parent = session.get(Grouping, parent_id)
    if parent is None:
        raise GroupingHierarchyError(f"Parent grouping {parent_id} not found")
    if parent.type != child.type:
        raise GroupingHierarchyError(
            f"Parent type {parent.type!r} != child type {child.type!r}"
        )
    if parent.parent_id is not None:
        raise GroupingHierarchyError("Parent must be top-level")
    if get_children(session, grouping_id):
        raise GroupingHierarchyError("Cannot parent a grouping that already has children")

    child.parent_id = parent_id
    child.updated_at = _now()
    session.flush()
    return child


def resolve_filter_ids(session: Session, grouping_id: int) -> list[int]:
    """Return grouping_id plus direct children, the id set a parent filter matches."""
    child_ids = [child.id for child in get_children(session, grouping_id)]
    return [grouping_id, *child_ids]


def rollup_parents(session: Session, grouping_ids: list[int]) -> list[int]:
    """Given matched grouping ids, add each one's parent, deduped."""
    result = list(grouping_ids)
    seen = set(grouping_ids)
    for grouping_id in grouping_ids:
        grouping = session.get(Grouping, grouping_id)
        if grouping is not None and grouping.parent_id is not None:
            if grouping.parent_id not in seen:
                result.append(grouping.parent_id)
                seen.add(grouping.parent_id)
    return result
