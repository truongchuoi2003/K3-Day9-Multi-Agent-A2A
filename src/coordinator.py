import os
import json
from typing import Dict, Any

from agents.verifier import VerifierAgent
from agents.order_seller import OrderSellerAgent
from agents.payment import PaymentAgent
from agents.delivery import DeliveryAgent
from agents.policy import PolicyAgent


def process_case(case_path: str, data_dir: str = None) -> Dict[str, Any]:
    with open(case_path, "r", encoding="utf-8") as f:
        case = json.load(f)

    verifier = VerifierAgent(data_dir=data_dir)
    vres = verifier.run(case)
    if not vres.get("verified"):
        return {"case_id": case.get("case_id"), "status": "rejected", "reason": vres.get("reason")}

    order_agent = OrderSellerAgent(data_dir=data_dir)
    payment_agent = PaymentAgent(data_dir=data_dir)
    delivery_agent = DeliveryAgent(data_dir=data_dir)
    policy_agent = PolicyAgent()

    order_res = order_agent.run(case)
    payment_res = payment_agent.run(case)
    delivery_res = delivery_agent.run(case)

    decision = policy_agent.decide(case.get("case_id"), order_res.get("partial_results", {}), payment_res, delivery_res.get("partial_results", {}))

    output = {
        "case_id": case.get("case_id"),
        "assessment": {
            "primary_issue": decision.get("primary_issue"),
            "case_status": decision.get("case_status"),
            "confidence": decision.get("confidence"),
        },
        "affected_entities": {
            "order_ids": [order_res.get("partial_results", {}).get("order_id")] if order_res.get("partial_results", {}).get("order_id") else [],
            "item_ids": order_res.get("partial_results", {}).get("item_ids", []),
            "seller_ids": order_res.get("partial_results", {}).get("seller_ids", []),
            "payment_ids": payment_res.get("evidence_ids", []),
        },
        "root_cause_analysis": {
            "ranked_causes": decision.get("root_causes", []),
            "responsible_parties": decision.get("responsible_parties", []),
        },
        "evidence_ids": list(set(order_res.get("evidence_ids", []) + payment_res.get("evidence_ids", []) + delivery_res.get("evidence_ids", []) + [f"policy:{c['cause_code']}" for c in decision.get("root_causes", []) if c.get('cause_code')])),
        "financial_resolution": {
            "currency": "BRL",
            "item_total_brl": order_res.get("partial_results", {}).get("item_total_brl", 0.0),
            "freight_total_brl": order_res.get("partial_results", {}).get("freight_total_brl", 0.0),
            "payment_total_brl": payment_res.get("partial_results", {}).get("payment_total_brl", 0.0),
            "recommended_refund_brl": decision.get("recommended_refund_brl", 0.0),
        },
        "resolution_actions": decision.get("resolution_actions", []),
    }

    # write output file next to input
    out_dir = os.path.join(os.path.dirname(case_path), os.pardir, "output")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(case_path))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    p = argparse.ArgumentParser()

    p.add_argument(
        "input_dir",
        help="Path to folder containing case JSON files"
    )

    p.add_argument(
        "--data-dir",
        default=None,
        help="Path to data folder containing CSVs"
    )

    args = p.parse_args()

    input_dir = Path(args.input_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Folder not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"{input_dir} is not a folder")

    json_files = sorted(input_dir.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        exit(0)

    for case_file in json_files:
        print(f"\nProcessing: {case_file.name}")

        out = process_case(
            str(case_file),
            data_dir=args.data_dir
        )

        print(json.dumps(out, ensure_ascii=False, indent=2))
