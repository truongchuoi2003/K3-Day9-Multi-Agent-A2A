import json
import os
from typing import Any, Dict, List

# If python-dotenv is available, load .env automatically so keys set there
# are visible to os.getenv() without manual `set` in the shell.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; if not installed, users must export env vars manually
    pass


def is_llm_enabled() -> bool:
    if os.getenv("USE_LLM", "").strip().lower() not in ("1", "true", "yes"):
        return False
    return bool(os.getenv("OPENAI_API_KEY"))


def get_llm_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.5")


def get_openai_client():
    """Create an OpenAI client lazily so imports are inside functions."""
    from openai import OpenAI

    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_json_object(text: str) -> Any:
    """Extract the first JSON object from an LLM response text."""
    if not isinstance(text, str):
        raise ValueError("LLM response must be a string")

    text = text.strip()
    if not text:
        raise ValueError("LLM response is empty")

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= 0 and end > start:
        candidate = text[start:end + 1]
    else:
        candidate = text

    return json.loads(candidate)


def call_openai(
    messages: List[Dict[str, str]],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> str:
    if not is_llm_enabled():
        raise RuntimeError("LLM is not enabled. Set USE_LLM=1 and OPENAI_API_KEY.")

    if model is None:
        model = get_llm_model()

    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        n=1,
    )

    choices = getattr(response, "choices", None) or response.get("choices")
    if not choices:
        raise RuntimeError("OpenAI returned no choices")

    choice = choices[0]
    message = getattr(choice, "message", None) or choice.get("message")
    if message is None:
        raise RuntimeError("OpenAI response missing message")

    content = getattr(message, "content", None) or message.get("content")
    if content is None:
        raise RuntimeError("OpenAI response message missing content")

    return content
