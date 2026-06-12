"""Guard: the legacy chunk retriever must stay eval-only (no production caller)."""
import pathlib

API_DIR = pathlib.Path(__file__).resolve().parent.parent / "api"


def test_no_production_module_references_retrieve_chunks():
    offenders = []
    for path in API_DIR.rglob("*.py"):
        if path.name == "rag.py":          # definition lives here; allowed
            continue
        text = path.read_text(encoding="utf-8")
        if "retrieve_chunks" in text:
            offenders.append(str(path.relative_to(API_DIR.parent)))
    assert offenders == [], (
        "retrieve_chunks is legacy/eval-only and must not be used in production: "
        + ", ".join(offenders)
    )
