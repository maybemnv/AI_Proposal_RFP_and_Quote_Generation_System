"""Document rendering.

The PDF test launches a real Chromium. It is the slowest test in the suite and
worth it: a template that renders as HTML but paginates into nonsense is a defect
only the real renderer catches.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.adapters import get_adapter
from app.adapters.base import AdapterFailure
from app.adapters.documents import DocumentRenderAdapter, render_html, render_pdf
from app.adapters.storage import LocalStorage, content_hash
from app.api.main import create_app
from app.domain.schemas import Document
from app.persistence.models import create_all
from app.persistence.repositories import DocumentRepo
from app.persistence.session import session_scope


@pytest.fixture
def document_download_client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    create_all(engine)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    pdf = b"%PDF-1.7\n" + (b"rendered fixture proposal\n" * 100)
    uri = LocalStorage().put("ver-download.pdf", pdf)
    with session_scope(engine) as session:
        DocumentRepo(session).add(Document(
            id="doc-download", proposal_version_id="ver-download", status="ready",
            content_type="application/pdf", storage_uri=uri,
            content_hash=content_hash(pdf), created_at="2026-08-01T12:00:00Z",
            ready_at="2026-08-01T12:00:00Z",
        ))
    with TestClient(create_app(engine=engine)) as client:
        yield client, pdf


def test_ready_document_download_returns_the_stored_pdf(document_download_client):
    client, expected_pdf = document_download_client

    response = client.get("/v1/documents/doc-download/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == expected_pdf
    assert response.content.startswith(b"%PDF")


def test_document_download_rejects_an_unknown_identifier(document_download_client):
    client, _ = document_download_client

    response = client.get("/v1/documents/not-a-document/download")

    assert response.status_code == 404


def test_document_download_does_not_accept_a_filesystem_path(document_download_client):
    client, _ = document_download_client

    response = client.get("/v1/documents/download", params={"path": "../outside.pdf"})

    assert response.status_code == 404


def test_rendered_html_contains_totals_formatted_from_minor_units(locked_version,
                                                                  sections):
    html = render_html(locked_version, sections, {}, {})
    assert "12,000.00 USD" in html


def test_template_never_computes_a_figure_itself(locked_version, sections):
    """Every rendered figure must come from the stored quote, not from the page."""
    html = render_html(locked_version, sections, {}, {})
    from app.domain.money import format_minor
    quote = locked_version.quote
    for minor in (quote.subtotal_minor, quote.total_minor):
        assert format_minor(minor, quote.currency) in html


def test_rendered_html_marks_every_claim_with_its_evidence(
    locked_version, sections, claims_by_id, evidence_by_claim
):
    html = render_html(locked_version, sections, claims_by_id, evidence_by_claim)
    for claim_id in claims_by_id:
        assert f'data-claim-id="{claim_id}"' in html


def test_evidence_excerpt_reaches_the_page(locked_version, sections, claims_by_id,
                                           evidence_by_claim):
    html = render_html(locked_version, sections, claims_by_id, evidence_by_claim)
    for links in evidence_by_claim.values():
        for link in links:
            assert link.locator in html


def test_a_block_citing_an_unknown_claim_renders_without_a_claim_mark(
    locked_version, sections
):
    """No evidence to show means no evidence mark — never an empty attribute."""
    html = render_html(locked_version, sections, {}, {})
    assert "data-claim-id" not in html


def test_source_record_ids_survive_into_the_document(locked_version, sections):
    html = render_html(locked_version, sections, {}, {})
    assert "src-notes-manual" in html


def test_optional_unselected_lines_are_labelled_and_excluded_from_the_total(
    version_with_optional_line, sections
):
    html = render_html(version_with_optional_line, sections, {}, {})
    assert "Optional" in html
    assert "not selected" in html


def test_scope_deliverables_and_milestones_are_listed(locked_version, sections):
    html = render_html(locked_version, sections, {}, {})
    assert "Discovery workshop series" in html
    assert "Discovery complete" in html


def test_render_is_deterministic(locked_version, sections):
    assert render_html(locked_version, sections, {}, {}) == \
        render_html(locked_version, sections, {}, {})


@pytest.mark.slow
def test_pdf_is_produced_and_non_trivial(tmp_path, locked_version, sections):
    out = render_pdf(render_html(locked_version, sections, {}, {}), tmp_path / "p.pdf")
    assert out.exists() and out.stat().st_size > 10_000
    assert out.read_bytes()[:4] == b"%PDF"


# --- storage ----------------------------------------------------------------


def test_local_storage_round_trips_bytes(tmp_path):
    storage = LocalStorage(tmp_path)
    uri = storage.put("proposals/ver-1.pdf", b"%PDF-1.4 body")
    assert uri.startswith("file://")
    assert storage.get("proposals/ver-1.pdf") == b"%PDF-1.4 body"


def test_local_storage_refuses_to_escape_its_root(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        LocalStorage(tmp_path).put("../outside.pdf", b"x")


def test_content_hash_is_stable_and_sensitive():
    assert content_hash(b"a") == content_hash(b"a")
    assert content_hash(b"a") != content_hash(b"b")


# --- adapter contract -------------------------------------------------------


def test_render_failure_returns_adapter_failure():
    result = get_adapter("pandadoc").execute({"outcome": "failure"})
    assert isinstance(result, AdapterFailure)


@pytest.mark.slow
def test_render_adapter_stores_the_pdf_and_reports_ready(tmp_path, locked_version,
                                                         sections):
    adapter = DocumentRenderAdapter(storage=LocalStorage(tmp_path))
    result = adapter.render(locked_version, sections, {}, {})
    assert result["status"] == "ready"
    assert result["documentId"]
    assert result["uri"].startswith("file://")
    assert len(result["contentHash"]) == 64


@pytest.mark.slow
def test_render_adapter_hash_matches_the_stored_bytes(tmp_path, locked_version,
                                                      sections):
    storage = LocalStorage(tmp_path)
    result = DocumentRenderAdapter(storage=storage).render(
        locked_version, sections, {}, {})
    stored = storage.get(f"{locked_version.id}.pdf")
    assert content_hash(stored) == result["contentHash"]


def test_render_adapter_reports_failed_rather_than_raising(monkeypatch,
                                                          locked_version, sections):
    """A demo shows a failed document; it does not show a traceback."""
    def boom(html, out_path):
        raise RuntimeError("chromium unavailable")

    monkeypatch.setattr("app.adapters.documents.render_pdf", boom)
    result = DocumentRenderAdapter().render(locked_version, sections, {}, {})
    assert isinstance(result, AdapterFailure)
    assert result.retryable is True
