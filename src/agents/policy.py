"""Apply EC_POLICY_V1 to verified order facts."""

from __future__ import annotations

from ..schemas import DeliveryResult, OrderSellerResult, PaymentResult, PolicyResult, ResponsibleParty


class PolicyDecisionError(RuntimeError):
    """Raised when source facts do not satisfy any EC_POLICY_V1 rule."""


class PolicyAgent:
    """Choose the issue, cause, responsible party, refund, and action."""

    _CONFIDENCE = {
        "canceled_order_paid": 0.98,
        "unavailable_order_paid": 0.98,
        "late_delivery_seller": 0.95,
        "late_delivery_logistics": 0.95,
        "valid_split_payment": 0.95,
        "unsupported_late_claim": 0.95,
    }

    def decide(
        self,
        order_result: OrderSellerResult,
        payment_result: PaymentResult,
        delivery_result: DeliveryResult,
    ) -> PolicyResult:
        """Apply EC_POLICY_V1 strictly in the priority order from the README."""
        order_status = order_result["order_status"]
        payment_total = payment_result["payment_total_brl"]
        freight_total = payment_result["freight_total_brl"]

        # 1. Canceled paid order
        if order_status == "canceled" and payment_total > 0:
            return self._result(
                primary_issue="canceled_order_paid",
                root_cause_code="ORDER_CANCELED_AFTER_PAYMENT",
                responsible_parties=[self._party("platform", "OLIST_PLATFORM")],
                refund=payment_total,
                action="issue_full_refund",
            )

        # 2. Unavailable paid order
        if order_status == "unavailable" and payment_total > 0:
            return self._result(
                primary_issue="unavailable_order_paid",
                root_cause_code="ORDER_UNAVAILABLE_AFTER_PAYMENT",
                responsible_parties=[self._party("platform", "OLIST_PLATFORM")],
                refund=payment_total,
                action="issue_full_refund",
            )

        # 3. Late delivery caused by seller handoff after the item deadline.
        if delivery_result["is_late"] and delivery_result["seller_handoff_late"]:
            seller_ids = delivery_result["violating_seller_ids"]
            if not seller_ids:
                raise PolicyDecisionError("Seller-late result is missing a violating seller ID")
            return self._result(
                primary_issue="late_delivery_seller",
                root_cause_code="SELLER_HANDOFF_AFTER_LIMIT",
                responsible_parties=[self._party("seller", seller_id) for seller_id in seller_ids],
                refund=freight_total,
                action="refund_freight",
            )

        # 4. Late delivery despite a carrier handoff within the seller deadline.
        if delivery_result["is_late"] and delivery_result["seller_handoff_within_limit"]:
            return self._result(
                primary_issue="late_delivery_logistics",
                root_cause_code="CARRIER_DELIVERED_AFTER_ESTIMATE",
                responsible_parties=[self._party("logistics_provider", "LOGISTICS_PROVIDER")],
                refund=freight_total,
                action="refund_freight",
            )

        # 5. Multiple reconciled payment rows are valid, with no refund.
        if payment_result["is_split_payment"] and payment_result["payment_matches"]:
            return self._result(
                primary_issue="valid_split_payment",
                root_cause_code="MULTIPLE_PAYMENTS_RECONCILED",
                responsible_parties=[],
                refund=0.0,
                action="explain_valid_split_payment",
            )

        # 6. A late-delivery request is unsupported when delivery met the estimate.
        if delivery_result["delivery_within_estimate"] and payment_result["payment_matches"]:
            return self._result(
                primary_issue="unsupported_late_claim",
                root_cause_code="DELIVERY_WITHIN_ESTIMATE",
                responsible_parties=[],
                refund=0.0,
                action="reject_late_refund",
            )

        raise PolicyDecisionError(
            "Facts do not match an EC_POLICY_V1 rule; do not invent a resolution. "
            f"status={order_status}, late={delivery_result['is_late']}, "
            f"payment_matches={payment_result['payment_matches']}"
        )

    def _result(
        self,
        *,
        primary_issue: str,
        root_cause_code: str,
        responsible_parties: list[ResponsibleParty],
        refund: float,
        action: str,
    ) -> PolicyResult:
        return {
            "primary_issue": primary_issue,
            "case_status": "action_required" if refund > 0 else "no_action",
            "confidence": self._CONFIDENCE[primary_issue],
            "root_cause_code": root_cause_code,
            "responsible_parties": responsible_parties,
            "recommended_refund_brl": round(refund, 2),
            "resolution_actions": [action],
        }

    @staticmethod
    def _party(party_type: str, party_id: str) -> ResponsibleParty:
        return {"party_type": party_type, "party_id": party_id}
