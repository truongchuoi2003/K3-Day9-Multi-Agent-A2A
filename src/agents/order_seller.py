"""Retrieve order, item, seller, and shipping-limit facts."""


class OrderSellerAgent:
    """Inspect order status and seller handoff deadlines."""

    def analyze(self, order_id: str) -> dict:
        raise NotImplementedError
