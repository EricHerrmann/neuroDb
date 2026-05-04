import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import h5py
from pynwb import NWBHDF5IO

from sqlalchemy import Engine

from neurodb.db import get_session


def _download_first_nwb(source_id: str) -> str | None:
    """Download the first NWB asset for a dandiset to a temp file. Returns path or None."""
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(source_id)
        for asset in dandiset.get_assets():
            if asset.path.endswith(".nwb"):
                tmp = tempfile.NamedTemporaryFile(suffix=".nwb", delete=False)
                tmp.close()
                asset.download(tmp.name)
                return tmp.name
    return None


def _parse_nwb(path: str) -> dict:
    """Extract enrichment fields from an NWB file. Raises on parse failure."""
    nwb_version = None
    with h5py.File(path, "r") as hf:
        raw_ver = hf.attrs.get("nwb_version")
        if raw_ver is not None:
            nwb_version = raw_ver.decode() if isinstance(raw_ver, bytes) else str(raw_ver)

    electrode_count = None
    sampling_rate = None
    brain_regions = None
    cognitive_paradigm = None

    with NWBHDF5IO(path, "r", load_namespaces=True) as io:
        nwb = io.read()

        if nwb.electrodes is not None:
            electrode_count = len(nwb.electrodes)
            df = nwb.electrodes.to_dataframe()
            if "sampling_rate" in df.columns:
                rates = df["sampling_rate"].dropna()
                if not rates.empty:
                    sampling_rate = float(rates.iloc[0])

        if nwb.electrode_groups:
            locations = [eg.location for eg in nwb.electrode_groups.values() if eg.location]
            if locations:
                brain_regions = json.dumps(list(dict.fromkeys(locations)))

        if nwb.session_description:
            cognitive_paradigm = nwb.session_description[:256]

    return {
        "electrode_count": electrode_count,
        "sampling_rate": sampling_rate,
        "brain_regions": brain_regions,
        "cognitive_paradigm": cognitive_paradigm,
        "nwb_version": nwb_version,
    }


def run_enrichment(engine: Engine, limit: int | None = None) -> int:
    """Enrich unenriched DANDI records with NWB metadata. Returns count enriched."""
    from neurodb.connectors.dandi import DandiDataset

    with get_session(engine) as session:
        query = session.query(DandiDataset).filter(DandiDataset.enriched_at.is_(None))
        if limit is not None:
            query = query.limit(limit)
        records = list(query)

    enriched_count = 0
    for record in records:
        tmp_path = None
        try:
            tmp_path = _download_first_nwb(record.source_id)
            if tmp_path is None:
                print(f"  {record.source_id}: no NWB asset found, skipping")
                continue
            fields = _parse_nwb(tmp_path)
            with get_session(engine) as session:
                rec = session.get(DandiDataset, record.id)
                for k, v in fields.items():
                    setattr(rec, k, v)
                rec.enriched_at = datetime.now(timezone.utc).isoformat()
            enriched_count += 1
            print(f"  {record.source_id}: enriched ({fields['electrode_count']} electrodes)")
        except Exception as e:
            print(f"  WARNING: {record.source_id}: enrichment failed: {e}")
            try:
                with get_session(engine) as session:
                    rec = session.get(DandiDataset, record.id)
                    if rec is not None:
                        rec.enriched_at = f"ERROR:{str(e)[:200]}"
            except Exception:
                pass
        finally:
            if tmp_path is not None:
                p = Path(tmp_path)
                if p.exists() and str(p).startswith(tempfile.gettempdir()):
                    p.unlink()

    return enriched_count
