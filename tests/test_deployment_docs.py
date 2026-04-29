from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_deployment_docs_document_public_safe_deployment() -> None:
    """The deployment runbook documents the public-safe Next.js deployment contract."""
    deployment = (REPO_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")

    assert "Production serves the Next.js dashboard" in deployment
    assert "public-safe" in deployment
    assert "Port Contract" in deployment
    assert "/api/health" in deployment
