import os
from datetime import datetime
from typing import Dict, Any

import pandas as pd

from llm import is_llm_enabled


class VerifierAgent:
    """Verify claimed order IDs against Olist orders.csv."""

    def __init__(self, data_dir: str = None):
        if data_dir:
            self.data_dir = data_dir
        else:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.data_dir = os.path.join(base, "data")

    @staticmethod
    def _extract_claimed_order_id(case: Dict[str, Any]) -> str | None:
        if isinstance(case.get("customer_request"), dict):
            return case["customer_request"].get("claimed_order_id") or case.get("claimed_order_id")
        return case.get("claimed_order_id")

    def _load_orders(self) -> pd.DataFrame:
        path = os.path.join(self.data_dir, "orders.csv")
        if os.path.exists(path):
            return pd.read_csv(path, dtype=str)
        return pd.DataFrame()

    def run(self, case: Dict[str, Any]) -> Dict[str, Any]:
        case_id = case.get("case_id")
        claimed_order_id = self._extract_claimed_order_id(case)
        orders = self._load_orders()

        result = {
            "case_id": case_id,
            "agent_id": "verifier_agent",
            "verified": False,
            "reason": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if not claimed_order_id:
            result["reason"] = "missing_claimed_order_id"
            return result

        if orders.empty:
            result["reason"] = "orders_csv_missing"
            return result

        available_order_ids = set(orders["order_id"].astype(str).tolist())
        if str(claimed_order_id) not in available_order_ids:
            result["reason"] = "order_not_found"
            return result

        result["verified"] = True
        return result
