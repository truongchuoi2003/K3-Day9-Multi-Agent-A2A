"""Minimal, secret-safe GPT-4o-mini client for coordinator audit handoffs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import MODEL_NAME, OPENAI_API_URL


class LLMClientError(RuntimeError):
    """Raised when the required model audit cannot be completed."""


class OpenAIHandoffClient:
    """Call GPT-4o-mini without exposing the API key in logs or artifacts."""

    def __init__(self, api_key: str, model: str = MODEL_NAME) -> None:
        if not api_key:
            raise LLMClientError("OPENAI_API_KEY is missing; add it to .env")
        self._api_key = api_key
        self.model = model

    @classmethod
    def from_environment(cls, dotenv_path: str | Path = ".env") -> "OpenAIHandoffClient":
        api_key = os.getenv("OPENAI_API_KEY") or cls._read_dotenv_key(Path(dotenv_path))
        return cls(api_key=api_key)

    def audit_case(self, case_id: str, facts: dict[str, Any]) -> dict[str, Any]:
        """Request a concise JSON audit without delegating policy decisions.

        The deterministic agents remain the only source of issue, party, refund,
        evidence, and output values. The model's audit is retained in trace only.
        """
        system_message = (
            "You are the GPT-4o-mini audit handoff in an e-commerce dispute pipeline. "
            "Do not change policy decisions, amounts, entities, or evidence. "
            "Read the supplied deterministic facts and return only valid JSON with "
            "keys: summary_vi (string, <= 40 words), facts_consistent (boolean)."
        )
        user_message = json.dumps({"case_id": case_id, "facts": facts}, ensure_ascii=False, default=str)
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        }
        request = Request(
            OPENAI_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise LLMClientError(f"GPT-4o-mini request failed with HTTP {error.code}") from error
        except URLError as error:
            raise LLMClientError(f"GPT-4o-mini request could not reach OpenAI: {error.reason}") from error

        try:
            content = body["choices"][0]["message"]["content"]
            audit = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise LLMClientError("GPT-4o-mini returned an invalid audit response") from error
        if not isinstance(audit, dict) or not isinstance(audit.get("summary_vi"), str):
            raise LLMClientError("GPT-4o-mini audit is missing summary_vi")
        if not isinstance(audit.get("facts_consistent"), bool):
            raise LLMClientError("GPT-4o-mini audit is missing facts_consistent")
        return {
            "model": self.model,
            "summary_vi": audit["summary_vi"][:300],
            "facts_consistent": audit["facts_consistent"],
        }

    @staticmethod
    def _read_dotenv_key(path: Path) -> str:
        """Read only OPENAI_API_KEY from a local .env file; never log its value."""
        if not path.is_file():
            return ""
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == "OPENAI_API_KEY":
                return value.strip().strip('"').strip("'")
        return ""
