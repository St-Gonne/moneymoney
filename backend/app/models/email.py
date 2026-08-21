"""
Email and Attachment Pydantic Models
Provides data structures for inbound forwarded email payloads, MIME metadata,
extracted in-memory attachments, and Identity Gate verification results.
"""

import io
from datetime import datetime
from typing import Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Graceful standard library fallback if pydantic is not installed
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self) -> dict:
            return self.model_dump()

        def model_dump(self) -> dict:
            res = {}
            for k, v in self.__dict__.items():
                if isinstance(v, BaseModel):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [i.model_dump() if isinstance(i, BaseModel) else i for i in v]
                else:
                    res[k] = v
            return res

        def __repr__(self):
            fields = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
            return f"{self.__class__.__name__}({fields})"

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.__dict__ == other.__dict__
            return False

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default


class ExtractedAttachment(BaseModel):
    """
    In-memory attachment extracted directly from email MIME parts.
    Maintains raw bytes and memory stream without disk persistence.
    """
    filename: str
    content_type: str
    size_bytes: int
    payload_bytes: bytes
    sha256: str

    def get_stream(self) -> io.BytesIO:
        """Returns an in-memory seekable byte stream for zero-disk downstream processing."""
        return io.BytesIO(self.payload_bytes)


class ExtractedEmailMetadata(BaseModel):
    """
    Normalized header and envelope metadata from forwarded emails.
    """
    forwarder_email: str
    original_sender: Optional[str] = None
    original_sender_domain: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[datetime] = None
    message_id: Optional[str] = None
    headers: Dict[str, str] = {}
    forwarded_body_header: Optional[str] = None


class InboundEmailPayload(BaseModel):
    """
    Raw inbound payload ingested from email forwarders or webhooks.
    """
    raw_mime: bytes
    forwarder_email: Optional[str] = None
    received_timestamp: Optional[datetime] = None
    target_pan: Optional[str] = None


class IdentityGateResult(BaseModel):
    """
    Result returned by Gate 1 (Identity Gate).
    Fail-closed: passed=False accompanied by typed rejection code and reason.
    """
    passed: bool
    rejection_code: Optional[str] = None
    rejection_reason: Optional[str] = None
    target_entity_id: Optional[str] = None
    target_pan: Optional[str] = None
    broker_institution: Optional[str] = None
    extracted_metadata: Optional[ExtractedEmailMetadata] = None
    extracted_attachments: List[ExtractedAttachment] = []
