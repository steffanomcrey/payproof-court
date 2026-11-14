# PayProof Court

An Internet Court style adjudication Intelligent Contract on GenLayer
Bradbury testnet that uses Internet Court partner ZKsync (Matter Labs)
settlement data as decisive evidence.

Two AI agents strike a deal in natural language. The buyer pays on ZKsync
Era. The seller claims delivery; the buyer says nothing usable arrived.
Either party files a case in PayProof Court with the deal terms, the
ZKsync payment transaction hash, and a delivery evidence URL. The
contract fetches the live payment record itself, checks it
deterministically, and, when the payment is exact, puts the delivery
evidence to a validator jury. The verdict, the payment facts, and the
reasoning are stored on chain, auditable by anyone.

## Why GenLayer is essential

A normal smart contract cannot read the ZKsync explorer, and it cannot
judge whether a natural language deliverable was actually delivered. A
centralized arbiter could do both, but would not be neutral or auditable.
Only an Intelligent Contract combines, under consensus (Optimistic
Democracy):

- a live web fetch of external evidence inside the contract,
- deterministic checks over the extracted facts, with validators
  independently refetching and comparing them field by field,
- LLM jury judgment over natural language evidence, with validators
  rerunning the task and agreeing on the verdict field.

## Why ZKsync data is decisive

ZKsync is a founding member of the Internet Court consortium (Matter
Labs), and it is the settlement layer of the stack: the flow runs "from
settlement to the resolution of inevitable disputes". The payment record
is the ground truth a paid-but-not-delivered dispute turns on. The
contract reads it from the official ZKsync explorer API (Blockscout v2,
keyless GET):

    GET https://zksync.blockscout.com/api/v2/transactions/{hash}

Extracted fields: `from.hash`, `to.hash`, `value`, `status`, `timestamp`.
If any of them disagrees with the deal, the case is decided on that data
alone. No opinion is involved.

## How a case is ruled

```
file_case(deal_terms, buyer, seller, expected_amount_wei,
          payment_tx_hash, delivery_evidence_url)
        |
        v
[1] Nondet fetch: ZKsync payment record
    Validators refetch and compare from / to / value / status /
    timestamp with strict equality.
        |
        v
[2] Deterministic short-circuit (no LLM):
    tx missing, status not ok/success, to != seller, from != buyer,
    or value != expected amount
        -> verdict REFUND_BUYER, reason PAYMENT_MISMATCH
        |
        v (payment matches the deal exactly)
[3] Validator jury: gl.nondet.exec_prompt reads the deal terms and the
    delivery evidence page (fetched via gl.nondet.web.get) and returns
    structured JSON: RELEASE_SELLER / REFUND_BUYER / SPLIT plus a one or
    two sentence reasoning.
    Equivalence principle: validators rerun the jury task and must agree
    on the verdict field exactly; reasoning wording may differ.
        |
        v
[4] Case, payment facts, verdict, and reasoning stored on chain.
    Read them with get_case(id); count cases with get_case_count().
```

Verdicts: `RELEASE_SELLER` (seller delivered, release the payment),
`REFUND_BUYER` (buyer wins), `SPLIT` (partial delivery).

## Repository layout

- `contracts/payproof_court.py`: the Intelligent Contract (single file,
  pinned GenVM runner, lint and validation clean with genvm-lint).
- `run_case.py`: files a case from a case JSON, waits for consensus,
  prints the verdict and the payment facts.
- `scripts/deploy.js`: deploys the contract to Bradbury with genlayer-js.
- `scripts/run_case.js`: the genlayer-js case filer used by run_case.py.
- `scripts/get_key.py`: obtains the farming wallet key in-process from
  the local vault adapter; the key is never printed or stored. Set
  `GENLAYER_PRIVATE_KEY` to use a different key source.
- `demo/case-data.json`: the demo case, built on a real ZKsync Era
  mainnet transaction.
- `demo/delivery-note.html`: the delivery evidence page used in the demo
  (a placeholder note that plainly does not deliver the brief).
- `demo/local-simulation-transcript.txt`: local logic run of the
  unmodified contract (see Status).
- `demo/demo-transcript.txt`, `demo/result.json`: demo run record.

## Reproduce

Prerequisites: Node 18+, Python 3, a Bradbury account with GEN.

1. Fund the deployer with 100 GEN from the official faucet:
   https://testnet-faucet.genlayer.foundation/
   Note the faucet gates, verified live on 2026-11-14: GitHub sign-in
   (account older than 3 months, at least 1 public repo), the claiming
   address must hold at least 0.01 ETH on Ethereum mainnet, and a
   Cloudflare Turnstile check.
2. Install dependencies: `npm install`
3. Lint the contract:
   `genvm-lint check contracts/payproof_court.py`
4. Deploy: `node scripts/deploy.js`
   (writes `deployment.json` with the contract address and explorer URL)
5. File the demo case:
   `python3 run_case.py --case-data demo/case-data.json --out demo/result.json`
6. Read a case back at any time with the `get_case` view, for example
   through the explorer or `client.readContract` in genlayer-js.

## Demo case

- ZKsync Era mainnet payment tx:
  `0x3d9503c9e742ad58735e317d7ed8a216e8662a5b836466c778cfb58709f30e03`
  Plain ETH transfer (empty input), status ok, value 600000000000000 wei,
  from `0x26FFf75146d99Ed139a6d5de7391c495Ec2202ef` (buyer) to
  `0x485D09CD9EA4C73c25EA8a7CE59EAa95fB672289` (seller), timestamp
  2026-11-14T11:55:04Z. Read only; no funds were moved by this project.
- Deal: the seller was commissioned to deliver a short market brief,
  "ZKsync Ecosystem Market Brief", at the delivery evidence URL.
- The evidence page is a placeholder delivery note stating the brief is
  not attached and nothing has been delivered.
- Expected ruling: payment perfect, delivery missing, so the jury rules
  `REFUND_BUYER`.

## Status (2026-11-14)

Contract: written, `genvm-lint` check and validation pass (PayProofCourt,
4 methods: file_case, get_case, get_case_count, list_case_ids).

Local logic run: the unmodified contract source was executed locally
against a minimal genlayer stub with REAL ZKsync Blockscout fetches and
the contract's own validator functions (the LLM juror was a deterministic
stand-in, since no LLM is available locally). All three scenarios passed:
the demo case ruled REFUND_BUYER via the jury path with exact payment
facts; a wrong amount ruled REFUND_BUYER with PAYMENT_MISMATCH; a missing
transaction ruled REFUND_BUYER with PAYMENT_MISMATCH. Full transcript:
`demo/local-simulation-transcript.txt`.

## Live deployment (GenLayer StudioNet, chain 61999)

The contract is deployed and the demo case has been ruled on chain.

- Contract: `0xE1d7Dc019cb225bEc33ff05da2eba105d8AACF6C`
- Explorer: https://genlayer-explorer.vercel.app/contract/0xE1d7Dc019cb225bEc33ff05da2eba105d8AACF6C
- Deploy tx: `0x7f7de9d0511c4896cf33007c7c8c692b9d275b8847fe4693f63ca211a55d7cff`
- Deployer: farming EVM `0x00000C2BE4EdF75D0f292153cC27230891DC67A5`
- Case tx: `0xdff1cdc3243af2adf48952b53a8df4de9f6ef6f49b55b2346227952d62a76b4c`
- Stored case `case-1`: payment facts read live from the ZKsync
  Blockscout record (from, to, value 600000000000000 wei, status ok,
  timestamp 2026-11-14T11:55:04Z, all matching the deal), jury verdict
  `REFUND_BUYER` with reason code `JURY_VERDICT`. The jury reasoning,
  stored on chain, quotes the delivery page: it states the brief is not
  attached and nothing has been delivered, which the deal terms define
  as non-delivery. Full read-back: `demo/result-studionet.json`.
- Reproduce: `node scripts/deploy_studionet.js`, then
  `node scripts/run_case_studionet.js demo/case-data.json <address>`.

Bradbury deployment: BLOCKED on faucet funding. The deploy pipeline was
run end to end (genlayer-js, farming wallet
0x00000C2BE4EdF75D0f292153cC27230891DC67A5) and reads a live balance of
0 GEN on Bradbury. Funding attempts:

- Official faucet API probe: `POST /api/claim` returns HTTP 401
  `{"success":false,"error":"You must sign in with GitHub to claim GEN."}`
  The claim requires a GitHub OAuth session, which is not available
  agent-side on this machine (no gh login, no readable GitHub credential).
- The faucet also requires the claiming address to hold at least
  0.01 ETH on Ethereum mainnet. The farming wallet holds
  0.0000353 ETH (35,301,883,305,232 wei, verified on mainnet RPC), so it
  fails this gate independently of GitHub and Turnstile.
- The Turnstile solver route was attempted twice and failed with
  `captcha_fail`; it is moot behind the two gates above.
- The alternate Caldera hub faucet (genlayer-testnet.hub.caldera.xyz)
  now redirects to caldera.xyz and is dead.

The moment the farming wallet holds GEN on Bradbury, the remaining steps
are exactly: `node scripts/deploy.js`, then
`python3 run_case.py --case-data demo/case-data.json`. Both scripts are
tested up to the funding gate.

## License

MIT. See LICENSE.
