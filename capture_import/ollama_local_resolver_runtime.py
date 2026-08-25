"""Local-only Ollama HTTP runtime for the standalone resolver experiment."""

from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlparse
import urllib.error
import urllib.request


DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"

_SYSTEM_INSTRUCTION = (
    "You are Coin Analyzer's local identity resolver experiment. "
    "Use only the evidence in the supplied request. Return exactly one JSON object "
    "matching response_contract, with no markdown or extra text. If the evidence is "
    "insufficient, set abstain=true and use null for unsupported identity fields. "
    "Set confidence=null because this Ollama runtime does not expose calibrated score "
    "semantics. Do not invent catalogue facts or ground truth."
)


class OllamaRuntimeError(RuntimeError):
    """Raised when the local Ollama HTTP boundary cannot return a usable response."""


def _require_loopback_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint must be a non-empty string")
    value = endpoint.strip()
    parsed = urlparse(value)
    if parsed.scheme != "http":
        raise ValueError("Ollama endpoint must use http on a loopback host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Ollama endpoint must not contain credentials, query, or fragment")
    if parsed.path != "/api/generate":
        raise ValueError("Ollama endpoint path must be /api/generate")
    host = parsed.hostname
    if host is None:
        raise ValueError("Ollama endpoint must include a loopback host")
    if host.casefold() == "localhost":
        return value
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Ollama endpoint host must be localhost or a loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("Ollama endpoint host must be loopback-only")
    return value


class OllamaLocalResolverRuntime:
    """Invoke an Ollama model through a loopback-only HTTP endpoint."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be a positive number")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")
        self.model = model.strip()
        self.endpoint = _require_loopback_endpoint(endpoint)
        self.timeout_seconds = float(timeout_seconds)

    def invoke(self, request_json: str) -> str:
        if not isinstance(request_json, str) or not request_json.strip():
            raise OllamaRuntimeError("resolver request must be a non-empty JSON string")
        try:
            request_payload = json.loads(request_json)
        except json.JSONDecodeError as exc:
            raise OllamaRuntimeError("resolver request is not valid JSON") from exc
        if not isinstance(request_payload, dict):
            raise OllamaRuntimeError("resolver request must be a JSON object")

        body = json.dumps(
            {
                "model": self.model,
                "system": _SYSTEM_INSTRUCTION,
                "prompt": request_json,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaRuntimeError(f"local Ollama request failed: {exc}") from exc

        try:
            envelope = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise OllamaRuntimeError("Ollama response envelope is not valid JSON") from exc
        if not isinstance(envelope, dict):
            raise OllamaRuntimeError("Ollama response envelope must be a JSON object")
        model_response = envelope.get("response")
        if not isinstance(model_response, str) or not model_response.strip():
            raise OllamaRuntimeError("Ollama response envelope is missing a non-empty response")

        try:
            payload = json.loads(model_response)
        except json.JSONDecodeError as exc:
            raise OllamaRuntimeError("Ollama model response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise OllamaRuntimeError("Ollama model response must be a JSON object")
        payload["confidence"] = None
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
