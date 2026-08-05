"""Orchestrate specialist agents and write verified case outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from ..evidence import EvidenceBuilder
from ..schemas import CaseOutput, DeliveryResult, OrderSellerResult, PaymentResult, PolicyResult
from .delivery import DeliveryAgent
from .order_seller import OrderSellerAgent
from .payment import PaymentAgent
from .policy import PolicyAgent


class OutputVerifier(Protocol):
    """Minimum interface required from the independent Verifier Agent."""

    def verify(
        self,
        output: CaseOutput,
        *,
        expected_case_id: str | None = None,
        expected_order_id: str | None = None,
    ) -> list[str]:
        """Return validation errors; return an empty list only when output is valid."""


class VerificationError(RuntimeError):
    """Raised when the Verifier Agent rejects a draft output."""


class CoordinatorAgent:
    """Coordinate specialist handoffs without duplicating their business logic."""

    def __init__(
        self,
        order_seller_agent: OrderSellerAgent,
        payment_agent: PaymentAgent,
        delivery_agent: DeliveryAgent,
        policy_agent: PolicyAgent,
        verifier_agent: OutputVerifier,
        output_dir: str | Path = "output",
    ) -> None:
        self.order_seller_agent = order_seller_agent
        self.payment_agent = payment_agent
        self.delivery_agent = delivery_agent
        self.policy_agent = policy_agent
        self.verifier_agent = verifier_agent
        self.output_dir = Path(output_dir)
        self.evidence_builder = EvidenceBuilder()

    def resolve_case(self, case: dict[str, Any], *, write_output: bool = True) -> CaseOutput:
        """Resolve one input case and write it only after verification succeeds."""
        output, _ = self.resolve_case_with_handoffs(case, write_output=write_output)
        return output

    def resolve_case_with_handoffs(
        self, case: dict[str, Any], *, write_output: bool = True
    ) -> tuple[CaseOutput, dict[str, Any]]:
        """Resolve a case and return the specialist handoffs for audit tracing."""
        case_id = self._required_string(case, "case_id")
        order_id = self._claimed_order_id(case)

        order_result = self.order_seller_agent.analyze(order_id)
        payment_result = self.payment_agent.analyze(order_id, order_result["items"])
        delivery_result = self.delivery_agent.analyze(order_result)
        policy_result = self.policy_agent.decide(order_result, payment_result, delivery_result)

        draft = self._build_output(
            case_id=case_id,
            order_result=order_result,
            payment_result=payment_result,
            delivery_result=delivery_result,
            policy_result=policy_result,
        )
        errors = self.verifier_agent.verify(
            draft, expected_case_id=case_id, expected_order_id=order_id
        )
        if errors:
            raise VerificationError(f"{case_id} failed verification: {'; '.join(errors)}")

        if write_output:
            self._write_output(draft)
        return draft, {
            "order_seller": order_result,
            "payment": payment_result,
            "delivery": delivery_result,
            "policy": policy_result,
            "verifier": {"status": "passed", "errors": []},
        }

    def _build_output(
        self,
        *,
        case_id: str,
        order_result: OrderSellerResult,
        payment_result: PaymentResult,
        delivery_result: DeliveryResult,
        policy_result: PolicyResult,
    ) -> CaseOutput:
        item_ids = self._limit(order_result["items"], 5, key="item_id")
        seller_ids = self._limit_values(order_result["seller_ids"], 5)
        payment_ids = self._limit_values(payment_result["payment_ids"], 5)

        return {
            "case_id": case_id,
            "assessment": {
                "primary_issue": policy_result["primary_issue"],
                "case_status": policy_result["case_status"],
                "confidence": policy_result["confidence"],
            },
            "affected_entities": {
                "order_ids": [order_result["order_id"]],
                "item_ids": item_ids,
                "seller_ids": seller_ids,
                "payment_ids": payment_ids,
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": policy_result["root_cause_code"], "rank": 1}],
                "responsible_parties": policy_result["responsible_parties"][:3],
            },
            "evidence_ids": self.evidence_builder.build(
                order_result, payment_result, delivery_result, policy_result
            ),
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": payment_result["item_total_brl"],
                "freight_total_brl": payment_result["freight_total_brl"],
                "payment_total_brl": payment_result["payment_total_brl"],
                "recommended_refund_brl": policy_result["recommended_refund_brl"],
            },
            "resolution_actions": policy_result["resolution_actions"][:5],
        }

    def _write_output(self, output: CaseOutput) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{output['case_id']}.json"
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)
            file.write("\n")

    @staticmethod
    def _claimed_order_id(case: dict[str, Any]) -> str:
        request = case.get("customer_request")
        if not isinstance(request, dict):
            raise ValueError("Input case is missing object customer_request")
        order_id = request.get("claimed_order_id")
        if not isinstance(order_id, str) or not order_id:
            raise ValueError("Input case is missing string customer_request.claimed_order_id")
        return order_id

    @staticmethod
    def _required_string(source: dict[str, Any], key: str) -> str:
        value = source.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Input case is missing string {key}")
        return value

    @staticmethod
    def _limit(items: list[dict[str, Any]], maximum: int, *, key: str) -> list[str]:
        return [str(item[key]) for item in items[:maximum]]

    @staticmethod
    def _limit_values(values: list[str], maximum: int) -> list[str]:
        return values[:maximum]
