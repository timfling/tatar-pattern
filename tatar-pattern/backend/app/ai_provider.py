"""Cloud-neutral interface. The actual DSLab adapter awaits verified specification.

Only a task payload crosses this boundary; never a user/session/email. Provider
methods MUST bound network timeouts. submit is never retried unless a future
verified provider explicitly guarantees idempotency. Download must stream with
size limits, validate URLs against its configured cloud origin, and return image
bytes only. Secrets are server environment values, never payload/recipe fields.
"""
from dataclasses import dataclass
from typing import Literal, Protocol

@dataclass(frozen=True)
class CloudStatus:
    state: Literal['pending','done','failed']
    error_code: str | None = None

class Provider(Protocol):
    name: str
    model_version: str
    def submit(self, payload: dict, *, request_id: str, timeout: int) -> str: ...
    def poll(self, job_id: str, *, timeout: int) -> CloudStatus: ...
    def download(self, job_id: str, *, timeout: int, max_bytes: int) -> bytes: ...


def configured_provider():
    # Intentionally no invented endpoint, token scheme, model or test fallback.
    return None
