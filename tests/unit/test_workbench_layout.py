import pathlib


SOURCE = pathlib.Path("src/neurodb/ui/workbench_layout.py")


def test_workbench_layout_uses_streamlit_v2_component():
    source = SOURCE.read_text()

    assert "st.components.v2.component" in source
    assert "neurodb_workbench_layout" in source
    assert "isolate_styles=False" in source


def test_workbench_layout_targets_marked_top_level_panes():
    source = SOURCE.read_text()

    assert ".ndb-chat-pane-marker" in source
    assert ".ndb-workspace-pane-marker" in source
    assert "closest('[data-testid=\"stColumn\"]')" in source
    assert "closest('[data-testid=\"stHorizontalBlock\"]')" in source
    assert "MutationObserver" in source


def test_app_mounts_workbench_layout_controller():
    source = pathlib.Path("src/neurodb/ui/app.py").read_text()

    assert "from neurodb.ui.workbench_layout import mount_workbench_layout_controller" in source
    assert "mount_workbench_layout_controller()" in source
