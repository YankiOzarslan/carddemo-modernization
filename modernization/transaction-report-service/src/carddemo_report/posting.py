"""Modernized transaction posting (CBTRN02C).

Validates daily transactions against card cross-reference and account data,
posts valid ones (creating transaction records, updating account & category
balances), and writes rejects with reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .models import CardXref, Transaction


@dataclass
class RejectRecord:
    tran_id: str
    card_num: str
    reason_code: int
    reason_desc: str


@dataclass
class PostingResult:
    total: int = 0
    posted: int = 0
    rejected: int = 0
    rejects: list[RejectRecord] = field(default_factory=list)
    posted_transactions: list[Transaction] = field(default_factory=list)
    account_updates: dict[int, Decimal] = field(default_factory=dict)


class TransactionPoster:
    """Modernizes CBTRN02C validation + posting logic."""

    def __init__(self, xrefs: list[CardXref], accounts: list[dict],
                 tcatbal: list[dict]):
        self.xref_map = {x.card_num: x for x in xrefs}
        self.account_map = {a["acct_id"]: a for a in accounts}
        self.tcatbal_map = {(t["acct_id"], t["type_cd"], t["cat_cd"]): t for t in tcatbal}

    def _validate(self, daily: dict) -> tuple[int, str, CardXref | None, dict | None]:
        """Returns (reason_code, reason_desc, xref, account). 0 = valid."""
        card_num = daily["card_num"]
        xref = self.xref_map.get(card_num)
        if not xref:
            return 100, "INVALID CARD NUMBER FOUND", None, None

        account = self.account_map.get(xref.acct_id)
        if not account:
            return 101, "ACCOUNT RECORD NOT FOUND", xref, None

        # credit limit check
        temp_bal = account["cyc_credit"] - account["cyc_debit"] + daily["amt"]
        if account["credit_limit"] < temp_bal:
            return 102, "OVERLIMIT TRANSACTION", xref, account

        # expiration date check
        proc_date = (daily.get("proc_ts") or daily.get("orig_ts") or "")[:10]
        if account["exp_date"] < proc_date:
            return 103, "TRANSACTION RECEIVED AFTER ACCT EXPIRATION", xref, account

        return 0, "", xref, account

    def post(self, daily_transactions: list[dict]) -> PostingResult:
        result = PostingResult(total=len(daily_transactions))

        for d in daily_transactions:
            reason, desc, xref, account = self._validate(d)
            if reason != 0:
                result.rejected += 1
                result.rejects.append(RejectRecord(
                    tran_id=d.get("tran_id", ""),
                    card_num=d["card_num"],
                    reason_code=reason,
                    reason_desc=desc,
                ))
                continue

            # Post: create transaction record
            posted_tran = Transaction(
                tran_id=d["tran_id"],
                tran_type_cd=d["type_cd"],
                tran_cat_cd=d["cat_cd"],
                tran_source=d.get("source", "POS"),
                tran_desc=d.get("desc", ""),
                tran_amt=d["amt"],
                merchant_id=d.get("merchant_id", 0),
                merchant_name=d.get("merchant_name", ""),
                merchant_city=d.get("merchant_city", ""),
                merchant_zip=d.get("merchant_zip", ""),
                card_num=d["card_num"],
                orig_ts=d.get("orig_ts", ""),
                proc_ts=d.get("proc_ts", d.get("orig_ts", "")),
            )
            result.posted_transactions.append(posted_tran)

            # Update account cycle balances
            acct = account
            acct["cyc_credit"] = acct["cyc_credit"] + (d["amt"] if d["amt"] > 0 else Decimal("0"))
            acct["cyc_debit"] = acct["cyc_debit"] + (abs(d["amt"]) if d["amt"] < 0 else Decimal("0"))
            result.account_updates[xref.acct_id] = acct["cyc_credit"] - acct["cyc_debit"]

            # Update tcatbal
            key = (xref.acct_id, d["type_cd"], d["cat_cd"])
            if key in self.tcatbal_map:
                self.tcatbal_map[key]["bal"] += d["amt"]
            else:
                self.tcatbal_map[key] = {"acct_id": xref.acct_id, "type_cd": d["type_cd"],
                                         "cat_cd": d["cat_cd"], "bal": d["amt"]}

            result.posted += 1

        return result
