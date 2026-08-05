"""Run the multi-agent dispute-resolution pipeline for input cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .agents.coordinator import CoordinatorAgent
from .agents.delivery import DeliveryAgent
from .agents.order_seller import OrderSellerAgent
from .agents.payment import PaymentAgent
from .agents.policy import PolicyAgent
from .agents.verifier import VerifierAgent
from .data_loader import DataLoader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Olist dispute cases.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--case-id", help="Run one case, for example EC_001.")
    selection.add_argument("--limit", type=int, help="Run the first N cases in filename order.")
    parser.add_argument("--input-dir", default="input")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--trace-path", default="logging/trace.jsonl")
    parser.add_argument(
        "--show-handoffs", action="store_true", help="Print full agent handoffs for each case."
    )
    return parser


def select_case_paths(input_dir: Path, case_id: str | None, limit: int | None) -> list[Path]:
    paths = sorted(input_dir.glob("EC_*.json"))
    if case_id:
        expected = input_dir / f"{case_id}.json"
        if expected not in paths:
            raise FileNotFoundError(f"Input case not found: {expected}")
        return [expected]
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be at least 1")
        return paths[:limit]
    return paths


def run(args: argparse.Namespace) -> int:
    paths = select_case_paths(Path(args.input_dir), args.case_id, args.limit)
    if not paths:
        raise FileNotFoundError(f"No EC_*.json files found in {args.input_dir}")

    loader = DataLoader(args.data_dir)
    coordinator = CoordinatorAgent(
        order_seller_agent=OrderSellerAgent(loader),
        payment_agent=PaymentAgent(loader),
        delivery_agent=DeliveryAgent(),
        policy_agent=PolicyAgent(),
        verifier_agent=VerifierAgent(loader),
        output_dir=args.output_dir,
    )

    trace_path = Path(args.trace_path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    failures = 0
    # "w" intentionally replaces the previous run: the submission requires
    # only the newest trace rather than an accumulated audit history.
    with trace_path.open("w", encoding="utf-8") as trace_file:
        for index, case_path in enumerate(paths, start=1):
            case = json.loads(case_path.read_text(encoding="utf-8"))
            case_id = case.get("case_id", case_path.stem)
            try:
                output, handoffs = coordinator.resolve_case_with_handoffs(case)
                trace_record = {
                    "case_id": case_id,
                    "claimed_order_id": case["customer_request"]["claimed_order_id"],
                    "agent_handoffs": handoffs,
                    "primary_issue": output["assessment"]["primary_issue"],
                    "verification": "passed",
                }
                trace_file.write(json.dumps(trace_record, ensure_ascii=False, default=str) + "\n")
                print(f"[{index}/{len(paths)}] {case_id}: {output['assessment']['primary_issue']}")
                if args.show_handoffs:
                    print(json.dumps(trace_record, ensure_ascii=False, indent=2, default=str))
            except Exception as error:  # Keep a trace record even when a case fails.
                failures += 1
                trace_file.write(
                    json.dumps(
                        {"case_id": case_id, "verification": "failed", "error": str(error)},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                print(f"[{index}/{len(paths)}] {case_id}: FAILED — {error}")

    if failures:
        print(f"Run failed: {failures}/{len(paths)} case(s) were rejected. See {trace_path}.")
        return 1
    print(f"Run passed: {len(paths)} case(s). Latest trace: {trace_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
