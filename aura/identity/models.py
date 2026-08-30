"""Operator identity models."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any


def hash_subject(subject: str) -> str:
    return sha256(subject.encode("utf-8")).hexdigest()[:16]


@dataclass
class OperatorIdentity:
    """Verified or declared operator attached to a session."""

    verified: bool
    method: str
    subject: str
    email: str | None = None
    name: str | None = None
    session_ref: str | None = None
    issuer: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)

    def to_operator_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "verified": self.verified,
            "method": self.method,
            "subject": self.subject,
            "subject_hash": hash_subject(self.subject),
        }
        if self.email:
            data["email"] = self.email
        if self.name:
            data["name"] = self.name
        if self.session_ref:
            data["session_ref"] = self.session_ref
        if self.issuer:
            data["issuer"] = self.issuer
        return data

    def bind_payload(self) -> dict[str, Any]:
        payload = {"operator": self.to_operator_dict()}
        if self.claims:
            payload["claim_keys"] = sorted(self.claims.keys())
        return payload
