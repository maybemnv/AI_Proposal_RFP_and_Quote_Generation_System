"""Where rendered documents land.

Local disk, because a prototype should not need a bucket to show a PDF. The
interface is the part that matters: `put` takes bytes and returns a URI, so
swapping in object storage later is one class, not a change at every call site.

`content_hash` lives here rather than in the renderer because the hash belongs to
the stored bytes. It is what lets a locked version prove the document a client
received is the document that was approved (I5).
"""

import hashlib
import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

DEFAULT_STORAGE_DIR = Path("var") / "documents"


def storage_dir() -> Path:
    """Read at call time so a test can point STORAGE_DIR at a tmp_path."""
    configured = os.environ.get("STORAGE_DIR")
    return Path(configured) if configured else DEFAULT_STORAGE_DIR


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Storage(Protocol):
    def put(self, path: str, data: bytes) -> str: ...
    def get(self, path: str) -> bytes: ...
    def get_uri(self, uri: str) -> bytes: ...
    def signed_url(self, uri: str, expires: int = 300) -> str: ...


class LocalStorage:
    """Files under STORAGE_DIR. `put` returns a `file://` URI."""

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(root) if root is not None else None

    @property
    def root(self) -> Path:
        # Resolved per access, not captured at construction, so the adapter can
        # be built once at import and still honour a test's STORAGE_DIR.
        return self._root if self._root is not None else storage_dir()

    def _resolve(self, path: str) -> Path:
        target = (self.root / path).resolve()
        root = self.root.resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"path escapes the storage root: {path!r}")
        return target

    def put(self, path: str, data: bytes) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target.as_uri()

    def get(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def get_uri(self, uri: str) -> bytes:
        return self.get(Path(uri).name)

    def signed_url(self, uri: str, expires: int = 300) -> str:
        return uri


class S3Storage:
    """Private S3-compatible storage; credentials stay in the server environment."""

    def __init__(self) -> None:
        import boto3

        self.bucket = os.environ["S3_BUCKET"]
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            region_name=os.getenv("S3_REGION", "auto"),
        )

    def put(self, path: str, data: bytes) -> str:
        key = f"documents/{uuid4().hex}.pdf"
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType="application/pdf"
        )
        return f"s3://{self.bucket}/{key}"

    def get(self, path: str) -> bytes:
        raise ValueError("S3 objects must be addressed by their storage URI")

    def get_uri(self, uri: str) -> bytes:
        bucket, key = _parse_s3_uri(uri)
        return self.client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def signed_url(self, uri: str, expires: int = 300) -> str:
        bucket, key = _parse_s3_uri(uri)
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires
        )


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    scheme, _, value = uri.partition("://")
    bucket, _, key = value.partition("/")
    if scheme != "s3" or not bucket or not key:
        raise ValueError("invalid private object storage URI")
    return bucket, key


def storage_from_env() -> Storage:
    return S3Storage() if os.getenv("STORAGE_BACKEND", "local").lower() == "s3" else LocalStorage()
