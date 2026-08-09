"""Signature adapters. Sending a document is what produces engagement events —
sent, viewed, signed — and those events are append-only records against a locked
version (I10), never edits to it."""

from typing import Any

from app.adapters.base import FixtureAdapter


class _SignatureAdapter(FixtureAdapter):
    _capabilities = ("send_for_signature", "fetch_status", "receive_engagement_events")

    def _on_success(
        self, payload: dict[str, Any], request: dict[str, Any]
    ) -> dict[str, Any]:
        document_id = request.get("documentId")
        if document_id:
            payload = {**payload, "documentId": document_id}
        return payload


class PandaDocAdapter(_SignatureAdapter):
    provider = "pandadoc"


class DocuSignAdapter(_SignatureAdapter):
    provider = "docusign"
