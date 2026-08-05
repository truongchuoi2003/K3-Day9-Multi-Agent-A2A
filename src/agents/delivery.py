import os
from datetime import datetime
from typing import Dict, Any

import pandas as pd

from agents.llm_agent import LLMAgent
from llm import is_llm_enabled
from prompts import DELIVERY_AGENT_SYSTEM_PROMPT, DELIVERY_AGENT_USER_TEMPLATE


class DeliveryAgent(LLMAgent):
    """Compare delivery timestamps to estimated and shipping limit dates.

    Uses GPT-5.5 when USE_LLM=1 and OPENAI_API_KEY is set.
    """

    def __init__(self, data_dir: str = None):
        if data_dir:
            self.data_dir = data_dir
        else:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.data_dir = os.path.join(base, "data")

    def _read(self, fname: str):
        path = os.path.join(self.data_dir, fname)
        if os.path.exists(path):
            return pd.read_csv(path, dtype=str)
        return pd.DataFrame()

    def run(self, case: Dict[str, Any]) -> Dict[str, Any]:
        case_id = case.get("case_id")
        claimed_order_id = None
        if isinstance(case.get("customer_request"), dict):
            claimed_order_id = case["customer_request"].get("claimed_order_id")
        claimed_order_id = claimed_order_id or case.get("claimed_order_id")

        orders = self._read("orders.csv")
        order_items = self._read("order_items.csv")

        result = {"case_id": case_id, "agent_id": "delivery_agent", "evidence_ids": [], "partial_results": {}, "confidence": 0.0}

        if not claimed_order_id:
            result["partial_results"] = {"error": "missing_claimed_order_id"}
            return result

        order_key = str(claimed_order_id)
        items = order_items[order_items["order_id"].astype(str) == order_key] if not order_items.empty else pd.DataFrame()
        order_row = orders[orders["order_id"].astype(str) == order_key] if not orders.empty else pd.DataFrame()

        if is_llm_enabled():
            items_records = items.to_dict("records") if not items.empty else []
            user_prompt = DELIVERY_AGENT_USER_TEMPLATE.format(
                case_id=case_id,
                order_id=order_key,
                items=json.dumps(items_records, ensure_ascii=False),
            )
            payload = self._call_llm(DELIVERY_AGENT_SYSTEM_PROMPT, user_prompt)
            result["partial_results"] = payload.get("partial_results", {})
            result["evidence_ids"] = payload.get("evidence_ids", [])
            result["confidence"] = min(max(self._normalize_float(payload.get("confidence", 0.0)), 0.0), 1.0)
            return result

        # default
        delivered_after_estimate = False
        carrier_after_shipping_limit = False

        # check per item
        if not items.empty:
            for _, r in items.iterrows():
                est = r.get("estimated_delivery_date") or r.get("estimated_delivery_date")
                shipping_limit = r.get("shipping_limit_date")
                delivered_carrier = r.get("order_delivered_carrier_date")
                delivered_customer = r.get("order_delivered_customer_date")
                try:
                    if pd.notna(est) and pd.notna(delivered_customer):
                        if pd.to_datetime(delivered_customer) > pd.to_datetime(est):
                            delivered_after_estimate = True
                    if pd.notna(shipping_limit) and pd.notna(delivered_carrier):
                        if pd.to_datetime(delivered_carrier) > pd.to_datetime(shipping_limit):
                            carrier_after_shipping_limit = True
                except Exception:
                    continue

        # fallback to order row if items didn't have dates
        if not delivered_after_estimate and order_row is not None and not order_row.empty:
            try:
                est = order_row.iloc[0].get("estimated_delivery_date")
                delivered_customer = order_row.iloc[0].get("order_delivered_customer_date")
                if pd.notna(est) and pd.notna(delivered_customer):
                    if pd.to_datetime(delivered_customer) > pd.to_datetime(est):
                        delivered_after_estimate = True
            except Exception:
                pass

        # Prepare partial
        partial = {
            "delivered_after_estimate": delivered_after_estimate,
            "carrier_after_shipping_limit": carrier_after_shipping_limit,
        }

        # evidence
        ev = []
        if not items.empty or (order_row is not None and not order_row.empty):
            ev.append(f"order:{claimed_order_id}")
        result["evidence_ids"] = ev
        result["partial_results"] = partial
        result["confidence"] = 0.9 if delivered_after_estimate or carrier_after_shipping_limit else 0.5
        return result
