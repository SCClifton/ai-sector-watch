from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_deployment_docs_document_cutover() -> None:
    """After Phase 3 (#68) the runbook documents the Next.js cutover and rollback."""
    deployment = (REPO_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")

    # The cutover section names the rollback tag and the new health endpoint.
    assert "Cutover from Streamlit to Next.js" in deployment
    assert "streamlit-final" in deployment
    assert "/api/health" in deployment
