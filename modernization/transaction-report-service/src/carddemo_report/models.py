"""Data models mirroring the COBOL copybooks (CVTRA05Y, CVACT03Y, ...)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class Transaction:
    """Mirrors CVTRA05Y (TRAN-RECORD, RECLN=350)."""
    tran_id: str
    tran_type_cd: str
    tran_cat_cd: int
    tran_source: str
    tran_desc: str
    tran_amt: Decimal
    merchant_id: int
    merchant_name: str
    merchant_city: str
    merchant_zip: str
    card_num: str
    orig_ts: str
    proc_ts: str  # 'YYYY-MM-DD HH:MM:SS.ffffff'

    @property
    def proc_date(self) -> str:
        # Prefer processed timestamp; fall back to original timestamp
        # (some CardDemo seed exports only populate ORIG-TS).
        ts = self.proc_ts.strip() or self.orig_ts.strip()
        return ts[:10] if ts else ""


@dataclass
class CardXref:
    """Mirrors CVACT03Y (CARD-XREF-RECORD)."""
    card_num: str
    cust_id: int
    acct_id: int


@dataclass
class TranType:
    """Mirrors CVTRA03Y."""
    type_cd: str
    type_desc: str


@dataclass
class TranCat:
    """Mirrors CVTRA04Y."""
    type_cd: str
    cat_cd: int
    cat_desc: str


@dataclass
class ReportLine:
    tran_id: str
    acct_id: int
    type_cd: str
    type_desc: str
    cat_cd: int
    cat_desc: str
    source: str
    amt: Decimal


@dataclass
class ReportTotals:
    page_total: Decimal = Decimal("0")
    account_total: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    line_counter: int = 0
    first_time: bool = True
    curr_card_num: str = ""
    page_size: int = 20


def parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def parse_decimal_cobol(s: str) -> Decimal:
    # COBOL S9(09)V99 -> signed, 2 implied decimals
    s = s.strip()
    # handle leading sign chars if present
    return Decimal(s) if s else Decimal("0")