"""Document adapters: fetch source files, render the proposal, and store it.

Google Drive and Microsoft 365 sit on both sides of the pipeline — they are where
source evidence comes from, and where a rendered proposal is filed. Those stay
fixture-backed, because a demo should not need a Google tenant.

Rendering is real. `render_html` builds the client-facing document from the
stored version, and `render_pdf` prints it through Chromium. Two things the
renderer will not do: compute a figure (every number comes from the quote the
pricing engine produced), and drop the evidence trail (claim-backed sentences
carry `data-claim-id` into the PDF, so I1 is visible on the page a client reads).
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.adapters.base import AdapterFailure, FixtureAdapter
from app.adapters.storage import LocalStorage, Storage, content_hash
from app.domain.money import format_minor
from app.domain.schemas import Claim, EvidenceLink, GeneratedSection, ProposalVersion

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_NAME = "proposal.html.j2"
STYLESHEET_NAME = "proposal.css"


class _DocumentAdapter(FixtureAdapter):
    _capabilities = ("fetch_file", "list_folder", "store_document", "fetch_document")
    _echo_keys = ("documentId", "sourceRecordId")


class DriveAdapter(_DocumentAdapter):
    provider = "google_drive"


class M365Adapter(_DocumentAdapter):
    provider = "microsoft_365"


# --- rendering --------------------------------------------------------------


def _environment() -> Environment:
    """StrictUndefined on purpose: a typo in the template should fail the render,
    not silently print an empty cell where a total belongs."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_ROOT),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _format_quantity(quantity: float) -> str:
    """Whole quantities print without a decimal tail; fractional ones keep it.

    In the template this was an inline conditional, which is arithmetic-adjacent
    logic living in markup. It belongs here.
    """
    return str(int(quantity)) if float(quantity).is_integer() else f"{quantity:g}"


def render_html(
    version: ProposalVersion,
    sections: list[GeneratedSection],
    claims_by_id: dict[str, Claim],
    evidence_by_claim: dict[str, list[EvidenceLink]],
    *,
    account_name: str = "",
) -> str:
    """The client-facing document as a single self-contained HTML string.

    The stylesheet is inlined rather than linked because the PDF renderer loads
    the page with `set_content` and has no base URL to resolve a relative href
    against — a linked stylesheet would silently produce an unstyled PDF.
    """
    template = _environment().get_template(TEMPLATE_NAME)
    return template.render(
        version=version,
        sections_by_key={section.key: section for section in sections},
        claims_by_id=claims_by_id,
        evidence_by_claim=evidence_by_claim,
        optional_lines=[line for line in version.quote.lines if line.optional],
        account_name=account_name or version.title,
        stylesheet=(TEMPLATE_ROOT / STYLESHEET_NAME).read_text(encoding="utf-8"),
        money=lambda minor: format_minor(minor, version.quote.currency),
        qty=_format_quantity,
    )


def render_pdf(html: str, out_path: Path) -> Path:
    """Chromium print-to-PDF. Letter, 18mm, backgrounds on.

    Backgrounds matter here: without `print_background` Chromium drops every
    fill, and the evidence marks that make claims legible go with them.
    """
    from playwright.sync_api import sync_playwright

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(out_path), format="Letter", print_background=True,
                margin={"top": "18mm", "bottom": "18mm",
                        "left": "18mm", "right": "18mm"},
            )
        finally:
            browser.close()
    return out_path


class DocumentRenderAdapter:
    """Render a version and file the result.

    Returns the same shape as any other adapter — a dict on success, an
    `AdapterFailure` on failure — so the endpoint handles rendering exactly as it
    handles a CRM import. A browser that will not launch is a `TEMPORARY`
    failure, not a traceback: the demo shows a document in `failed` state and the
    reviewer can retry.

    It reports as the `manual` provider because rendering is ours, not a
    third party's. Inventing a ninth provider would widen a closed contract
    literal for one in-house component.
    """

    provider = "manual"

    def __init__(self, storage: Storage | None = None) -> None:
        self._storage = storage or LocalStorage()

    def capabilities(self) -> list[str]:
        return ["render_document", "store_document"]

    def render(
        self,
        version: ProposalVersion,
        sections: list[GeneratedSection],
        claims_by_id: dict[str, Claim],
        evidence_by_claim: dict[str, list[EvidenceLink]],
        *,
        account_name: str = "",
    ) -> dict[str, Any] | AdapterFailure:
        import tempfile

        try:
            html = render_html(version, sections, claims_by_id, evidence_by_claim,
                               account_name=account_name)
            with tempfile.TemporaryDirectory() as tmp:
                pdf_path = render_pdf(html, Path(tmp) / f"{version.id}.pdf")
                data = pdf_path.read_bytes()
        except Exception as exc:  # noqa: BLE001 - any render failure is reportable
            return AdapterFailure(
                code="TEMPORARY", provider=self.provider,
                message=f"rendering failed: {exc}", retryable=True,
            )

        name = f"{version.id}.pdf"
        return {
            "documentId": f"doc-{version.id}",
            "status": "ready",
            "uri": self._storage.put(name, data),
            "contentHash": content_hash(data),
        }
