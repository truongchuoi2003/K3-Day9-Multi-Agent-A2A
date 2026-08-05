"""Assess actual delivery and seller-handoff timing."""


class DeliveryAgent:
    """Determine whether delivery was late and who caused it."""

    def analyze(self, order: dict, items: list[dict]) -> dict:
        raise NotImplementedError
