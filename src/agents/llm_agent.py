import json
from typing import Any, Dict, List

from llm import call_openai, extract_json_object, get_llm_model, is_llm_enabled


class LLMAgent:
    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not is_llm_enabled():
            raise RuntimeError("LLM is not enabled. Set USE_LLM=1 and OPENAI_API_KEY.")

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = call_openai(messages, model=get_llm_model(), temperature=0.0)
        parsed = extract_json_object(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object")
        return parsed

    @staticmethod
    def _normalize_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _normalize_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1")
        return bool(value)

    @staticmethod
    def _normalize_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default
