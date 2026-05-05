import streamlit as st


_WORKBENCH_LAYOUT_JS = """
export default function(component) {
  const applyLayout = () => {
    const chatMarker = document.querySelector('.ndb-chat-pane-marker');
    const workspaceMarker = document.querySelector('.ndb-workspace-pane-marker');
    if (!chatMarker || !workspaceMarker) {
      return;
    }

    const chatColumn = chatMarker.closest('[data-testid="stColumn"]');
    const workspaceColumn = workspaceMarker.closest('[data-testid="stColumn"]');
    const horizontalBlock = chatColumn ? chatColumn.closest('[data-testid="stHorizontalBlock"]') : null;
    const main = document.querySelector('section[data-testid="stMain"]');
    const blockContainer = document.querySelector('section[data-testid="stMain"] .block-container');
    const appView = document.querySelector('[data-testid="stAppViewContainer"]');

    [document.documentElement, document.body, appView, main, blockContainer].forEach((el) => {
      if (!el) return;
      el.style.height = '100vh';
      el.style.maxHeight = '100vh';
      el.style.overflow = 'hidden';
    });

    if (blockContainer) {
      blockContainer.style.paddingTop = '1rem';
      blockContainer.style.paddingBottom = '0';
    }

    if (horizontalBlock) {
      horizontalBlock.style.height = 'calc(100vh - 2rem)';
      horizontalBlock.style.maxHeight = 'calc(100vh - 2rem)';
      horizontalBlock.style.overflow = 'hidden';
      horizontalBlock.style.alignItems = 'stretch';
    }

    if (chatColumn) {
      chatColumn.style.height = 'calc(100vh - 2rem)';
      chatColumn.style.maxHeight = 'calc(100vh - 2rem)';
      chatColumn.style.minHeight = '0';
      chatColumn.style.overflow = 'hidden';
    }

    if (workspaceColumn) {
      workspaceColumn.style.height = 'calc(100vh - 2rem)';
      workspaceColumn.style.maxHeight = 'calc(100vh - 2rem)';
      workspaceColumn.style.minHeight = '0';
      workspaceColumn.style.overflowY = 'auto';
      workspaceColumn.style.overflowX = 'hidden';
      workspaceColumn.style.paddingRight = '0.25rem';
    }
  };

  applyLayout();
  requestAnimationFrame(applyLayout);
  setTimeout(applyLayout, 50);
  setTimeout(applyLayout, 250);

  const observer = new MutationObserver(applyLayout);
  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('resize', applyLayout);

  return () => {
    observer.disconnect();
    window.removeEventListener('resize', applyLayout);
  };
}
"""


_workbench_layout_component = st.components.v2.component(
    "neurodb_workbench_layout",
    js=_WORKBENCH_LAYOUT_JS,
    isolate_styles=False,
)


def mount_workbench_layout_controller() -> None:
    """Mount a small layout controller for the Pre-LT-2 Streamlit workbench."""
    _workbench_layout_component(key="neurodb_workbench_layout", height=0)
