#!/usr/bin/env python
"""Generate a minimal NWB fixture for DANDI enrichment tests.

Run once: uv run tests/fixtures/make_dandi_fixture.py
Output:   tests/fixtures/dandi_sample.nwb

The file is committed to git so tests never need to regenerate it.
"""
from datetime import datetime, timezone
from pathlib import Path
from pynwb import NWBFile, NWBHDF5IO

OUTPUT = Path(__file__).parent / "dandi_sample.nwb"


def main():
    nwbfile = NWBFile(
        session_description="Motor cortex recording during lever pressing task",
        identifier="test-fixture-001",
        session_start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    device = nwbfile.create_device(name="array", description="test array", manufacturer="test")
    nwbfile.create_electrode_group(
        name="tetrode1",
        description="test electrode group",
        location="CA1",
        device=device,
    )
    nwbfile.add_electrode_column(name="sampling_rate", description="sampling rate in Hz")
    nwbfile.add_electrode(
        x=1.0,
        y=2.0,
        z=3.0,
        imp=-1.0,
        location="CA1",
        filtering="300-3000 Hz",
        group=nwbfile.electrode_groups["tetrode1"],
        group_name="tetrode1",
        sampling_rate=30000.0,
    )
    with NWBHDF5IO(str(OUTPUT), "w") as io:
        io.write(nwbfile)
    print(f"Written: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
