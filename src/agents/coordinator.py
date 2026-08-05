"""Orchestrate specialist agents for one customer-support case."""


class CoordinatorAgent:
    """Collect agent results, assemble a draft, then request verification."""

    def resolve_case(self, case: dict) -> dict:
        raise NotImplementedError
