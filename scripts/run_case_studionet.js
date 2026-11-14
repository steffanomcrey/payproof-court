// File a PayProof Court case on GenLayer StudioNet and print the ruling.
//
// Usage:
//   node scripts/run_case.js <case-data.json> <contract-address>
//
// The case JSON must contain: deal_terms, buyer, seller,
// expected_amount_wei, payment_tx_hash, delivery_evidence_url.
// Signing uses the farming EVM wallet only; the key is obtained in-process
// (see scripts/get_key.py) and is never printed or written to disk.
// Output: one JSON object on stdout with the GenLayer transaction hash and
// the stored case read back from the contract.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const here = path.dirname(fileURLToPath(import.meta.url));

function getPrivateKey() {
  if (process.env.GENLAYER_PRIVATE_KEY) {
    return process.env.GENLAYER_PRIVATE_KEY;
  }
  const out = execFileSync("python3", [path.join(here, "get_key.py")], {
    encoding: "utf8",
  });
  return out.trim();
}

async function main() {
  const casePath = process.argv[2];
  const contractAddress = process.argv[3];
  if (!casePath || !contractAddress) {
    console.error(
      "Usage: node scripts/run_case.js <case-data.json> <contract-address>"
    );
    process.exit(2);
  }
  const c = JSON.parse(readFileSync(casePath, "utf8"));

  const account = createAccount(getPrivateKey());
  const client = createClient({ chain: studionet, account });

  const txHash = await client.writeContract({
    address: contractAddress,
    functionName: "file_case",
    args: [
      c.deal_terms,
      c.buyer,
      c.seller,
      String(c.expected_amount_wei),
      c.payment_tx_hash,
      c.delivery_evidence_url,
    ],
    value: 0n,
  });
  console.error("Case tx hash:", txHash);

  const receipt = await client.waitForTransactionReceipt({
    hash: txHash,
    status: TransactionStatus.FINALIZED,
    interval: 5000,
    retries: 360,
  });
  console.error("Receipt status:", receipt.statusName || receipt.status);

  const count = await client.readContract({
    address: contractAddress,
    functionName: "get_case_count",
    args: [],
  });
  const caseId = "case-" + String(count);
  const stored = await client.readContract({
    address: contractAddress,
    functionName: "get_case",
    args: [caseId],
  });

  console.log(
    JSON.stringify(
      {
        contract_address: contractAddress,
        case_tx_hash: txHash,
        receipt_status: receipt.statusName || String(receipt.status),
        case_id: caseId,
        case: stored,
      },
      null,
      1
    )
  );
}

main().catch((e) => {
  console.error("RUN CASE FAILED:", e && e.message ? e.message : e);
  process.exit(1);
});
