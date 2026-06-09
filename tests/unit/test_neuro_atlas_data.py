import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ATLAS_DATA = ROOT / "tools" / "neuro-atlas" / "data"
IMAGE_DIR = ROOT / "library" / "Neuroscience7thed" / "images"


def _load_plate(plate_id: str) -> dict:
    return json.loads((ATLAS_DATA / "plates" / f"{plate_id}.json").read_text())


def test_neuro_atlas_manifest_references_valid_plate_files() -> None:
    manifest = json.loads((ATLAS_DATA / "manifest.json").read_text())

    assert manifest["plates"]
    for plate_id in manifest["plates"]:
        plate = _load_plate(plate_id)
        assert plate["id"] == plate_id
        assert plate["displayName"]
        assert (IMAGE_DIR / plate["filename"]).is_file()
        assert isinstance(plate["regions"], list)


def test_neuro_atlas_manifest_includes_all_local_images() -> None:
    manifest = json.loads((ATLAS_DATA / "manifest.json").read_text())
    referenced = {_load_plate(plate_id)["filename"] for plate_id in manifest["plates"]}
    local_images = {
        path.name
        for path in IMAGE_DIR.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    }

    assert local_images <= referenced


def test_neuro_atlas_data_fetches_bypass_browser_cache() -> None:
    atlas_js = (ROOT / "tools" / "neuro-atlas" / "atlas.js").read_text()
    index_html = (ROOT / "tools" / "neuro-atlas" / "index.html").read_text()

    assert "cache: 'no-store'" in atlas_js
    assert 'src="atlas.js?v=' in index_html
