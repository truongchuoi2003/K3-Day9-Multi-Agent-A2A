"""Validate final output against source data and the submission schema."""


class VerifierAgent:
    """Reject invalid IDs, unsupported evidence, inconsistent money, or schema errors."""

    def verify(self, output: dict) -> list[str]:
        raise NotImplementedError
