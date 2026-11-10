"""Reimplementation of CBTRN03C report generation logic in Python."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .models import (
    CardXref,
    ReportTotals,
    TranCat,
    Transaction,
    TranType,
)

PAGE_SIZE = 20


@dataclass
class ReportContext:
    start_date: str
    end_date: str
    xref: dict[str, CardXref] = field(default_factory=dict)
    trantypes: dict[str, TranType] = field(default_factory=dict)
    trancats: dict[tuple, TranCat] = field(default_factory=dict)
    totals: ReportTotals = field(default_factory=ReportTotals)
    lines: list[str] = field(default_factory=list)  # final report text lines

    def lookup_xref(self, card_num: str) -> CardXref | None:
        return self.xref.get(card_num.strip())

    def lookup_trantype(self, type_cd: str) -> TranType | None:
        return self.trantypes.get(type_cd.strip())

    def lookup_trancat(self, type_cd: str, cat_cd: int) -> TranCat | None:
        return self.trancats.get((type_cd.strip(), cat_cd))


class TransactionReportGenerator:
    """Mirrors CBTRN03C PROCEDURE DIVISION main loop."""

    def __init__(self, ctx: ReportContext):
        self.ctx = ctx

    def generate(self, transactions: Iterable[Transaction]) -> str:
        ctx = self.ctx
        # Sort by card number (JCL SORT FIELDS=(TRAN-CARD-NUM,A))
        txns = sorted(transactions, key=lambda t: t.card_num)
        # Filter by date range (TRAN-PROC-TS(1:10))
        filtered = [t for t in txns
                    if ctx.start_date <= t.proc_date <= ctx.end_date]

        # Header (written on first detail)
        for t in filtered:
            if ctx.totals.first_time:
                ctx.totals.first_time = False
                ctx.totals.curr_card_num = t.card_num
                self._write_headers(ctx.start_date, ctx.end_date)
                # lookup xref for first card
                xr = ctx.lookup_xref(t.card_num)
                self._current_xref = xr
            # card change -> account totals
            if t.card_num != ctx.totals.curr_card_num:
                self._write_account_totals()
                ctx.totals.curr_card_num = t.card_num
                xr = ctx.lookup_xref(t.card_num)
                self._current_xref = xr
                # page break handling already inside write_detail flow? replicate:
            # page break: every PAGE_SIZE detail lines
            if ctx.totals.line_counter > 0 and (ctx.totals.line_counter % PAGE_SIZE == 0):
                self._write_page_totals()
                self._write_headers(ctx.start_date, ctx.end_date)

            # lookups
            xr = ctx.lookup_xref(t.card_num) or self._current_xref
            tt = ctx.lookup_trantype(t.tran_type_cd)
            tc = ctx.lookup_trancat(t.tran_type_cd, t.tran_cat_cd)

            type_desc = tt.type_desc if tt else ""
            cat_desc = tc.cat_desc if tc else ""
            acct_id = xr.acct_id if xr else 0

            # detail line (mirrors TRANSACTION-DETAIL-REPORT)
            detail = (
                f"{t.tran_id:<16} {acct_id:<11} {t.tran_type_cd:<2}-{type_desc[:15]:<15} "
                f"{t.tran_cat_cd:04d}-{cat_desc[:29]:<29} {t.tran_source:<10}    "
                f"{t.tran_amt:>14,.2f}"
            )
            ctx.lines.append(detail)
            ctx.totals.line_counter += 1

            ctx.totals.page_total += t.tran_amt
            ctx.totals.account_total += t.tran_amt

        # EOF handling: page totals + account totals + grand totals
        if filtered:
            # account totals for last card
            self._write_account_totals()
            # page totals
            self._write_page_totals()
            # grand totals
            self._write_grand_totals()

        return "\n".join(ctx.lines) + ("\n" if ctx.lines else "")

    # ---- helpers ----
    def _write_headers(self, start: str, end: str):
        ctx = self.ctx
        ctx.lines.append(f"DALYREPT  Daily Transaction Report  Date Range: {start} to {end}")
        ctx.lines.append("")
        ctx.lines.append(
            f"{'Transaction ID':<17}{'Account ID':<12}{'Transaction Type':<19}"
            f"{'Tran Category':<35}{'Tran Source':<14}{'        Amount':>16}"
        )
        ctx.lines.append("-" * 133)

    def _write_page_totals(self):
        ctx = self.ctx
        ctx.lines.append(f"Page Total{'.'*86}{ctx.totals.page_total:>14,.2f}")
        ctx.lines.append("-" * 133)
        ctx.totals.grand_total += ctx.totals.page_total
        ctx.totals.page_total = 0  # reset; note COBOL adds page_total to grand on page total
        # Actually COBOL: ADD WS-PAGE-TOTAL TO WS-GRAND-TOTAL then MOVE 0. We did that.

    def _write_account_totals(self):
        ctx = self.ctx
        ctx.lines.append(f"Account Total{'.'*84}{ctx.totals.account_total:>14,.2f}")
        ctx.lines.append("-" * 133)
        ctx.totals.account_total = 0

    def _write_grand_totals(self):
        ctx = self.ctx
        ctx.lines.append(f"Grand Total{'.'*86}{ctx.totals.grand_total:>14,.2f}")
