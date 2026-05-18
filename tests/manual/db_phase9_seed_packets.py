#!/usr/bin/env python
"""Manual helper: seed dataset research packets from deterministic fixtures."""
import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv

load_dotenv()

from neurodb.connectors.allen_brain import AllenBrainConnector  # noqa: E402
from neurodb.connectors.dandi import DandiConnector  # noqa: E402
from neurodb.connectors.neurovault import NeuroVaultConnector  # noqa: E402
from neurodb.connectors.openneuro import OpenNeuroConnector  # noqa: E402
from neurodb.db import create_views, get_engine, init_db  # noqa: E402
from neurodb.provenance import run_ingest  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"

SOURCES = {
    "openneuro": {
        "connector": OpenNeuroConnector,
        "patch_target": "neurodb.connectors.openneuro.httpx.post",
        "fixture": FIXTURES / "openneuro_sample.json",
    },
    "dandi": {
        "connector": DandiConnector,
        "patch_target": "neurodb.connectors.dandi.httpx.get",
        "fixture": FIXTURES / "dandi_api_sample.json",
    },
    "neurovault": {
        "connector": NeuroVaultConnector,
        "patch_target": "neurodb.connectors.neurovault.httpx.get",
        "fixture": FIXTURES / "neurovault_sample.json",
    },
    "allen_brain": {
        "connector": AllenBrainConnector,
        "patch_target": "neurodb.connectors.allen_brain.httpx.get",
        "fixture": FIXTURES / "allen_sample.json",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed a local DB with fixture-backed dataset research packets"
    )
    parser.add_argument("--db", default="neurodb.duckdb")
    parser.add_argument(
        "--source",
        choices=["all", *SOURCES.keys()],
        default="openneuro",
        help="Fixture source to seed",
    )
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    create_views(engine)

    source_names = list(SOURCES) if args.source == "all" else [args.source]
    seeded = 0
    for source_name in source_names:
        config = SOURCES[source_name]
        with patch(config["patch_target"], side_effect=_mock_response(config["fixture"])):
            run = run_ingest(
                engine,
                connector=config["connector"](),
                limit=args.limit,
            )
        print(f"Seeded {source_name}: run_id={run.id}")
        seeded += 1

    print(f"PASS: seeded {seeded} fixture-backed source(s) into {args.db}.")
    return 0


def _mock_response(path: Path):
    data = json.loads(path.read_text())

    def _response(*_args, **_kwargs):
        mock = MagicMock()
        mock.json.return_value = data
        mock.raise_for_status.return_value = None
        return mock

    return _response


if __name__ == "__main__":
    raise SystemExit(main())
