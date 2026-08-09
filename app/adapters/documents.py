"""Document adapters: fetch source files, and store a rendered document.

Google Drive and Microsoft 365 sit on both sides of the pipeline — they are where
source evidence comes from, and where a rendered proposal is filed. One adapter
per provider, capabilities covering both directions.

Task 11 replaces the rendering path with real HTML→PDF. Until then this is
fixture-backed like every other boundary, so the pipeline is exercisable end to
end from day one.
"""

from app.adapters.base import FixtureAdapter


class _DocumentAdapter(FixtureAdapter):
    _capabilities = ("fetch_file", "list_folder", "store_document", "fetch_document")
    _echo_keys = ("documentId", "sourceRecordId")


class DriveAdapter(_DocumentAdapter):
    provider = "google_drive"


class M365Adapter(_DocumentAdapter):
    provider = "microsoft_365"
