"""Parsers for the CardDemo fixed-width (VSAM) files and date-param file."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from .models import CardXref, TranCat, Transaction, TranType

_POSITIVE_OVERPUNCH = {"{": "0", "A": "1", "B": "2", "C": "3", "D": "4",
                      "E": "5", "F": "6", "G": "7", "H": "8", "I": "9"}
_NEGATIVE_OVERPUNCH = {"}": "0", "J": "1", "K": "2", "L": "3", "M": "4",
                      "N": "5", "O": "6", "P": "7", "Q": "8", "R": "9"}


def _decode_zoned_amount(field: str) -> Decimal:
    """Decode a COBOL S9(09)V99 zoned-decimal field as stored in the
    ASCII dump (last digit overpunched with sign)."""
    f = field.strip() if field else ""
    if not f:
        return Decimal("0")
    # pad to 11
    f = f.rjust(11)
    sign = "+"
    last = f[-1]
    if last in _POSITIVE_OVERPUNCH:
        digit = _POSITIVE_OVERPUNCH[last]
    elif last in _NEGATIVE_OVERPUNCH:
        digit = _NEGATIVE_OVERPUNCH[last]
        sign = "-"
    else:
        # plain digit
        digit = last if last.isdigit() else "0"
    num_str = f[:-1] + digit
    # remove any non-digits just in case
    num_str = "".join(ch for ch in num_str if ch.isdigit())
    if not num_str:
        return Decimal("0")
    value = Decimal(num_str) / Decimal("100")
    return -value if sign == "-" else value


def _safe_int(s: str, default: int = 0) -> int:
    s = s.strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        return default


def parse_transactions(text: str) -> list[Transaction]:
    """Parse TRANSACT file (RECLN=350). Mirrors CVTRA05Y layout."""
    out: list[Transaction] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(350)
        # CVTRA05Y offsets (1-based -> 0-based)
        tran_id = line[0:16]
        tran_type_cd = line[16:18]
        tran_cat_cd = _safe_int(line[18:22])
        tran_source = line[22:32]
        tran_desc = line[32:132]
        amt_str = line[132:143]  # S9(09)V99 -> 11 chars, last digit overpunched with sign
        tran_amt = _decode_zoned_amount(amt_str)
        merchant_id = _safe_int(line[143:152])
        merchant_name = line[152:202]
        merchant_city = line[202:252]
        merchant_zip = line[252:262]
        card_num = line[262:278]
        orig_ts = line[278:304]
        proc_ts = line[304:330]
        out.append(Transaction(
            tran_id=tran_id.strip(),
            tran_type_cd=tran_type_cd.strip(),
            tran_cat_cd=tran_cat_cd,
            tran_source=tran_source.strip(),
            tran_desc=tran_desc.strip(),
            tran_amt=tran_amt,
            merchant_id=merchant_id,
            merchant_name=merchant_name.strip(),
            merchant_city=merchant_city.strip(),
            merchant_zip=merchant_zip.strip(),
            card_num=card_num.strip(),
            orig_ts=orig_ts.strip(),
            proc_ts=proc_ts.strip(),
        ))
    return out


def parse_cardxref(text: str) -> list[CardXref]:
    out: list[CardXref] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(50)
        card_num = line[0:16].strip()
        cust_id = _safe_int(line[16:25])
        acct_id = _safe_int(line[25:36])
        out.append(CardXref(card_num=card_num, cust_id=cust_id, acct_id=acct_id))
    return out


def parse_trantype(text: str) -> list[TranType]:
    out: list[TranType] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(60)
        out.append(TranType(type_cd=line[0:2].strip(), type_desc=line[2:52].strip()))
    return out


def parse_trancatg(text: str) -> list[TranCat]:
    out: list[TranCat] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(60)
        type_cd = line[0:2].strip()
        cat_cd = _safe_int(line[2:6])
        desc = line[6:56].strip()
        out.append(TranCat(type_cd=type_cd, cat_cd=cat_cd, cat_desc=desc))
    return out


def parse_dateparm(text: str) -> tuple[str, str]:
    """DATEPARM file: 'YYYY-MM-DD YYYY-MM-DD'."""
    for raw in text.splitlines():
        if raw.strip():
            parts = raw.split()
            if len(parts) >= 2:
                return parts[0], parts[1]
    raise ValueError("DATEPARM file is empty or invalid")


def parse_accounts(text: str):
    """Parse ACCOUNT file (RECLN=300). Returns list of dicts."""
    out = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(300)
        acct_id = _safe_int(line[0:11])
        active_status = line[11:12].strip()
        curr_bal = _decode_zoned_amount(line[12:24])
        credit_limit = _decode_zoned_amount(line[24:36])
        cash_credit_limit = _decode_zoned_amount(line[36:48])
        open_date = line[48:58].strip()
        exp_date = line[58:68].strip()
        reissue_date = line[68:78].strip()
        cyc_credit = _decode_zoned_amount(line[78:90])
        cyc_debit = _decode_zoned_amount(line[90:102])
        addr_zip = line[102:112].strip()
        group_id = line[112:122].strip()
        out.append({
            "acct_id": acct_id,
            "active_status": active_status,
            "curr_bal": curr_bal,
            "credit_limit": credit_limit,
            "cash_credit_limit": cash_credit_limit,
            "open_date": open_date,
            "exp_date": exp_date,
            "reissue_date": reissue_date,
            "cyc_credit": cyc_credit,
            "cyc_debit": cyc_debit,
            "addr_zip": addr_zip,
            "group_id": group_id,
        })
    return out


def parse_tcatbal(text: str):
    """Parse TCATBAL file (RECLN=50). Returns list of dicts."""
    out = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(50)
        acct_id = _safe_int(line[0:11])
        type_cd = line[11:13].strip()
        cat_cd = _safe_int(line[13:17])
        bal = _decode_zoned_amount(line[17:28])
        out.append({"acct_id": acct_id, "type_cd": type_cd, "cat_cd": cat_cd, "bal": bal})
    return out


def load_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")
