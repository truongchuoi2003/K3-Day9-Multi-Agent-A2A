# Multi-Agent E-commerce Dispute Resolution Architecture

## Overview

The system resolves one input case at a time using the claimed Olist order ID.
It uses `gpt-4o-mini` for a structured Coordinator audit handoff and
deterministic Python rules for `EC_POLICY_V1`. The model never changes policy
decisions, money, entities, or evidence; these remain attributable to CSV
source records and are independently checked by the Verifier.

```text
Input case (EC_xxx.json)
        |
        v
Coordinator Agent
   |----> Order & Seller Agent ----> order and item facts
   |----> Payment Agent -----------> reconciled payment facts
   |----> Delivery Agent ----------> delivery and handoff timing facts
   |----> Policy Agent ------------> EC_POLICY_V1 decision
   |----> GPT-4o-mini audit -------> structured trace-only handoff
   |----> Verifier Agent ----------> approve or reject draft output
        |
        +-- approved --> output/EC_xxx.json
        +-- rejected --> no output write; failure is recorded in trace
```

## Agent responsibilities and data access

| Agent | Responsibility | Direct data access | Handoff output |
| --- | --- | --- | --- |
| Coordinator Agent | Extract `claimed_order_id`, invoke agents, request a GPT-4o-mini audit of deterministic facts, assemble required JSON, write only approved output. | Input case JSON; specialist handoffs; no direct policy calculation. | Draft `CaseOutput`, GPT-4o-mini audit trace record. |
| Order & Seller Agent | Retrieve order status, timestamps, items, sellers, and shipping limits. | `orders`, `order_items`, `sellers`. | `OrderSellerResult`: order status, carrier/customer/estimate dates, item facts, seller IDs. |
| Payment Agent | Reconcile item and freight totals with payment rows. | `order_payments`; item facts received from Order & Seller Agent. | `PaymentResult`: payment IDs/evidence, item total, freight total, payment total, reconciliation flags. |
| Delivery Agent | Determine late delivery and seller handoff breaches per item. | No direct CSV access; receives normalized order and item facts. | `DeliveryResult`: late flags, violating item IDs, violating seller IDs. |
| Policy Agent | Apply `EC_POLICY_V1` in README priority order. | No direct CSV access; receives specialist handoffs. | `PolicyResult`: issue, cause, responsible party, refund, action, status, confidence. |
| Verifier Agent | Independently validate schema, source IDs, evidence, money, policy consistency, and limits. | `orders`, `order_items`, `order_payments`, `sellers`. | List of validation errors; an empty list is approval. |

Supporting datasets (`customers`, `order_reviews`, `products`, `geolocation`,
and category translation) remain available through `DataLoader` but do not
affect `EC_POLICY_V1`, because the policy has no rule based on them.

## Handoff contract

```text
Order & Seller Agent
  -> OrderSellerResult(order status, dates, items, seller IDs)

OrderSellerResult
  -> Payment Agent -> PaymentResult(totals, payment IDs, payment_matches, split flag)
  -> Delivery Agent -> DeliveryResult(late status, handoff status, violating sellers)

OrderSellerResult + PaymentResult + DeliveryResult
  -> Policy Agent -> PolicyResult(issue, root cause, parties, refund, actions)

All deterministic results
  -> Coordinator -> draft CaseOutput
  -> GPT-4o-mini -> trace-only structured audit
  -> Verifier Agent -> [] or validation errors
```

The Coordinator creates evidence only from source-grounded IDs:
`order:`, `item:`, `payment:`, `seller:`, and `policy:`. It never creates
tracking, refund-ledger, or customer evidence because those records do not
exist in the supplied dataset.

## Verification checkpoint and output safety

The Verifier is a mandatory checkpoint. The Coordinator passes the input
`case_id` and `claimed_order_id` with the draft output to `VerifierAgent`.

- If `verify(...)` returns `[]`, the Coordinator writes `output/EC_xxx.json`.
- If it returns one or more errors, the Coordinator raises `VerificationError`
  and does not write that case's output file.

`src/main.py` writes `logging/trace.jsonl` with mode `"w"` for every run, so
the file contains only the newest run's 50-case trace rather than appended
historical runs.
