from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from agents.llm_agent import LLMAgent
from llm import is_llm_enabled
from prompts import POLICY_AGENT_SYSTEM_PROMPT, POLICY_AGENT_USER_TEMPLATE


class PolicyAgent(LLMAgent):
    """Apply EC_POLICY_V1 policy to order, payment, and delivery facts.

    Uses GPT-5.5 when USE_LLM=1 and OPENAI_API_KEY is set.
    """

    def decide(self, case_id: str, order_part: Dict[str, Any], payment_part: Dict[str, Any], delivery_part: Dict[str, Any]) -> Dict[str, Any]:
        item_total = Decimal(str(order_part.get("item_total_brl", 0)))
        freight_total = Decimal(str(order_part.get("freight_total_brl", 0)))
        payment_total = Decimal(str(payment_part.get("payment_total_brl", 0)))

        item_total = item_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        freight_total = freight_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        payment_total = payment_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        order_status = order_part.get("order_status")
        delivered_after = delivery_part.get("delivered_after_estimate")
        carrier_after = delivery_part.get("carrier_after_shipping_limit")
        reconciled = payment_part.get("partial_results", {}).get("reconciled") if isinstance(payment_part, dict) else False
        payment_rows = payment_part.get("partial_results", {}).get("payment_rows", []) if isinstance(payment_part, dict) else []

        if is_llm_enabled():
            user_prompt = POLICY_AGENT_USER_TEMPLATE.format(
                case_id=case_id,
                order_part=json.dumps(order_part, ensure_ascii=False),
                payment_part=json.dumps(payment_part, ensure_ascii=False),
                delivery_part=json.dumps(delivery_part, ensure_ascii=False),
            )
            payload = self._call_llm(POLICY_AGENT_SYSTEM_PROMPT, user_prompt)
            normalized = {
                "primary_issue": payload.get("primary_issue"),
                "case_status": payload.get("case_status"),
                "confidence": min(max(self._normalize_float(payload.get("confidence", 0.0)), 0.0), 1.0),
                "root_causes": payload.get("root_causes", []),
                "responsible_parties": payload.get("responsible_parties", []),
                "recommended_refund_brl": self._normalize_float(payload.get("recommended_refund_brl", 0.0)),
                "resolution_actions": payload.get("resolution_actions", []),
            }
            return normalized

        result = {
            "primary_issue": None,
            "case_status": None,
            "confidence": 0.0,
            "root_causes": [],
            "responsible_parties": [],
            "recommended_refund_brl": 0.0,
            "resolution_actions": [],
        }

        if order_status in ("canceled", "unavailable") and payment_total > Decimal("0.00"):
            issue = "canceled_order_paid" if order_status == "canceled" else "unavailable_order_paid"
            code = "ORDER_CANCELED_AFTER_PAYMENT" if order_status == "canceled" else "ORDER_UNAVAILABLE_AFTER_PAYMENT"
            result["primary_issue"] = issue
            result["case_status"] = "action_required"
            result["confidence"] = 0.98
            result["root_causes"].append({"cause_code": code, "rank": 1})
            result["responsible_parties"].append({"party_type": "platform", "party_id": "OLIST_PLATFORM"})
            result["recommended_refund_brl"] = float(payment_total)
            result["resolution_actions"].append("issue_full_refund")
            return result

        if delivered_after:
            if carrier_after:
                result["primary_issue"] = "late_delivery_seller"
                result["case_status"] = "action_required"
                result["confidence"] = 0.9
                result["root_causes"].append({"cause_code": "SELLER_HANDOFF_AFTER_LIMIT", "rank": 1})
                for seller_id in order_part.get("seller_ids", [])[:3]:
                    result["responsible_parties"].append({"party_type": "seller", "party_id": seller_id})
                result["recommended_refund_brl"] = float(freight_total)
                result["resolution_actions"].append("refund_freight")
                return result
            result["primary_issue"] = "late_delivery_logistics"
            result["case_status"] = "action_required"
            result["confidence"] = 0.9
            result["root_causes"].append({"cause_code": "CARRIER_DELIVERED_AFTER_ESTIMATE", "rank": 1})
            result["responsible_parties"].append({"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"})
            result["recommended_refund_brl"] = float(freight_total)
            result["resolution_actions"].append("refund_freight")
            return result

        if reconciled and len(payment_rows) >= 2:
            result["primary_issue"] = "valid_split_payment"
            result["case_status"] = "no_action"
            result["confidence"] = 0.9
            result["root_causes"].append({"cause_code": "MULTIPLE_PAYMENTS_RECONCILED", "rank": 1})
            result["resolution_actions"].append("explain_valid_split_payment")
            return result

        result["primary_issue"] = "unsupported_late_claim"
        result["case_status"] = "no_action"
        result["confidence"] = 0.6
        result["root_causes"].append({"cause_code": "DELIVERY_WITHIN_ESTIMATE", "rank": 1})
        result["resolution_actions"].append("reject_late_refund")
        return result
