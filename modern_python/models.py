"""Data models mirroring the COBOL copybooks (CVTRA05Y, CVACT03Y, ...)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional


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
    proc_ts: str

    @property
    def proc_date(self) -> str:
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
class Account:
    """Mirrors CVACT01Y (ACCOUNT-RECORD, RECLN=300)."""
    acct_id: int
    active_status: str
    curr_bal: Decimal
    credit_limit: Decimal
    cash_credit_limit: Decimal
    open_date: str
    exp_date: str
    reissue_date: str
    cyc_credit: Decimal
    cyc_debit: Decimal
    addr_zip: str
    group_id: str


@dataclass
class TranCatBal:
    """Mirrors CVTRA01Y (TRAN-CAT-BAL-RECORD, RECLN=50)."""
    acct_id: int
    type_cd: str
    cat_cd: int
    bal: Decimal


def parse_date(s: str) -> str:
    return s.strip()[:10]
