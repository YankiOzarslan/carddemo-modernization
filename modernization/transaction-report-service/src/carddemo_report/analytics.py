"""Transaction analytics — a 'modern' value-add on top of the legacy report.

The original CBTRN03C only printed a flat transaction listing. This module
computes the aggregates a modern dashboard/API would expose: totals by
category, by account, by transaction type, top merchants, and daily volume.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .models import Transaction


@dataclass
class CategorySummary:
    type_cd: str
    cat_cd: int
    cat_desc: str
    count: int
    total: Decimal
    avg: Decimal


@dataclass
class AccountSummary:
    acct_id: int
    count: int
    total: Decimal
    avg: Decimal
    min_amt: Decimal
    max_amt: Decimal


@dataclass
class AnalyticsResult:
    total_transactions: int
    total_amount: Decimal
    by_category: list[CategorySummary]
    by_account: list[AccountSummary]
    by_type: dict[str, tuple[int, Decimal]]
    top_merchants: list[tuple[str, int, Decimal]]
    daily_volume: dict[str, tuple[int, Decimal]]


class TransactionAnalytics:
    def __init__(self, trancat_desc: dict = None):
        self.trancat_desc = trancat_desc or {}

    def _cat_desc(self, t: Transaction) -> str:
        return self.trancat_desc.get((t.tran_type_cd, t.tran_cat_cd), "")

    def compute(self, transactions: list[Transaction]) -> AnalyticsResult:
        by_cat: dict[tuple[str, int], list[Transaction]] = defaultdict(list)
        by_type: dict[str, list[Transaction]] = defaultdict(list)
        by_merchant: dict[str, list[Transaction]] = defaultdict(list)
        daily: dict[str, list[Transaction]] = defaultdict(list)
        by_card: dict[str, list[Transaction]] = defaultdict(list)

        for t in transactions:
            by_cat[(t.tran_type_cd, t.tran_cat_cd)].append(t)
            by_card[t.card_num].append(t)
            by_type[t.tran_type_cd].append(t)
            if t.merchant_name:
                by_merchant[t.merchant_name].append(t)
            if t.proc_date:
                daily[t.proc_date].append(t)

        # category summaries
        cat_summaries = []
        for (tc, cc), txns in by_cat.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            cat_summaries.append(CategorySummary(
                type_cd=tc, cat_cd=cc, cat_desc=self._cat_desc_simple(tc, cc),
                count=len(txns), total=total,
                avg=(total / len(txns)) if txns else Decimal("0"),
            ))
        cat_summaries.sort(key=lambda c: abs(c.total), reverse=True)

        # account (card) summaries
        acct_summaries = []
        for _card, txns in by_card.items():
            amts = [x.tran_amt for x in txns]
            total = sum(amts, Decimal("0"))
            acct_summaries.append(AccountSummary(
                acct_id=0,  # card-level; xref maps card->account
                count=len(txns), total=total,
                avg=(total / len(txns)) if txns else Decimal("0"),
                min_amt=min(amts) if amts else Decimal("0"),
                max_amt=max(amts) if amts else Decimal("0"),
            ))
        acct_summaries.sort(key=lambda a: abs(a.total), reverse=True)

        # type summaries
        type_summary = {}
        for tc, txns in by_type.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            type_summary[tc] = (len(txns), total)

        # top merchants
        merchant_list = []
        for m, txns in by_merchant.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            merchant_list.append((m, len(txns), total))
        merchant_list.sort(key=lambda x: abs(x[2]), reverse=True)

        # daily volume
        daily_summary = {}
        for d, txns in daily.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            daily_summary[d] = (len(txns), total)

        total_amount = sum((t.tran_amt for t in transactions), Decimal("0"))

        return AnalyticsResult(
            total_transactions=len(transactions),
            total_amount=total_amount,
            by_category=cat_summaries,
            by_account=acct_summaries,
            by_type=type_summary,
            top_merchants=merchant_list[:10],
            daily_volume=daily_summary,
        )

    def _cat_desc_simple(self, tc, cc):
        return self.trancat_desc.get((tc, cc), "")

    def to_json(self, result: AnalyticsResult) -> dict:
        return {
            "total_transactions": result.total_transactions,
            "total_amount": str(result.total_amount),
            "by_category": [
                {"type": c.type_cd, "category": c.cat_cd, "desc": c.cat_desc,
                 "count": c.count, "total": str(c.total), "avg": str(c.avg)}
                for c in result.by_category
            ],
            "by_type": {k: {"count": v[0], "total": str(v[1])} for k, v in result.by_type.items()},
            "top_merchants": [{"name": m, "count": c, "total": str(t)} for m, c, t in result.top_merchants],
            "daily_volume": {d: {"count": v[0], "total": str(v[1])} for d, v in result.daily_volume.items()},
        }
