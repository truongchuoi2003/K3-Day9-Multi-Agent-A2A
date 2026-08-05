"""Retrieve order, item, seller, and shipping-limit facts."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..data_loader import DataLoader, DatasetError
from ..schemas import ItemFact, OrderSellerResult


class OrderSellerAgent:
    """Build the order and seller handoff used by downstream agents."""

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader = data_loader

    def analyze(self, order_id: str) -> OrderSellerResult:
        """Retrieve one order and all of its item-level seller facts."""
        order = self.data_loader.get_order(order_id)
        item_rows = self.data_loader.get_order_items(order_id)

        items: list[ItemFact] = []
        seller_ids: list[str] = []
        seen_seller_ids: set[str] = set()

        for _, row in item_rows.iterrows():
            seller_id = str(row["seller_id"])
            if not self.data_loader.seller_exists(seller_id):
                raise DatasetError(
                    f"Item {order_id}:{row['order_item_id']} references unknown seller {seller_id}"
                )

            order_item_id = int(row["order_item_id"])
            item: ItemFact = {
                "order_item_id": order_item_id,
                "item_id": f"{order_id}:{order_item_id}",
                "product_id": str(row["product_id"]),
                "seller_id": seller_id,
                "shipping_limit_date": self._optional_timestamp(row["shipping_limit_date"]),
                "price": round(float(row["price"]), 2),
                "freight_value": round(float(row["freight_value"]), 2),
            }
            items.append(item)

            if seller_id not in seen_seller_ids:
                seller_ids.append(seller_id)
                seen_seller_ids.add(seller_id)

        return {
            "order_id": str(order["order_id"]),
            "order_status": str(order["order_status"]),
            "carrier_date": self._optional_timestamp(order["order_delivered_carrier_date"]),
            "customer_delivery_date": self._optional_timestamp(
                order["order_delivered_customer_date"]
            ),
            "estimated_delivery_date": self._optional_timestamp(
                order["order_estimated_delivery_date"]
            ),
            "items": items,
            "seller_ids": seller_ids,
        }

    @staticmethod
    def _optional_timestamp(value: Any) -> Any:
        """Convert pandas missing timestamps to None while preserving timestamps."""
        return None if pd.isna(value) else value
