"""Source ingestion. ``manual`` is the paste-and-upload path: always available,
no credentials, and the fallback whenever a CRM or drive connector is not
configured. It is also a document sink, so a rendered proposal can be downloaded
rather than pushed to a provider."""

from app.adapters.base import FixtureAdapter


class ManualAdapter(FixtureAdapter):
    provider = "manual"
    _capabilities = ("upload_file", "paste_text", "store_document", "fetch_document")
    _echo_keys = ("documentId", "sourceRecordId")
