"""Modernized report engine (CBTRN03C) — pure Python, no dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from modern_python.models import Transaction, CardXref, TranType, TranCat


PAGE_SIZE = 20


@dataclass
class ReportContext:
    start_date: str
    end_date: str
    xref: Dict[str, CardXref] = field(default_factory=dict)
    trantypes: Dict[str, TranType] = field(default_factory=dict)
    trancats: Dict[tuple, TranCat] = field(default_factory=dict)


@dataclass
class Totals:
    page_total: Decimal = Decimal("0")
    account_total: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    line_counter: int = 0
    first_time: bool = True
    curr_card_num: str = ""


class ReportEngine:
    """Reimplementation of CBTRN03C report generation."""

    def __init__(self, ctx: ReportContext):
        self.ctx = ctx
        self.totals = Totals()
        self.lines: List[str] = []

    def generate(self, transactions: List[Transaction]) -> str:
        txns = sorted(transactions, key=lambda t: t.card_num)
        filtered = [t for t in txns if self.ctx.start_date <= t.proc_date <= self.ctx.end_date]

        for t in filtered:
            if self.totals.first_time:
                self.totals.first_time = False
                self.totals.curr_card_num = t.card_num
                self._write_headers(self.ctx.start_date, self.ctx.end_date)

            if t.card_num != self.totals.curr_card_num:
                self._write_account_totals()
                self.totals.curr_card_num = t.card_num

            if self.totals.line_counter > 0 and (self.totals.line_counter % PAGE_SIZE == 0):
                self._write_page_totals()
                self._write_headers(self.ctx.start_date, self.ctx.end_date)

            xr = self.ctx.xref.get(t.card_num)
            tt = self.ctx.trantypes.get(t.tran_type_cd)
            tc = self.ctx.trancats.get((t.tran_type_cd, t.tran_cat_cd))

            acct_id = xr.acct_id if xr else 0
            type_desc = tt.type_desc if tt else ""
            cat_desc = tc.cat_desc if tc else ""

            detail = (
                f"{t.tran_id:<16} {acct_id:<11} {t.tran_type_cd:<2}-{type_desc[:15]:<15} "
                f"{t.tran_cat_cd:04d}-{cat_desc[:29]:<29} {t.tran_source:<10}    "
                f"{t.tran_amt:>14,.2f}"
            )
            self.lines.append(detail)
            self.totals.line_counter += 1
            self.totals.page_total += t.tran_amt
            self.totals.account_total += t.tran_amt

        if filtered:
            self._write_account_totals()
            self._write_page_totals()
            self._write_grand_totals()

        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def _write_headers(self, start: str, end: str):
        self.lines.append(f"DALYREPT  Daily Transaction Report  Date Range: {start} to {end}")
        self.lines.append("")
        self.lines.append(
            f"{'Transaction ID':<17}{'Account ID':<12}{'Transaction Type':<19}"
            f"{'Tran Category':<35}{'Tran Source':<14}{'        Amount':>16}"
        )
        self.lines.append("-" * 133)

    def _write_page_totals(self):
        self.lines.append(f"Page Total{'.'*86}{self.totals.page_total:>14,.2f}")
        self.lines.append("-" * 133)
        self.totals.grand_total += self.totals.page_total
        self.totals.page_total = Decimal("0")

    def _write_account_totals(self):
        self.lines.append(f"Account Total{'.'*84}{self.totals.account_total:>14,.2f}")
        self.lines.append("-" * 133)
        self.totals.account_total = Decimal("0")

    def _write_grand_totals(self):
        self.lines.append(f"Grand Total{'.'*86}{self.totals.grand_total:>14,.2f}")
