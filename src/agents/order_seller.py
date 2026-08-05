import os
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd

from agents.llm_agent import LLMAgent
from llm import is_llm_enabled
from prompts import ORDER_SELLER_AGENT_SYSTEM_PROMPT, ORDER_SELLER_AGENT_USER_TEMPLATE


class OrderSellerAgent(LLMAgent):
    """Collect items, seller ids and basic order info.

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

        order_items = self._read("order_items.csv")
        sellers = self._read("sellers.csv")
        orders = self._read("orders.csv")

        result = {"case_id": case_id, "agent_id": "order_seller_agent", "evidence_ids": [], "partial_results": {}, "confidence": 0.0}

        if not claimed_order_id:
            result["partial_results"] = {"error": "missing_claimed_order_id"}
            return result

        order_key = str(claimed_order_id)
        items = order_items[order_items["order_id"].astype(str) == order_key] if not order_items.empty else pd.DataFrame()

        if is_llm_enabled():
            items_records = items.to_dict("records") if not items.empty else []
            user_prompt = ORDER_SELLER_AGENT_USER_TEMPLATE.format(
                case_id=case_id,
                order_id=order_key,
                items=json.dumps(items_records, ensure_ascii=False),
            )
            payload = self._call_llm(ORDER_SELLER_AGENT_SYSTEM_PROMPT, user_prompt)
            result["partial_results"] = payload.get("partial_results", {})
            result["evidence_ids"] = payload.get("evidence_ids", [])
            result["confidence"] = min(max(self._normalize_float(payload.get("confidence", 0.0)), 0.0), 1.0)
            return result

        item_ids: List[str] = []
        seller_ids: List[str] = []
        item_total = 0.0
        freight_total = 0.0

        if not items.empty:
            for _, r in items.iterrows():
                item_id = r.get("order_item_id")
                seller_id = r.get("seller_id")
                item_ids.append(f"{claimed_order_id}:{item_id}")
                if seller_id and seller_id not in seller_ids:
                    seller_ids.append(seller_id)
                item_total += float(r.get("price", 0.0))
                freight_total += float(r.get("freight_value", 0.0))

        # evidence
        if item_ids:
            result["evidence_ids"].append(f"order:{claimed_order_id}")
            for iid in item_ids[:5]:
                result["evidence_ids"].append(f"item:{iid}")
        for sid in seller_ids[:5]:
            result["evidence_ids"].append(f"seller:{sid}")

        result["partial_results"] = {
            "order_id": claimed_order_id,
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "item_total_brl": round(item_total, 2),
            "freight_total_brl": round(freight_total, 2),
        }
        result["confidence"] = 0.9 if items is not None and not items.empty else 0.2
        return result
