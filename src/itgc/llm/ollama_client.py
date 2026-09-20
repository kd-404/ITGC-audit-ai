"""Thin client for a local Ollama server.

This deliberately does NOT try to reach the network beyond localhost/the
configured OLLAMA_HOST - the whole point of running against Ollama is that
client evidence never leaves the auditor's machine. If Ollama isn't reachable
(e.g. running this in a sandboxed/CI environment, or the user hasn't started
`ollama serve`), every call fails fast and the caller falls back to a
deterministic template - the pipeline never blocks on the LLM being available.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    host: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.environ.get("OLLAMA_MODEL", "llama3.1")
    timeout_s: float = 20.0


class OllamaUnavailable(Exception):
    pass


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig()

    def is_reachable(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.config.host}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Calls Ollama's /api/generate with format=json and returns the parsed dict.
        Raises OllamaUnavailable on any connection/timeout/parse failure - callers
        must catch this and use a deterministic fallback, per the "LLM never blocks
        or changes the verdict" principle."""
        payload = {
            "model": self.config.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.config.host}/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise OllamaUnavailable(f"Could not reach Ollama at {self.config.host}: {e}") from e

        text = raw.get("response", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise OllamaUnavailable(f"Ollama returned non-JSON output: {e}") from e
