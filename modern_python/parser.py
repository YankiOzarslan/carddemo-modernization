"""Parsers for CardDemo fixed-width (VSAM) files."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Tuple

from modern_python.models import Transaction, CardXref, TranType, TranCat, Account, TranCatBal

_POSITIVE_OVERPUNCH = {"{": "0", "A": "1", "B": "2", "C": "3", "D": "4",
                      "E": "5", "F": "6", "G": "7", "H": "8", "I": "9"}
_NEGATIVE_OVERPUNCH = {"}": "0", "J": "1", "K": "2", "L": "3", "M": "4",
                      "N": "5", "O": "6", "P": "7", "Q": "8", "R": "9"}


def _safe_int(s: str, default: int = 0) -> int:
    s = s.strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        return default


def _decode_zoned_amount(field: str) -> Decimal:
    """Decode a COBOL S9(09)V99 zoned-decimal field (overpunch sign)."""
    f = (field or "").strip()
    if not f:
        return Decimal("0")
    f = f.rjust(11)
    sign = "+"
    last = f[-1]
    if last in _POSITIVE_OVERPUNCH:
        digit = _POSITIVE_OVERPUNCH[last]
    elif last in _NEGATIVE_OVERPUNCH:
        digit = _NEGATIVE_OVERPUNCH[last]
        sign = "-"
    else:
        digit = last if last.isdigit() else "0"
    num_str = "".join(ch for ch in (f[:-1] + digit) if ch.isdigit())
    if not num_str:
        return Decimal("0")
    value = Decimal(num_str) / Decimal("100")
    return -value if sign == "-" else value


def parse_transactions(text: str) -> List[Transaction]:
    """Parse TRANSACT file (RECLN=350). Mirrors CVTRA05Y layout."""
    out: List[Transaction] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(350)
        out.append(Transaction(
            tran_id=line[0:16].strip(),
            tran_type_cd=line[16:18].strip(),
            tran_cat_cd=_safe_int(line[18:22]),
            tran_source=line[22:32].strip(),
            tran_desc=line[32:132].strip(),
            tran_amt=_decode_zoned_amount(line[132:143]),
            merchant_id=_safe_int(line[143:152]),
            merchant_name=line[152:202].strip(),
            merchant_city=line[202:252].strip(),
            merchant_zip=line[252:262].strip(),
            card_num=line[262:278].strip(),
            orig_ts=line[278:304].strip(),
            proc_ts=line[304:330].strip(),
        ))
    return out


def parse_cardxref(text: str) -> List[CardXref]:
    out: List[CardXref] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(50)
        out.append(CardXref(
            card_num=line[0:16].strip(),
            cust_id=_safe_int(line[16:25]),
            acct_id=_safe_int(line[25:36]),
        ))
    return out


def parse_trantype(text: str) -> List[TranType]:
    out: List[TranType] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(60)
        out.append(TranType(type_cd=line[0:2].strip(), type_desc=line[2:52].strip()))
    return out


def parse_trancatg(text: str) -> List[TranCat]:
    out: List[TranCat] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(60)
        out.append(TranCat(
            type_cd=line[0:2].strip(),
            cat_cd=_safe_int(line[2:6]),
            cat_desc=line[6:56].strip(),
        ))
    return out


def parse_accounts(text: str) -> List[Account]:
    out: List[Account] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(300)
        out.append(Account(
            acct_id=_safe_int(line[0:11]),
            active_status=line[11:12].strip(),
            curr_bal=_decode_zoned_amount(line[12:24]),
            credit_limit=_decode_zoned_amount(line[24:36]),
            cash_credit_limit=_decode_zoned_amount(line[36:48]),
            open_date=line[48:58].strip(),
            exp_date=line[58:68].strip(),
            reissue_date=line[68:78].strip(),
            cyc_credit=_decode_zoned_amount(line[78:90]),
            cyc_debit=_decode_zoned_amount(line[90:102]),
            addr_zip=line[102:112].strip(),
            group_id=line[112:122].strip(),
        ))
    return out


def parse_tcatbal(text: str) -> List[TranCatBal]:
    out: List[TranCatBal] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.ljust(50)
        out.append(TranCatBal(
            acct_id=_safe_int(line[0:11]),
            type_cd=line[11:13].strip(),
            cat_cd=_safe_int(line[13:17]),
            bal=_decode_zoned_amount(line[17:28]),
        ))
    return out


def load_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def load_all(data_dir: str):
    """Load all CardDemo data files from a directory."""
    d = Path(data_dir)
    return {
        "transactions": parse_transactions(load_file(str(d / "dailytran.txt"))),
        "xrefs": parse_cardxref(load_file(str(d / "cardxref.txt"))),
        "trantypes": parse_trantype(load_file(str(d / "trantype.txt"))),
        "trancats": parse_trancatg(load_file(str(d / "trancatg.txt"))),
        "accounts": parse_accounts(load_file(str(d / "acctdata.txt"))) if (d / "acctdata.txt").exists() else [],
        "tcatbal": parse_tcatbal(load_file(str(d / "tcatbal.txt"))) if (d / "tcatbal.txt").exists() else [],
    }


def build_maps_from_data(xrefs, trantypes, trancats):
    """Build lookup dictionaries from parsed data."""
    xmap = {x.card_num: x for x in xrefs}
    tmap = {t.type_cd: t for t in trantypes}
    cmap = {(c.type_cd, c.cat_cd): c for c in trancats}
    return xmap, tmap, cmap
