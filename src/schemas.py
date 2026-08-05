"""Contracts for agent handoffs and the required submission JSON schema."""

from __future__ import annotations

from typing import Any, TypedDict


class ItemFact(TypedDict):
    order_item_id: int
    item_id: str
    product_id: str
    seller_id: str
    shipping_limit_date: Any
    price: float
    freight_value: float


class OrderSellerResult(TypedDict):
    order_id: str
    order_status: str
    carrier_date: Any
    customer_delivery_date: Any
    estimated_delivery_date: Any
    items: list[ItemFact]
    seller_ids: list[str]


class PaymentResult(TypedDict):
    payment_ids: list[str]
    payment_evidence_ids: list[str]
    payment_sequentials: list[int]
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    payment_matches: bool
    is_split_payment: bool


class DeliveryResult(TypedDict):
    is_late: bool
    delivery_within_estimate: bool
    seller_handoff_late: bool
    seller_handoff_within_limit: bool
    violating_seller_ids: list[str]
    violating_item_ids: list[str]


class ResponsibleParty(TypedDict):
    party_type: str
    party_id: str


class PolicyResult(TypedDict):
    primary_issue: str
    case_status: str
    confidence: float
    root_cause_code: str
    responsible_parties: list[ResponsibleParty]
    recommended_refund_brl: float
    resolution_actions: list[str]


class Assessment(TypedDict):
    primary_issue: str
    case_status: str
    confidence: float


class AffectedEntities(TypedDict):
    order_ids: list[str]
    item_ids: list[str]
    seller_ids: list[str]
    payment_ids: list[str]


class RankedCause(TypedDict):
    cause_code: str
    rank: int


class RootCauseAnalysis(TypedDict):
    ranked_causes: list[RankedCause]
    responsible_parties: list[ResponsibleParty]


class FinancialResolution(TypedDict):
    currency: str
    item_total_brl: float
    freight_total_brl: float
    payment_total_brl: float
    recommended_refund_brl: float


class CaseOutput(TypedDict):
    case_id: str
    assessment: Assessment
    affected_entities: AffectedEntities
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: list[str]
    financial_resolution: FinancialResolution
    resolution_actions: list[str]
