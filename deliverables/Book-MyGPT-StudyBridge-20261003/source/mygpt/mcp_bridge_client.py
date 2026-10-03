"""Bounded loopback client for the local MCP bridge, not a Your dot connector.

The ingest credential authenticates only the local mygpt-to-bridge hop. An ACK
does NOT prove event delivery, a dot subscription, or the identity of a decision
author. Do not bind this structural ``report`` interface to a production DotPort
until the host separately verifies actual Your dot authentication/provenance.
In particular, BookProgressRelay's ``reported_to_dot`` label is not suitable for
this local prototype. No method starts a model, renderer, or relay.decide().
"""
from __future__ import annotations

import asyncio
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .book_progress import BookProgress, DotDecision, ProgressError


MAX_BYTES = 8192
TIMEOUT_SECONDS = 2
_INTERPRETATION = "position is not comprehension; idle is not proof of distraction"


class LocalBridgeError(ProgressError):
    """A local transport/contract failure; never evidence of a dot response."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LocalBridgeError("local bridge redirects are not allowed")


class LocalMcpBridgeClient:
    """Use only the separate MYGPT_INGEST_TOKEN, never MCP_BRIDGE_TOKEN.

    ``report`` acknowledges local ingestion only. ``take_decision`` returns a
    schema-validated, untrusted decision candidate, not permission to speak.
    The real host must authenticate provenance and recheck current lease,
    session, sequence, visibility and cooldown in BookProgressRelay.decide().
    Timed-out writes have an unknown outcome and are never retried here.
    """

    def __init__(self, origin: str, ingest_token: str):
        # Exact spelling avoids urlsplit's stripping of control characters,
        # alternate IP spellings, userinfo, paths and accidental SSRF expansion.
        match = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})", origin) if isinstance(origin, str) else None
        if match is None or not 1 <= int(match.group(1)) <= 65535:
            raise ValueError("bridge origin must be exactly http://127.0.0.1:PORT")
        if (not isinstance(ingest_token, str) or not 32 <= len(ingest_token) <= 512
                or any(not 33 <= ord(char) <= 126 for char in ingest_token)):
            raise ValueError("ingest token must be 32..512 non-whitespace ASCII characters")
        self._origin = origin
        self._token = ingest_token
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _post(self, endpoint: str, payload: dict) -> dict:
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise LocalBridgeError("local bridge request exceeds 8192 bytes")
        request = Request(self._origin + endpoint, data=raw, method="POST", headers={
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200 or response.headers.get_content_type() != "application/json":
                    raise LocalBridgeError("invalid local bridge HTTP response")
                body = response.read(MAX_BYTES + 1)
        except HTTPError as error:
            error.close()
            raise LocalBridgeError("local bridge request failed") from None
        except (URLError, OSError):
            # Do not echo response bodies, server error text, or credentials.
            raise LocalBridgeError("local bridge request failed") from None
        if len(body) > MAX_BYTES:
            raise LocalBridgeError("local bridge response exceeds 8192 bytes")
        try:
            result = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise LocalBridgeError("local bridge response is not JSON") from None
        if not isinstance(result, dict):
            raise LocalBridgeError("local bridge response must be an object")
        return result

    async def _request(self, endpoint: str, payload: dict) -> dict:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._post, endpoint, payload),
                                          timeout=TIMEOUT_SECONDS)
        except TimeoutError:
            raise LocalBridgeError("local bridge request timed out; outcome unknown") from None

    async def report(self, feedback: dict) -> None:
        """Send validated progress only; ignore neither extra fields nor errors."""
        if (not isinstance(feedback, dict) or set(feedback) != {"schema", "progress", "interpretation"}
                or feedback["schema"] != "mygpt.dot-study-feedback.v1"
                or feedback["interpretation"] != _INTERPRETATION
                or not isinstance(feedback["progress"], dict)):
            raise LocalBridgeError("invalid study-feedback envelope")
        try:
            progress = BookProgress.model_validate(feedback["progress"])
        except ValueError:
            raise LocalBridgeError("invalid Book progress contract") from None
        result = await self._request("/local/progress", progress.wire())
        if result.get("status") not in ("accepted_locally_not_dot_delivery", "duplicate_ignored"):
            raise LocalBridgeError("local ingestion was not acknowledged")

    async def take_decision(self) -> dict | None:
        """Take a decision candidate once; caller still owns provenance/safety."""
        result = await self._request("/local/decisions/take", {})
        if result.get("status") == "unavailable" and result.get("decision") is None:
            return None
        if result.get("status") != "available" or not isinstance(result.get("decision"), dict):
            raise LocalBridgeError("invalid local decision envelope")
        try:
            decision = DotDecision.model_validate(result["decision"])
        except ValueError:
            raise LocalBridgeError("invalid dot decision contract") from None
        return decision.model_dump(mode="json")

    async def disconnect(self) -> None:
        """Clear local bridge state; the caller must also clear its relay state."""
        result = await self._request("/local/disconnect", {})
        if result.get("status") != "disconnected":
            raise LocalBridgeError("local disconnect was not acknowledged")

