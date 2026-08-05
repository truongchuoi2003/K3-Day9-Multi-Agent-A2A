"""Apply EC_POLICY_V1 to verified order facts."""


class PolicyAgent:
    """Choose the issue, cause, responsible party, refund, and action."""

    def decide(self, order_result: dict, payment_result: dict, delivery_result: dict) -> dict:
        raise NotImplementedError
