import json
import os
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd

from agents.llm_agent import LLMAgent
from llm import is_llm_enabled
from prompts import PAYMENT_AGENT_SYSTEM_PROMPT, PAYMENT_AGENT_USER_TEMPLATE


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


class PaymentAgent(LLMAgent):
    """Payment Agent for K3-Day9-PRAI

    Uses GPT-5.5 when USE_LLM=1 and OPENAI_API_KEY is set.
    """

    def __init__(self, data_dir: str = None):
        if data_dir:
            self.data_dir = data_dir
        else:
            # default: repo root data folder
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.data_dir = os.path.join(base, "data")

    @staticmethod
    def _extract_claimed_order_id(case: Dict[str, Any]) -> str | None:
        if isinstance(case.get("customer_request"), dict):
            return case["customer_request"].get("claimed_order_id") or case.get("claimed_order_id")
        return case.get("claimed_order_id")

    def _load(self) -> Dict[str, pd.DataFrame]:
        def _read(fname: str):
            path = os.path.join(self.data_dir, fname)
            if os.path.exists(path):
                return pd.read_csv(path, dtype=str)
            return pd.DataFrame()

        return {
            "orders": _read("orders.csv"),
            "order_items": _read("order_items.csv"),
            "order_payments": _read("order_payments.csv"),
        }

    def run(self, case: Dict[str, Any]) -> Dict[str, Any]:
        case_id = case.get("case_id")
        claimed_order_id = self._extract_claimed_order_id(case)

        tables = self._load()
        order_items = tables["order_items"]
        order_payments = tables["order_payments"]

        result: Dict[str, Any] = {
            "case_id": case_id,
            "agent_id": "payment_agent",
            "evidence_ids": [],
            "partial_results": {},
            "confidence": 0.0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if not claimed_order_id:
            result["partial_results"] = {"error": "missing claimed_order_id"}
            result["confidence"] = 0.0
            return result

        order_key = str(claimed_order_id)
        items = order_items[order_items["order_id"].astype(str) == order_key] if not order_items.empty else pd.DataFrame()
        payments = order_payments[order_payments["order_id"].astype(str) == order_key] if not order_payments.empty else pd.DataFrame()

        if is_llm_enabled():
            items_records = items.to_dict("records") if not items.empty else []
            payments_records = payments.to_dict("records") if not payments.empty else []
            user_prompt = PAYMENT_AGENT_USER_TEMPLATE.format(
                case_id=case_id,
                order_id=order_key,
                items=json.dumps(items_records, ensure_ascii=False),
                payments=json.dumps(payments_records, ensure_ascii=False),
            )
            payload = self._call_llm(PAYMENT_AGENT_SYSTEM_PROMPT, user_prompt)
            result["partial_results"] = payload.get("partial_results", {})
            result["evidence_ids"] = payload.get("evidence_ids", [])
            result["confidence"] = min(max(self._normalize_float(payload.get("confidence", 0.0)), 0.0), 1.0)
            return result

        item_total = Decimal("0.00")
        freight_total = Decimal("0.00")
        payment_total = Decimal("0.00")

        if not items.empty:
            for _, r in items.iterrows():
                item_total += _to_decimal(r.get("price", 0))
                freight_total += _to_decimal(r.get("freight_value", 0))

        payment_rows: List[Dict[str, Any]] = []
        if not payments.empty:
            order_col = "payment_sequential" if "payment_sequential" in payments.columns else None
            if order_col:
                payments = payments.sort_values(order_col)
            payments = payments.reset_index(drop=True)
            for idx, r in payments.iterrows():
                seq = None
                if "payment_sequential" in r.index:
                    seq = r.get("payment_sequential")
                else:
                    seq = idx + 1
                val = _to_decimal(r.get("payment_value", 0))
                payment_total += val
                payment_rows.append({"seq": int(seq), "payment_value": float(val)})

        reconciliation_tolerance = Decimal("0.10")
        expected_total = (item_total + freight_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        diff = (payment_total - expected_total).copy_abs()
        reconciled = diff <= reconciliation_tolerance

        evidence_ids: List[str] = []
        if payment_rows:
            for p in payment_rows[:10]:
                evidence_ids.append(f"payment:{claimed_order_id}:{p['seq']}")

        partial = {
            "item_total_brl": float(item_total.quantize(Decimal("0.01"))),
            "freight_total_brl": float(freight_total.quantize(Decimal("0.01"))),
            "payment_total_brl": float(payment_total.quantize(Decimal("0.01"))),
            "payment_rows": payment_rows,
            "reconciled": reconciled,
            "difference_brl": float(diff.quantize(Decimal("0.01"))),
        }

        if payments.empty:
            confidence = 0.15
        elif reconciled:
            confidence = 0.95
        else:
            confidence = 0.6 if len(payment_rows) > 1 else 0.5

        result["evidence_ids"] = evidence_ids
        result["partial_results"] = partial
        result["confidence"] = float(Decimal(confidence).quantize(Decimal("0.01")))

        return result


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to input case JSON")
    parser.add_argument("--data-dir", default=None, help="Path to data directory containing Olist CSVs")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as input_file:
        case_data = json.load(input_file)

    agent = PaymentAgent(data_dir=args.data_dir)
    out = agent.run(case_data)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
