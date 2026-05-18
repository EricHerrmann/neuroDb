"""Dataset research packet builders and coverage helpers."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from neurodb.schema import DatasetIndex, DatasetResearchPacket


USEFULNESS_STATES = {
    "sparse",
    "partial",
    "research_context_ready",
    "analysis_ready",
    "not_useful_for_focus",
}


def make_dataset_research_packet(
    *,
    source: str,
    source_id: str,
    raw: dict[str, Any],
    index_id: int,
    run_id: int,
    connector_version: str,
) -> DatasetResearchPacket:
    """Build a source-aware research packet from raw connector metadata."""
    data = _extract_source_fields(source, source_id, raw)
    missing = _missing_context(data)
    state = _usefulness_state(data, missing)
    supported, unsupported = _workflow_labels(state, data, missing)
    harvested_at = datetime.now(timezone.utc).isoformat()
    provenance = {
        "source": source,
        "connector_version": connector_version,
        "harvested_at": harvested_at,
        "raw_fields_used": data.pop("_raw_fields_used", []),
    }
    confidence = {
        "source_identity": "direct",
        "source_summary": "direct" if data.get("source_summary") else "missing",
        "publication": "direct" if data.get("doi") or data.get("paper_url") else "missing",
        "topics": "direct" if _json_has_items(data.get("topics_json")) else "missing",
        "assets": "direct" if _json_has_items(data.get("assets_json")) else "missing",
    }
    return DatasetResearchPacket(
        index_id=index_id,
        source=source,
        source_id=source_id,
        title=data.get("title"),
        landing_url=data.get("landing_url"),
        api_url=data.get("api_url"),
        source_summary=data.get("source_summary"),
        doi=data.get("doi"),
        paper_url=data.get("paper_url"),
        publication_title=data.get("publication_title"),
        abstract=data.get("abstract"),
        authors_json=data.get("authors_json"),
        topics_json=data.get("topics_json"),
        brain_regions_json=data.get("brain_regions_json"),
        diseases_json=data.get("diseases_json"),
        modalities_json=data.get("modalities_json"),
        participant_summary=data.get("participant_summary"),
        methods_json=data.get("methods_json"),
        assets_json=data.get("assets_json"),
        usefulness_state=state,
        supported_workflows_json=_json(supported),
        unsupported_workflows_json=_json(unsupported),
        missing_context_json=_json(missing),
        provenance_json=_json(provenance),
        confidence_json=_json(confidence),
        harvested_at=harvested_at,
        run_id=run_id,
    )


def upsert_dataset_research_packet(session: Session, packet: DatasetResearchPacket) -> None:
    """Insert or update the packet for a dataset index row."""
    existing = session.execute(
        select(DatasetResearchPacket).where(DatasetResearchPacket.index_id == packet.index_id)
    ).scalar_one_or_none()
    if existing is None:
        session.add(packet)
        return
    for attr, val in vars(packet).items():
        if not attr.startswith("_") and attr != "id":
            setattr(existing, attr, val)


def get_dataset_packet_summary(
    engine: Engine,
    *,
    source: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return compact packet rows for CLI, UI, and agent retrieval."""
    with Session(engine) as session:
        query = session.query(DatasetResearchPacket)
        if source:
            query = query.filter(DatasetResearchPacket.source == source)
        rows = (
            query.order_by(DatasetResearchPacket.source, DatasetResearchPacket.source_id)
            .limit(limit)
            .all()
        )
        return [_packet_to_summary(row) for row in rows]


def get_dataset_packet_coverage(engine: Engine) -> list[dict[str, Any]]:
    """Return source-level coverage metrics for dataset research packets."""
    with Session(engine) as session:
        rows = session.query(DatasetResearchPacket).all()

    grouped: dict[str, list[DatasetResearchPacket]] = defaultdict(list)
    for row in rows:
        grouped[row.source].append(row)

    report = []
    for source, packets in sorted(grouped.items()):
        state_counts = Counter(packet.usefulness_state for packet in packets)
        total_missing = sum(len(_loads_list(packet.missing_context_json)) for packet in packets)
        report.append(
            {
                "source": source,
                "total_packets": len(packets),
                "states": dict(sorted(state_counts.items())),
                "doi_or_paper_url": sum(
                    1 for packet in packets if packet.doi or packet.paper_url
                ),
                "source_summary": sum(1 for packet in packets if packet.source_summary),
                "topics": sum(1 for packet in packets if _json_has_items(packet.topics_json)),
                "asset_manifest": sum(1 for packet in packets if _json_has_items(packet.assets_json)),
                "avg_missing_context_count": (
                    round(total_missing / len(packets), 2) if packets else 0.0
                ),
            }
        )
    return report


def backfill_dataset_research_packets(engine: Engine) -> int:
    """Create sparse packets for existing indexed datasets without source raw metadata."""
    count = 0
    with Session(engine) as session:
        rows = session.execute(select(DatasetIndex)).scalars().all()
        for row in rows:
            existing = session.execute(
                select(DatasetResearchPacket).where(
                    DatasetResearchPacket.index_id == row.id
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            packet = make_dataset_research_packet(
                source=row.source,
                source_id=row.source_id,
                raw={"id": row.source_id},
                index_id=row.id,
                run_id=row.run_id,
                connector_version="backfill",
            )
            session.add(packet)
            count += 1
        session.commit()
    return count


def _extract_source_fields(source: str, source_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    if source == "openneuro":
        return _extract_openneuro(source_id, raw)
    if source == "dandi":
        return _extract_dandi(source_id, raw)
    if source == "neurovault":
        return _extract_neurovault(source_id, raw)
    if source == "allen_brain":
        return _extract_allen(source_id, raw)
    return {
        "title": raw.get("title") or raw.get("name") or source_id,
        "api_url": None,
        "landing_url": None,
        "source_summary": raw.get("description") or raw.get("summary"),
        "_raw_fields_used": ["description", "summary"],
    }


def _extract_openneuro(source_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    meta = raw.get("metadata") or {}
    draft = raw.get("draft") or {}
    draft_desc = draft.get("description") or {}
    modalities = _clean_list(meta.get("modalities") or [])
    ages = meta.get("ages") or []
    methods = {"bids_version": draft_desc.get("BIDSVersion")}
    return {
        "title": raw.get("name") or source_id,
        "landing_url": f"https://openneuro.org/datasets/{source_id}",
        "api_url": "https://openneuro.org/crn/graphql",
        "source_summary": draft.get("readme"),
        "doi": meta.get("associatedPaperDOI"),
        "modalities_json": _json_or_none(modalities),
        "participant_summary": (
            f"{len(ages)} participant age record(s)" if ages else None
        ),
        "methods_json": _json_or_none(_strip_empty_dict(methods)),
        "_raw_fields_used": [
            "name",
            "metadata.associatedPaperDOI",
            "metadata.modalities",
            "metadata.ages",
            "draft.readme",
            "draft.description.BIDSVersion",
        ],
    }


def _extract_dandi(source_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    version = raw.get("most_recent_published_version") or raw.get("draft_version") or {}
    asset_summary = version.get("asset_summary") or {}
    species = _names(asset_summary.get("species") or [])
    data_standards = _names(asset_summary.get("dataStandard") or [])
    variable_measured = _names(asset_summary.get("variableMeasured") or [])
    approach = _names(asset_summary.get("approach") or [])
    measurement = _names(asset_summary.get("measurementTechnique") or [])
    topics = _clean_list(variable_measured + approach + measurement)
    assets = {
        "number_of_bytes": asset_summary.get("numberOfBytes"),
        "number_of_files": asset_summary.get("numberOfFiles"),
    }
    methods = {
        "data_standards": data_standards,
        "approach": approach,
        "measurement_technique": measurement,
        "species": species,
    }
    return {
        "title": version.get("name") or raw.get("name") or source_id,
        "landing_url": f"https://dandiarchive.org/dandiset/{source_id}",
        "api_url": f"https://api.dandiarchive.org/api/dandisets/{source_id}/",
        "source_summary": version.get("description"),
        "doi": version.get("doi") or raw.get("doi"),
        "topics_json": _json_or_none(topics),
        "modalities_json": _json_or_none(data_standards),
        "participant_summary": _subject_summary(asset_summary.get("numberOfSubjects")),
        "methods_json": _json_or_none(_strip_empty_dict(methods)),
        "assets_json": _json_or_none(_strip_empty_dict(assets)),
        "_raw_fields_used": [
            "version.name",
            "version.description",
            "version.doi",
            "version.asset_summary",
        ],
    }


def _extract_neurovault(source_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    topics = _clean_list([
        raw.get("cognitive_paradigm_cog_atlas"),
        raw.get("contrast_definition_cog_atlas"),
    ])
    methods = {
        "repetition_time": raw.get("repetition_time"),
        "resolution": raw.get("resolution"),
    }
    assets = {
        "number_of_images": raw.get("number_of_images"),
        "collection_images_url": raw.get("images"),
    }
    return {
        "title": raw.get("name") or source_id,
        "landing_url": raw.get("url") or f"https://neurovault.org/collections/{source_id}/",
        "api_url": f"https://neurovault.org/api/collections/{source_id}/",
        "source_summary": raw.get("description"),
        "doi": raw.get("doi") or None,
        "paper_url": raw.get("paper_url") or raw.get("url_paper"),
        "topics_json": _json_or_none(topics),
        "modalities_json": _json(["fMRI"]),
        "participant_summary": _subject_summary(raw.get("number_of_subjects")),
        "methods_json": _json_or_none(_strip_empty_dict(methods)),
        "assets_json": _json_or_none(_strip_empty_dict(assets)),
        "_raw_fields_used": [
            "name",
            "description",
            "doi",
            "paper_url",
            "cognitive_paradigm_cog_atlas",
            "number_of_images",
            "number_of_subjects",
        ],
    }


def _extract_allen(source_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    methods = {
        "modality": "ISH",
        "plane_of_section_id": raw.get("plane_of_section_id"),
        "specimen_id": raw.get("specimen_id"),
    }
    assets = {
        "api_section_dataset_url": (
            "https://api.brain-map.org/api/v2/data/query.json"
            f"?criteria=model::SectionDataSet[id$eq{source_id}]"
        )
    }
    topics = _clean_list([raw.get("name"), raw.get("section_data_set_type")])
    return {
        "title": raw.get("name") or source_id,
        "landing_url": f"https://mouse.brain-map.org/experiment/show/{source_id}",
        "api_url": assets["api_section_dataset_url"],
        "source_summary": raw.get("description"),
        "topics_json": _json_or_none(topics),
        "modalities_json": _json(["ISH"]),
        "methods_json": _json_or_none(_strip_empty_dict(methods)),
        "assets_json": _json_or_none(assets),
        "_raw_fields_used": [
            "name",
            "description",
            "plane_of_section_id",
            "specimen_id",
            "section_data_set_type",
        ],
    }


def _missing_context(data: dict[str, Any]) -> list[str]:
    checks = {
        "publication_link": bool(data.get("doi") or data.get("paper_url")),
        "source_summary": bool(data.get("source_summary")),
        "topics_or_concepts": _json_has_items(data.get("topics_json")),
        "participant_context": bool(data.get("participant_summary")),
        "methods": _json_has_items(data.get("methods_json")),
        "asset_manifest": _json_has_items(data.get("assets_json")),
    }
    return [name for name, present in checks.items() if not present]


def _usefulness_state(data: dict[str, Any], missing: list[str]) -> str:
    has_publication = "publication_link" not in missing
    has_summary = "source_summary" not in missing
    has_methods = "methods" not in missing
    has_assets = "asset_manifest" not in missing
    has_topics = "topics_or_concepts" not in missing
    has_participants = "participant_context" not in missing
    if has_assets and has_summary and has_methods and has_participants:
        return "analysis_ready"
    if has_publication and has_summary and (has_topics or has_methods):
        return "research_context_ready"
    useful_fields = [
        has_publication,
        has_summary,
        has_methods,
        has_assets,
        has_topics,
        has_participants,
        bool(data.get("title")),
    ]
    return "partial" if sum(1 for value in useful_fields if value) >= 3 else "sparse"


def _workflow_labels(
    state: str,
    data: dict[str, Any],
    missing: list[str],
) -> tuple[list[str], list[str]]:
    supported = []
    unsupported = []
    if state in {"research_context_ready", "analysis_ready"}:
        supported.extend(["learning_context", "research_synthesis"])
    elif state == "partial":
        supported.append("orientation")
    else:
        unsupported.extend(["research_synthesis", "direct_analysis"])
    if "asset_manifest" in missing:
        unsupported.append("direct_analysis")
    elif state == "analysis_ready":
        supported.append("direct_analysis")
    if data.get("source_summary"):
        supported.append("teaching_example")
    return sorted(set(supported)), sorted(set(unsupported))


def _packet_to_summary(packet: DatasetResearchPacket) -> dict[str, Any]:
    return {
        "source": packet.source,
        "source_id": packet.source_id,
        "title": packet.title,
        "usefulness_state": packet.usefulness_state,
        "doi": packet.doi,
        "paper_url": packet.paper_url,
        "source_summary": packet.source_summary,
        "missing_context": _loads_list(packet.missing_context_json),
        "supported_workflows": _loads_list(packet.supported_workflows_json),
        "unsupported_workflows": _loads_list(packet.unsupported_workflows_json),
        "harvested_at": packet.harvested_at,
    }


def _names(items: list[Any]) -> list[str]:
    values = []
    for item in items:
        if isinstance(item, dict):
            values.append(item.get("name") or item.get("identifier"))
        else:
            values.append(item)
    return _clean_list(values)


def _subject_summary(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return f"{value} subject(s)"


def _clean_list(values: list[Any]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _strip_empty_dict(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "", [], {})
    }


def _json_or_none(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    return _json(value)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _json_has_items(value: str | None) -> bool:
    if not value:
        return False
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return False
    if isinstance(decoded, dict):
        return any(v not in (None, "", [], {}) for v in decoded.values())
    if isinstance(decoded, list):
        return len(decoded) > 0
    return bool(decoded)


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    decoded = json.loads(value)
    return decoded if isinstance(decoded, list) else []

