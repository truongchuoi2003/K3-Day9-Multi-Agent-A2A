"""Assess actual delivery and seller-handoff timing."""

from __future__ import annotations

from collections.abc import Sequence

from ..schemas import DeliveryResult, ItemFact, OrderSellerResult


class DeliveryAgent:
    """Determine whether delivery was late and which sellers handed off late."""

    def analyze(
        self, order_facts: OrderSellerResult, items: Sequence[ItemFact] | None = None
    ) -> DeliveryResult:
        """Compare customer delivery and carrier handoff timestamps with deadlines.

        ``items`` is optional because the standard handoff already includes all
        item facts. It is accepted separately to make the input contract explicit
        for a coordinator that keeps order facts and item facts in separate values.
        """
        order_items = order_facts["items"] if items is None else items
        carrier_date = order_facts["carrier_date"]
        customer_delivery_date = order_facts["customer_delivery_date"]
        estimated_delivery_date = order_facts["estimated_delivery_date"]

        is_late = (
            customer_delivery_date is not None
            and estimated_delivery_date is not None
            and customer_delivery_date > estimated_delivery_date
        )
        delivery_within_estimate = (
            customer_delivery_date is not None
            and estimated_delivery_date is not None
            and customer_delivery_date <= estimated_delivery_date
        )
        handoff_timing_known = carrier_date is not None and all(
            item["shipping_limit_date"] is not None for item in order_items
        )

        violating_seller_ids: list[str] = []
        violating_item_ids: list[str] = []
        seen_seller_ids: set[str] = set()

        for item in order_items:
            shipping_limit_date = item["shipping_limit_date"]
            seller_handoff_late = (
                carrier_date is not None
                and shipping_limit_date is not None
                and carrier_date > shipping_limit_date
            )
            if not seller_handoff_late:
                continue

            violating_item_ids.append(item["item_id"])
            seller_id = item["seller_id"]
            if seller_id not in seen_seller_ids:
                violating_seller_ids.append(seller_id)
                seen_seller_ids.add(seller_id)

        return {
            "is_late": is_late,
            "delivery_within_estimate": delivery_within_estimate,
            "seller_handoff_late": bool(violating_seller_ids),
            "seller_handoff_within_limit": handoff_timing_known
            and not bool(violating_seller_ids),
            "violating_seller_ids": violating_seller_ids,
            "violating_item_ids": violating_item_ids,
        }
