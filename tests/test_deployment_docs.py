from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_deployment_docs_require_streamlit_websockets() -> None:
    """Azure runbook must enable the WebSocket transport Streamlit needs."""
    deployment = (REPO_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")

    assert "--web-sockets-enabled true" in deployment
    assert "--query webSocketsEnabled" in deployment
