#!/usr/bin/env python
"""CLI: study tag operations for NeuroDb.

Usage:
    uv run scripts/study.py tag --source dandi --id 000003 --concept "primary visual cortex"
    uv run scripts/study.py tag --source dandi --id 000003 --concept "V1" --section "Augustine Ch13" --note "electrode recordings"
    uv run scripts/study.py list
    uv run scripts/study.py list --concept "visual" --source dandi
    uv run scripts/study.py search retinotopic
"""
import argparse

from neurodb.db import get_engine, get_session, init_db
from neurodb.embed_hooks import embed_note, remove_note
from neurodb.embedder import Embedder
from neurodb.study import delete_tag, list_tags, search_tags, tag_dataset
from neurodb.vector_store import VectorStore


def _vector_store(db_path: str) -> VectorStore:
    chroma_path = db_path.replace(".duckdb", "_chroma")
    return VectorStore(path=chroma_path, embedder=Embedder())

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def cmd_tag(args):
    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    with get_session(engine) as session:
        note = tag_dataset(
            session,
            source=args.source,
            source_id=args.id,
            concept_tag=args.concept,
            section_ref=args.section or None,
            note_text=args.note or None,
        )
    if note is None:
        print(f"Dataset not found: {args.source}:{args.id} — run ingest first")
        return
    print(f"Tagged {args.source}:{args.id} → '{args.concept}'")
    embed_note(_vector_store(args.db), note.id, args.source, args.id,
               args.concept, args.section or None, args.note or None)


def cmd_list(args):
    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    with get_session(engine) as session:
        tags = list_tags(session, concept=args.concept or None, source=args.source or None)
    if not tags:
        print("No tags found.")
        return
    for t in tags:
        print(f"[{t['source']}:{t['source_id']}] {t['concept_tag']}")
        if t["section_ref"]:
            print(f"  Section: {t['section_ref']}")
        if t["note_text"]:
            print(f"  Note:    {t['note_text']}")
        print(f"  Tagged:  {t['tagged_at']}")
        print()


def cmd_delete(args):
    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    with get_session(engine) as session:
        deleted = delete_tag(session, args.tag_id)
    if not deleted:
        print(f"Tag id={args.tag_id} not found.")
        return
    print(f"Deleted tag id={args.tag_id}.")
    remove_note(_vector_store(args.db), args.tag_id)


def cmd_search(args):
    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    with get_session(engine) as session:
        tags = search_tags(session, args.keyword)
    if not tags:
        print(f"No tags matching '{args.keyword}'")
        return
    for t in tags:
        print(f"[{t['source']}:{t['source_id']}] {t['concept_tag']}")
        if t["note_text"]:
            print(f"  Note: {t['note_text']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Study tag operations for NeuroDb")
    parser.add_argument("--db", default="neurodb.duckdb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    tag_p = sub.add_parser("tag", help="Tag a dataset with a concept")
    tag_p.add_argument("--source", required=True, choices=SOURCES)
    tag_p.add_argument("--id", required=True, dest="id", metavar="SOURCE_ID")
    tag_p.add_argument("--concept", required=True)
    tag_p.add_argument("--section", default="", metavar="SECTION_REF")
    tag_p.add_argument("--note", default="")

    list_p = sub.add_parser("list", help="List study tags")
    list_p.add_argument("--concept", default="", help="Filter by concept substring")
    list_p.add_argument("--source", default="", choices=[""] + SOURCES)

    search_p = sub.add_parser("search", help="Search tags by keyword")
    search_p.add_argument("keyword")

    del_p = sub.add_parser("delete", help="Delete a study tag by id")
    del_p.add_argument("tag_id", type=int, metavar="TAG_ID")

    args = parser.parse_args()
    {"tag": cmd_tag, "list": cmd_list, "search": cmd_search, "delete": cmd_delete}[args.cmd](args)


if __name__ == "__main__":
    main()
