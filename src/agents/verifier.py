"""Validate final output against source data and the submission schema."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from ..data_loader import DataLoader
from ..schemas import CaseOutput


class VerifierAgent:
    """Reject invalid IDs, unsupported evidence, inconsistent money, or schema errors."""

    _CAUSES = {
        "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
        "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
        "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
        "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
    }
    _ACTIONS = {
        "canceled_order_paid": "issue_full_refund",
        "unavailable_order_paid": "issue_full_refund",
        "late_delivery_seller": "refund_freight",
        "late_delivery_logistics": "refund_freight",
        "valid_split_payment": "explain_valid_split_payment",
        "unsupported_late_claim": "reject_late_refund",
    }
    _LIMITS = {
        "order_ids": 5,
        "item_ids": 5,
        "seller_ids": 5,
        "payment_ids": 5,
        "evidence_ids": 10,
        "ranked_causes": 3,
        "responsible_parties": 3,
        "resolution_actions": 5,
    }

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader = data_loader

    def verify(
        self,
        output: CaseOutput,
        *,
        expected_case_id: str | None = None,
        expected_order_id: str | None = None,
    ) -> list[str]:
        """Return every detectable issue; an empty list approves output writing."""
        errors: list[str] = []
        if not isinstance(output, Mapping):
            return ["Output must be a JSON object"]

        self._check_case_id(output, expected_case_id, errors)
        assessment = self._object(output, "assessment", errors)
        entities = self._object(output, "affected_entities", errors)
        analysis = self._object(output, "root_cause_analysis", errors)
        financial = self._object(output, "financial_resolution", errors)
        evidence_ids = self._string_list(output, "evidence_ids", errors)
        actions = self._string_list(output, "resolution_actions", errors)

        self._check_limits(entities, analysis, evidence_ids, actions, errors)
        self._check_confidence(assessment, errors)
        order_id = self._check_entities(entities, expected_order_id, errors)
        self._check_evidence(evidence_ids, order_id, errors)
        self._check_financials(financial, order_id, errors)
        self._check_policy(assessment, analysis, financial, evidence_ids, actions, order_id, errors)
        return errors

    def _check_case_id(
        self, output: Mapping[str, Any], expected_case_id: str | None, errors: list[str]
    ) -> None:
        case_id = output.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("case_id must be a non-empty string")
        elif expected_case_id is not None and case_id != expected_case_id:
            errors.append(f"case_id {case_id} does not match input {expected_case_id}")

    def _check_limits(
        self,
        entities: Mapping[str, Any],
        analysis: Mapping[str, Any],
        evidence_ids: list[str],
        actions: list[str],
        errors: list[str],
    ) -> None:
        for field in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
            values = self._string_list(entities, field, errors)
            if len(values) > self._LIMITS[field]:
                errors.append(f"{field} exceeds {self._LIMITS[field]} IDs")
        if len(evidence_ids) > self._LIMITS["evidence_ids"]:
            errors.append("evidence_ids exceeds 10 IDs")
        if len(actions) > self._LIMITS["resolution_actions"]:
            errors.append("resolution_actions exceeds 5 actions")
        for field in ("ranked_causes", "responsible_parties"):
            values = analysis.get(field)
            if not isinstance(values, list):
                errors.append(f"root_cause_analysis.{field} must be a list")
            elif len(values) > self._LIMITS[field]:
                errors.append(f"{field} exceeds {self._LIMITS[field]} entries")

    def _check_confidence(self, assessment: Mapping[str, Any], errors: list[str]) -> None:
        confidence = assessment.get("confidence")
        if not self._is_money_number(confidence) or not 0 <= float(confidence) <= 1:
            errors.append("assessment.confidence must be a number in [0, 1]")

    def _check_entities(
        self,
        entities: Mapping[str, Any],
        expected_order_id: str | None,
        errors: list[str],
    ) -> str | None:
        order_ids = self._string_list(entities, "order_ids", errors)
        if len(order_ids) != 1:
            errors.append("affected_entities.order_ids must contain exactly one order ID")
            return None
        order_id = order_ids[0]
        try:
            self.data_loader.get_order(order_id)
        except KeyError:
            errors.append(f"Unknown order ID: {order_id}")
            return None
        if expected_order_id is not None and order_id != expected_order_id:
            errors.append(f"Output order ID {order_id} does not match input {expected_order_id}")

        item_rows = self.data_loader.get_order_items(order_id)
        payment_rows = self.data_loader.get_order_payments(order_id)
        source_seller_ids = set(item_rows["seller_id"].astype(str))
        valid_item_ids = {
            f"{order_id}:{int(row.order_item_id)}" for row in item_rows.itertuples(index=False)
        }
        valid_payment_ids = {
            f"{order_id}:{int(row.payment_sequential)}"
            for row in payment_rows.itertuples(index=False)
        }

        for item_id in self._string_list(entities, "item_ids", errors):
            if item_id not in valid_item_ids:
                errors.append(f"Invalid or unrelated item ID: {item_id}")
        for payment_id in self._string_list(entities, "payment_ids", errors):
            if payment_id not in valid_payment_ids:
                errors.append(f"Invalid or unrelated payment ID: {payment_id}")
        for seller_id in self._string_list(entities, "seller_ids", errors):
            if not self.data_loader.seller_exists(seller_id):
                errors.append(f"Unknown seller ID: {seller_id}")
            elif seller_id not in source_seller_ids:
                errors.append(f"Seller ID is unrelated to order {order_id}: {seller_id}")
        return order_id

    def _check_evidence(self, evidence_ids: Sequence[str], order_id: str | None, errors: list[str]) -> None:
        for evidence_id in evidence_ids:
            if ":" not in evidence_id:
                errors.append(f"Invalid evidence format: {evidence_id}")
                continue
            kind, value = evidence_id.split(":", 1)
            if kind == "order":
                self._validate_order_evidence(value, order_id, errors)
            elif kind == "item":
                self._validate_item_evidence(value, order_id, errors)
            elif kind == "payment":
                self._validate_payment_evidence(value, order_id, errors)
            elif kind == "seller":
                if not self.data_loader.seller_exists(value):
                    errors.append(f"Evidence has unknown seller: {evidence_id}")
            elif kind == "policy":
                if value not in self._CAUSES.values():
                    errors.append(f"Evidence has unsupported policy cause: {evidence_id}")
            else:
                errors.append(f"Evidence kind is not allowed: {evidence_id}")

    def _check_financials(
        self, financial: Mapping[str, Any], order_id: str | None, errors: list[str]
    ) -> None:
        if financial.get("currency") != "BRL":
            errors.append("financial_resolution.currency must be BRL")
        amount_fields = (
            "item_total_brl",
            "freight_total_brl",
            "payment_total_brl",
            "recommended_refund_brl",
        )
        for field in amount_fields:
            value = financial.get(field)
            if not self._is_money_number(value):
                errors.append(f"financial_resolution.{field} must be a finite number")
            elif abs(float(value) - round(float(value), 2)) > 1e-9:
                errors.append(f"financial_resolution.{field} must be rounded to 2 decimals")

        if order_id is None:
            return
        item_rows = self.data_loader.get_order_items(order_id)
        payment_rows = self.data_loader.get_order_payments(order_id)
        expected = {
            "item_total_brl": round(float(item_rows["price"].sum()), 2),
            "freight_total_brl": round(float(item_rows["freight_value"].sum()), 2),
            "payment_total_brl": round(float(payment_rows["payment_value"].sum()), 2),
        }
        for field, expected_value in expected.items():
            actual = financial.get(field)
            if self._is_money_number(actual) and abs(float(actual) - expected_value) > 0.001:
                errors.append(f"financial_resolution.{field} does not match source data")

    def _check_policy(
        self,
        assessment: Mapping[str, Any],
        analysis: Mapping[str, Any],
        financial: Mapping[str, Any],
        evidence_ids: Sequence[str],
        actions: Sequence[str],
        order_id: str | None,
        errors: list[str],
    ) -> None:
        issue = assessment.get("primary_issue")
        if issue not in self._CAUSES:
            errors.append(f"Unsupported primary_issue: {issue}")
            return
        expected_cause = self._CAUSES[issue]
        policy_evidence = [evidence for evidence in evidence_ids if evidence.startswith("policy:")]
        if policy_evidence != [f"policy:{expected_cause}"]:
            errors.append(f"evidence_ids must contain only policy:{expected_cause} as policy evidence")
        causes = analysis.get("ranked_causes")
        if not isinstance(causes, list) or not causes:
            errors.append("root_cause_analysis.ranked_causes must contain the primary cause")
        elif causes[0] != {"cause_code": expected_cause, "rank": 1}:
            errors.append(f"Primary root cause must be {expected_cause} at rank 1")

        expected_action = self._ACTIONS[issue]
        if list(actions) != [expected_action]:
            errors.append(f"resolution_actions must be [{expected_action}]")

        refund = financial.get("recommended_refund_brl")
        if self._is_money_number(refund):
            if issue in {"canceled_order_paid", "unavailable_order_paid"}:
                expected_refund = financial.get("payment_total_brl")
            elif issue in {"late_delivery_seller", "late_delivery_logistics"}:
                expected_refund = financial.get("freight_total_brl")
            else:
                expected_refund = 0.0
            if self._is_money_number(expected_refund) and abs(float(refund) - float(expected_refund)) > 0.001:
                errors.append("recommended_refund_brl does not match EC_POLICY_V1")
            expected_status = "action_required" if float(refund) > 0 else "no_action"
            if assessment.get("case_status") != expected_status:
                errors.append("assessment.case_status does not match recommended_refund_brl")

        parties = analysis.get("responsible_parties")
        if not isinstance(parties, list):
            return
        self._check_responsible_parties(issue, parties, order_id, errors)

    def _check_responsible_parties(
        self, issue: str, parties: list[Any], order_id: str | None, errors: list[str]
    ) -> None:
        if issue in {"valid_split_payment", "unsupported_late_claim"}:
            if parties:
                errors.append(f"{issue} must not have responsible_parties")
            return
        if issue in {"canceled_order_paid", "unavailable_order_paid"}:
            if parties != [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]:
                errors.append(f"{issue} must assign OLIST_PLATFORM as platform")
            return
        if issue == "late_delivery_logistics":
            expected = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            if parties != expected:
                errors.append("late_delivery_logistics must assign LOGISTICS_PROVIDER")
            return
        if issue != "late_delivery_seller":
            return
        if not parties or order_id is None:
            errors.append("late_delivery_seller must include a violating seller")
            return
        order = self.data_loader.get_order(order_id)
        carrier_date = order["order_delivered_carrier_date"]
        items = self.data_loader.get_order_items(order_id)
        violating_sellers = set()
        if not pd.isna(carrier_date):
            for row in items.itertuples(index=False):
                limit = row.shipping_limit_date
                if not pd.isna(limit) and carrier_date > limit:
                    violating_sellers.add(str(row.seller_id))
        for party in parties:
            if not isinstance(party, Mapping):
                errors.append("responsible party must be an object")
            elif party.get("party_type") != "seller" or party.get("party_id") not in violating_sellers:
                errors.append("late_delivery_seller party must be a seller with a violating seller ID")

    def _validate_order_evidence(self, value: str, order_id: str | None, errors: list[str]) -> None:
        try:
            self.data_loader.get_order(value)
        except KeyError:
            errors.append(f"Evidence has unknown order: order:{value}")
        if order_id is not None and value != order_id:
            errors.append(f"Evidence order is unrelated to case: order:{value}")

    def _validate_item_evidence(self, value: str, order_id: str | None, errors: list[str]) -> None:
        parts = value.rsplit(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            errors.append(f"Invalid item evidence format: item:{value}")
            return
        evidence_order, sequence = parts[0], int(parts[1])
        rows = self.data_loader.get_order_items(evidence_order)
        if not ((rows["order_item_id"] == sequence).any()):
            errors.append(f"Evidence has unknown item: item:{value}")
        if order_id is not None and evidence_order != order_id:
            errors.append(f"Evidence item is unrelated to case: item:{value}")

    def _validate_payment_evidence(self, value: str, order_id: str | None, errors: list[str]) -> None:
        parts = value.rsplit(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            errors.append(f"Invalid payment evidence format: payment:{value}")
            return
        evidence_order, sequence = parts[0], int(parts[1])
        rows = self.data_loader.get_order_payments(evidence_order)
        if not ((rows["payment_sequential"] == sequence).any()):
            errors.append(f"Evidence has unknown payment: payment:{value}")
        if order_id is not None and evidence_order != order_id:
            errors.append(f"Evidence payment is unrelated to case: payment:{value}")

    @staticmethod
    def _object(source: Mapping[str, Any], key: str, errors: list[str]) -> Mapping[str, Any]:
        value = source.get(key)
        if not isinstance(value, Mapping):
            errors.append(f"{key} must be an object")
            return {}
        return value

    @staticmethod
    def _string_list(source: Mapping[str, Any], key: str, errors: list[str]) -> list[str]:
        value = source.get(key)
        if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
            errors.append(f"{key} must be a list of strings")
            return []
        return value

    @staticmethod
    def _is_money_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
