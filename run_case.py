#!/usr/bin/env python3
"""File a PayProof Court case on GenLayer Bradbury and print the verdict.

Runnable interface around scripts/run_case.js (genlayer-js):

    python3 run_case.py --case-data demo/case-data.json
    python3 run_case.py --case-data demo/case-data.json --contract 0x...

The contract address defaults to deployment.json (written by
scripts/deploy.js). The script files the case, waits for consensus to
finalize, reads the stored case back from the contract, prints the
verdict, and optionally saves the full result JSON.

Prerequisites: node, `npm install` in this repo, and a funded farming
EVM wallet on Bradbury (see README.md). The signing key is obtained
in-process by scripts/run_case.js and is never printed or stored.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--case-data",
        default=os.path.join(HERE, "demo", "case-data.json"),
        help="Path to the case JSON (default: demo/case-data.json)",
    )
    ap.add_argument(
        "--contract",
        default=None,
        help="PayProof Court contract address (default: deployment.json)",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Optional path to save the full result JSON",
    )
    args = ap.parse_args()

    contract = args.contract
    if not contract:
        dep_path = os.path.join(HERE, "deployment.json")
        if os.path.exists(dep_path):
            with open(dep_path) as f:
                contract = json.load(f)["contract_address"]
    if not contract:
        print(
            "ERROR: no contract address. Deploy first "
            "(node scripts/deploy.js) or pass --contract.",
            file=sys.stderr,
        )
        return 2

    proc = subprocess.run(
        [
            "node",
            os.path.join(HERE, "scripts", "run_case.js"),
            os.path.abspath(args.case_data),
            contract,
        ],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print("ERROR: case filing failed, see messages above.", file=sys.stderr)
        return proc.returncode

    result = json.loads(proc.stdout)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=1)

    stored = result["case"]
    print(f"Case filed: {result['case_id']} (tx {result['case_tx_hash']})")
    print(f"Receipt status: {result['receipt_status']}")
    print(
        "Payment facts: from={payment_from} to={payment_to} "
        "value={payment_value} status={payment_status} "
        "timestamp={payment_timestamp}".format(**stored)
    )
    print(f"Verdict: {stored['verdict']} ({stored['reason_code']})")
    print(f"Reasoning: {stored['reasoning']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
