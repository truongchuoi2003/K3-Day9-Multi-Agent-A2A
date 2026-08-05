"""Reconcile order payments against item and freight totals."""

from __future__ import annotations

from collections.abc import Sequence

from ..data_loader import DataLoader, DatasetError
from ..schemas import ItemFact, PaymentResult


class PaymentAgent:
    """Calculate payment totals, reconciliation status, and payment evidence."""

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader = data_loader

    def analyze(self, order_id: str, items: Sequence[ItemFact]) -> PaymentResult:
        """Reconcile payments with supplied item and freight facts.

        A payment total is considered reconciled when it is within 0.10 BRL of
        ``item_total_brl + freight_total_brl``, as required by EC_POLICY_V1.
        """
        payments = self.data_loader.get_order_payments(order_id)

        if payments["payment_value"].isna().any():
            raise DatasetError(f"Order {order_id} contains a payment row without payment_value")

        item_total = round(sum(float(item["price"]) for item in items), 2)
        freight_total = round(sum(float(item["freight_value"]) for item in items), 2)
        payment_total = round(float(payments["payment_value"].sum()), 2)
        expected_total = round(item_total + freight_total, 2)

        payment_sequentials = [int(value) for value in payments["payment_sequential"].tolist()]
        payment_ids = [f"{order_id}:{sequential}" for sequential in payment_sequentials]
        payment_evidence_ids = [
            f"payment:{order_id}:{sequential}" for sequential in payment_sequentials
        ]

        return {
            "payment_ids": payment_ids,
            "payment_evidence_ids": payment_evidence_ids,
            "payment_sequentials": payment_sequentials,
            "item_total_brl": item_total,
            "freight_total_brl": freight_total,
            "payment_total_brl": payment_total,
            "payment_matches": abs(payment_total - expected_total) <= 0.10,
            "is_split_payment": len(payments) >= 2,
        }
