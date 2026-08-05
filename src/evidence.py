"""Build only source-grounded evidence IDs allowed by the submission README."""

from __future__ import annotations

from .schemas import DeliveryResult, OrderSellerResult, PaymentResult, PolicyResult


class EvidenceBuilder:
    """Create the five allowed evidence-ID kinds and cap each case at ten IDs."""

    _ALLOWED_CAUSES = frozenset(
        {
            "SELLER_HANDOFF_AFTER_LIMIT",
            "CARRIER_DELIVERED_AFTER_ESTIMATE",
            "ORDER_CANCELED_AFTER_PAYMENT",
            "ORDER_UNAVAILABLE_AFTER_PAYMENT",
            "MULTIPLE_PAYMENTS_RECONCILED",
            "DELIVERY_WITHIN_ESTIMATE",
        }
    )
    _MAX_EVIDENCE = 10

    def build(
        self,
        order_result: OrderSellerResult,
        payment_result: PaymentResult,
        delivery_result: DeliveryResult,
        policy_result: PolicyResult,
    ) -> list[str]:
        """Build evidence in README-approved formats from agent facts only."""
        root_cause = policy_result["root_cause_code"]
        if root_cause not in self._ALLOWED_CAUSES:
            raise ValueError(f"Unsupported policy evidence root cause: {root_cause}")

        order_id = order_result["order_id"]
        item_evidence = [f"item:{item['item_id']}" for item in order_result["items"]]
        if delivery_result["violating_item_ids"]:
            violating_evidence = [
                f"item:{item_id}" for item_id in delivery_result["violating_item_ids"]
            ]
            item_evidence = violating_evidence + [
                evidence for evidence in item_evidence if evidence not in violating_evidence
            ]

        seller_evidence = [f"seller:{seller_id}" for seller_id in order_result["seller_ids"]]
        candidates = item_evidence + payment_result["payment_evidence_ids"] + seller_evidence

        # Keep order and policy evidence mandatory; spend the remaining eight IDs
        # on direct item, payment, and seller records in a deterministic order.
        evidence = [
            f"order:{order_id}",
            *candidates[: self._MAX_EVIDENCE - 2],
            f"policy:{root_cause}",
        ]
        return list(dict.fromkeys(evidence))
