"""Run all dispute cases and save results to output folder."""

import argparse
import glob
import json
import os
from typing import List

from coordinator import process_case


def find_cases(input_dir: str, pattern: str = "*.json") -> List[str]:
    """Find all JSON case files in the input directory."""
    return sorted(glob.glob(os.path.join(input_dir, pattern)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run coordinator for all JSON cases"
    )

    parser.add_argument(
        "--input-dir",
        default="input",
        help="Folder containing input JSON files",
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Folder to save output JSON files",
    )

    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to data folder containing CSV files",
    )

    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    cases = find_cases(input_dir)

    if not cases:
        print(f"No JSON files found in {input_dir}")
        return

    processed = 0
    failed = 0

    for case_path in cases:
        filename = os.path.basename(case_path)
        print(f"Processing: {filename}")

        try:
            result = process_case(
                case_path,
                data_dir=args.data_dir,
            )

            output_path = os.path.join(output_dir, filename)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            processed += 1

        except Exception as e:
            failed += 1
            print(f"❌ Error processing {filename}")
            print(e)

    print("\n==============================")
    print("Finished")
    print(f"Processed : {processed}")
    print(f"Failed    : {failed}")
    print(f"Total     : {len(cases)}")
    print(f"Output    : {output_dir}")
    print("==============================")


if __name__ == "__main__":
    main()