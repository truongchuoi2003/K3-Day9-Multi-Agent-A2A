"""Declared runtime and model configuration for submission compliance."""

# This pipeline makes deterministic EC_POLICY_V1 decisions and does not call an
# LLM provider. Therefore no agent uses a model with parameters over 10B.
MODEL_NAME = "rule-based / no LLM"
MODEL_PARAMETER_SIZE = "N/A"
FRAMEWORK = "Python + pandas"
RUNTIME = "local"
USES_LLM = False
MAX_ALLOWED_MODEL_PARAMETERS = 10_000_000_000
