"""Declared runtime and model configuration for the submission."""

# Required by the instructor. The API key is read only at runtime from .env or
# OPENAI_API_KEY and is never stored in source, trace, metadata, or output.
MODEL_NAME = "gpt-4o-mini"
MODEL_PARAMETER_SIZE = "provider-managed (instructor-required model)"
FRAMEWORK = "Python + pandas + OpenAI Chat Completions API"
RUNTIME = "local"
USES_LLM = True
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
