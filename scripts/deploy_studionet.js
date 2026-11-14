// Deploy PayProof Court to GenLayer StudioNet with genlayer-js.
//
// Signing identity: the farming EVM wallet only. The private key is never
// stored in this repo and never printed. It is obtained in-process from
// scripts/get_key.py (which unlocks the local airdrop runner vault), or
// from the GENLAYER_PRIVATE_KEY environment variable when set.
//
// Usage:
//   npm install
//   node scripts/deploy.js
// Writes deployment.json with the contract address, deploy tx hash, and
// explorer URL on success.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");

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
  const account = createAccount(getPrivateKey());
  console.log("Deployer (farming EVM):", account.address);
  const client = createClient({ chain: studionet, account });

  const balance = await client.getBalance({ address: account.address });
  console.log("StudioNet balance (wei):", balance.toString());
  if (balance === 0n) {
    console.error(
      "ERROR: deployer balance is 0 GEN on StudioNet. Fund it from " +
        "the StudioNet faucet first."
    );
    process.exit(2);
  }

  const code = readFileSync(
    path.join(root, "contracts", "payproof_court.py"),
    "utf8"
  );
  console.log("Deploying PayProofCourt...");
  const txHash = await client.deployContract({ code, args: [] });
  console.log("Deploy tx hash:", txHash);

  const receipt = await client.waitForTransactionReceipt({
    hash: txHash,
    status: TransactionStatus.FINALIZED,
    interval: 5000,
    retries: 240,
  });
  const contractAddress = receipt.to_address || receipt.recipient;
  console.log("Receipt status:", receipt.statusName || receipt.status);
  console.log("Contract address:", contractAddress);

  const deployment = {
    network: "studionet",
    chain_id: 61999,
    rpc: "https://studio.genlayer.com/api",
    deployer: account.address,
    contract_address: contractAddress,
    deploy_tx_hash: txHash,
    explorer_url:
      "https://genlayer-explorer.vercel.app/contract/" + contractAddress,
    deploy_tx_explorer_url:
      "https://genlayer-explorer.vercel.app/tx/" + txHash,
  };
  writeFileSync(
    path.join(root, "deployment.json"),
    JSON.stringify(deployment, null, 1) + "\n"
  );
  console.log("Wrote deployment.json");
}

main().catch((e) => {
  console.error("DEPLOY FAILED:", e && e.message ? e.message : e);
  process.exit(1);
});
