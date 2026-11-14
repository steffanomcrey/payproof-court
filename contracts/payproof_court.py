# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

# PayProof Court
#
# An Internet Court style adjudication contract on GenLayer.
#
# Two agents strike a deal in natural language. The buyer pays on ZKsync Era
# (the Internet Court settlement layer run by Matter Labs). If delivery is
# disputed, either party files a case here with the deal terms, the ZKsync
# payment transaction hash, and a delivery evidence URL.
#
# Ruling pipeline:
#   1. The contract fetches the live payment record from the ZKsync
#      Blockscout explorer API inside a nondeterministic block. Validators
#      independently refetch the same record and must agree exactly on the
#      extracted fields (from, to, value, status, timestamp).
#   2. Deterministic short-circuit: if the transaction is missing, not
#      successful, paid the wrong receiver, came from the wrong sender, or
#      moved a different amount than the deal states, the verdict is
#      REFUND_BUYER with reason PAYMENT_MISMATCH. No LLM is needed.
#   3. If the payment matches the deal exactly, a validator jury reads the
#      deal terms and the delivery evidence page and returns a structured
#      verdict: RELEASE_SELLER, REFUND_BUYER, or SPLIT. Validators rerun
#      the jury task and must agree on the verdict field (the equivalence
#      principle); the reasoning wording may differ.
#
# The verdict, the ZKsync payment facts, and the jury reasoning are stored
# on chain and are auditable by anyone through get_case().

import json
from dataclasses import dataclass

from genlayer import *

# Error classification prefixes, so validators can compare failure paths.
ERROR_EXPECTED = "[EXPECTED]"    # Business logic, deterministic
ERROR_EXTERNAL = "[EXTERNAL]"    # External API 4xx, deterministic
ERROR_TRANSIENT = "[TRANSIENT]"  # Network or 5xx, non-deterministic
ERROR_LLM = "[LLM_ERROR]"        # LLM misbehavior, always disagree

ZKSYNC_API = "https://zksync.blockscout.com/api/v2/transactions/"

VERDICT_RELEASE = "RELEASE_SELLER"
VERDICT_REFUND = "REFUND_BUYER"
VERDICT_SPLIT = "SPLIT"
ALLOWED_VERDICTS = (VERDICT_RELEASE, VERDICT_REFUND, VERDICT_SPLIT)

REASON_PAYMENT_MISMATCH = "PAYMENT_MISMATCH"
REASON_JURY = "JURY_VERDICT"


@allow_storage
@dataclass
class Case:
    case_id: str
    filed_by: str
    buyer: str
    seller: str
    deal_terms: str
    expected_amount_wei: str
    payment_tx_hash: str
    delivery_evidence_url: str
    payment_from: str
    payment_to: str
    payment_value: str
    payment_status: str
    payment_timestamp: str
    verdict: str
    reason_code: str
    reasoning: str
    status: str


def _norm_addr(addr: str) -> str:
    return addr.strip().lower()


def _norm_value(value) -> str:
    # Canonical decimal string for a wei amount, so "0600" and "600" agree.
    try:
        return str(int(str(value).strip()))
    except (ValueError, TypeError):
        return str(value).strip()


def _handle_leader_error(leaders_res, leader_fn) -> bool:
    """Canonical validator error handler: deterministic errors must match
    exactly, transient errors agree with transient errors, LLM errors and
    unknown errors always disagree so consensus rotates the leader."""
    leader_msg = leaders_res.message if hasattr(leaders_res, "message") else ""
    try:
        leader_fn()
        return False
    except gl.vm.UserError as e:
        validator_msg = e.message if hasattr(e, "message") else str(e)
        if validator_msg.startswith(ERROR_EXPECTED) or validator_msg.startswith(ERROR_EXTERNAL):
            return validator_msg == leader_msg
        if validator_msg.startswith(ERROR_TRANSIENT) and leader_msg.startswith(ERROR_TRANSIENT):
            return True
        return False
    except Exception:
        return False


class PayProofCourt(gl.Contract):
    # Storage: one Case per filed dispute, plus an index for enumeration.
    cases: TreeMap[str, Case]
    case_ids: DynArray[str]
    case_count: u256

    def __init__(self):
        self.case_count = u256(0)

    # ------------------------------------------------------------------
    # Nondeterministic step 1: fetch and verify the ZKsync payment record
    # ------------------------------------------------------------------

    def _fetch_payment_facts(self, tx_hash: str) -> dict:
        """Fetch the payment record from the ZKsync explorer API and return
        only the stable, decisive fields. Validators refetch and compare
        every field with strict equality."""

        def leader_fn():
            res = gl.nondet.web.get(ZKSYNC_API + tx_hash)
            if res.status == 404:
                return {
                    "exists": False,
                    "from": "",
                    "to": "",
                    "value": "",
                    "status": "not_found",
                    "timestamp": "",
                }
            if res.status >= 500:
                raise gl.vm.UserError(
                    f"{ERROR_TRANSIENT} ZKsync explorer returned {res.status}"
                )
            if res.status != 200:
                raise gl.vm.UserError(
                    f"{ERROR_EXTERNAL} ZKsync explorer returned {res.status}"
                )
            data = json.loads(res.body.decode("utf-8"))
            return {
                "exists": True,
                "from": _norm_addr(str(data["from"]["hash"])),
                "to": _norm_addr(str(data["to"]["hash"])),
                "value": _norm_value(data["value"]),
                "status": str(data["status"]).strip().lower(),
                "timestamp": str(data["timestamp"]),
            }

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_leader_error(leaders_res, leader_fn)
            validator_facts = leader_fn()
            leader_facts = leaders_res.calldata
            # Strict equality on every extracted field.
            return (
                validator_facts["exists"] == leader_facts["exists"]
                and validator_facts["from"] == leader_facts["from"]
                and validator_facts["to"] == leader_facts["to"]
                and validator_facts["value"] == leader_facts["value"]
                and validator_facts["status"] == leader_facts["status"]
                and validator_facts["timestamp"] == leader_facts["timestamp"]
            )

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # Nondeterministic step 2: the validator jury on delivery evidence
    # ------------------------------------------------------------------

    def _jury_verdict(self, deal_terms: str, evidence_url: str) -> dict:
        """The jury reads the deal terms and the delivery evidence page and
        returns a structured verdict. Validators rerun the task and must
        agree on the verdict field exactly; reasoning wording may differ."""

        def leader_fn():
            page_text = ""
            try:
                res = gl.nondet.web.get(evidence_url)
                if res.status == 200:
                    page_text = res.body.decode("utf-8", errors="replace")
                else:
                    page_text = (
                        f"[Evidence page could not be fetched, HTTP {res.status}]"
                    )
            except Exception:
                page_text = "[Evidence page could not be fetched]"
            page_text = page_text[:4000]

            prompt = f"""You are an impartial juror in the PayProof Court, an
Internet Court style dispute tribunal for agent to agent commerce.

A buyer and a seller made the deal below. The buyer has already paid in
full on ZKsync, and the payment is verified. Your only job is to decide,
from the delivery evidence page, whether the seller delivered what the
deal promised.

DEAL TERMS:
{deal_terms}

DELIVERY EVIDENCE PAGE (fetched live from the seller's evidence URL):
{page_text}

Decide exactly one verdict:
- RELEASE_SELLER: the evidence shows the promised deliverable was delivered.
- REFUND_BUYER: the evidence shows the deliverable was not delivered, is
  missing, is only a placeholder, or does not match the deal terms.
- SPLIT: the evidence shows partial delivery of real value.

Return JSON only, in exactly this shape:
{{"verdict": "RELEASE_SELLER" or "REFUND_BUYER" or "SPLIT", "reasoning": "one or two sentences explaining the decision based on the evidence"}}
"""
            result = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(result, dict):
                raise gl.vm.UserError(
                    f"{ERROR_LLM} Jury returned non-dict: {type(result)}"
                )
            verdict = str(result.get("verdict", "")).strip().upper()
            if verdict not in ALLOWED_VERDICTS:
                raise gl.vm.UserError(
                    f"{ERROR_LLM} Jury returned invalid verdict: {verdict}"
                )
            reasoning = str(result.get("reasoning", "")).strip()
            if not reasoning:
                raise gl.vm.UserError(f"{ERROR_LLM} Jury returned no reasoning")
            return {"verdict": verdict, "reasoning": reasoning}

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_leader_error(leaders_res, leader_fn)
            validator_result = leader_fn()
            # Equivalence principle: the verdict field must match exactly.
            return validator_result["verdict"] == leaders_res.calldata["verdict"]

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # Public write: file a case and get a ruling in the same transaction
    # ------------------------------------------------------------------

    @gl.public.write
    def file_case(
        self,
        deal_terms: str,
        buyer: str,
        seller: str,
        expected_amount_wei: str,
        payment_tx_hash: str,
        delivery_evidence_url: str,
    ) -> str:
        buyer_n = _norm_addr(buyer)
        seller_n = _norm_addr(seller)
        expected_n = _norm_value(expected_amount_wei)
        tx_hash_n = payment_tx_hash.strip().lower()

        # Step 1: live partner evidence, verified by validator refetch.
        facts = self._fetch_payment_facts(tx_hash_n)

        # Step 2: deterministic short-circuit on the payment facts.
        mismatch = (
            not facts["exists"]
            or facts["status"] not in ("ok", "success")
            or facts["to"] != seller_n
            or facts["from"] != buyer_n
            or facts["value"] != expected_n
        )

        if mismatch:
            verdict = VERDICT_REFUND
            reason_code = REASON_PAYMENT_MISMATCH
            reasoning = (
                "The ZKsync payment record does not match the deal: the "
                "transaction is missing, not successful, paid a different "
                "receiver, came from a different sender, or moved a "
                "different amount than the deal states."
            )
        else:
            # Step 3: payment is exact, so the jury weighs delivery.
            jury = self._jury_verdict(deal_terms, delivery_evidence_url)
            verdict = jury["verdict"]
            reason_code = REASON_JURY
            reasoning = jury["reasoning"]

        # Step 4: store the full case, payment facts, and ruling on chain.
        new_count = self.case_count + u256(1)
        case_id = "case-" + str(int(new_count))
        self.cases[case_id] = Case(
            case_id=case_id,
            filed_by=str(gl.message.sender_address),
            buyer=buyer_n,
            seller=seller_n,
            deal_terms=deal_terms,
            expected_amount_wei=expected_n,
            payment_tx_hash=tx_hash_n,
            delivery_evidence_url=delivery_evidence_url,
            payment_from=facts["from"],
            payment_to=facts["to"],
            payment_value=facts["value"],
            payment_status=facts["status"],
            payment_timestamp=facts["timestamp"],
            verdict=verdict,
            reason_code=reason_code,
            reasoning=reasoning,
            status="RULED",
        )
        self.case_ids.append(case_id)
        self.case_count = new_count
        return case_id

    # ------------------------------------------------------------------
    # Public views
    # ------------------------------------------------------------------

    @gl.public.view
    def get_case(self, case_id: str) -> dict:
        if case_id not in self.cases:
            raise gl.UserError(f"{ERROR_EXPECTED} Unknown case: {case_id}")
        c = self.cases[case_id]
        return {
            "case_id": c.case_id,
            "filed_by": c.filed_by,
            "buyer": c.buyer,
            "seller": c.seller,
            "deal_terms": c.deal_terms,
            "expected_amount_wei": c.expected_amount_wei,
            "payment_tx_hash": c.payment_tx_hash,
            "delivery_evidence_url": c.delivery_evidence_url,
            "payment_from": c.payment_from,
            "payment_to": c.payment_to,
            "payment_value": c.payment_value,
            "payment_status": c.payment_status,
            "payment_timestamp": c.payment_timestamp,
            "verdict": c.verdict,
            "reason_code": c.reason_code,
            "reasoning": c.reasoning,
            "status": c.status,
        }

    @gl.public.view
    def get_case_count(self) -> int:
        return int(self.case_count)

    @gl.public.view
    def list_case_ids(self) -> list:
        return [case_id for case_id in self.case_ids]
