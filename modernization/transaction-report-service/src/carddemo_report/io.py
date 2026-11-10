"""Helpers to load CardDemo data from disk or S3 and run the report."""
from __future__ import annotations

from pathlib import Path

from .parsers import (
    load_file,
    parse_cardxref,
    parse_dateparm,
    parse_trancatg,
    parse_transactions,
    parse_trantype,
)


def load_from_disk(data_dir: str, dateparm_path: str | None = None) -> tuple:
    d = Path(data_dir)
    trans = parse_transactions(load_file(str(d / "dailytran.txt")))
    xrefs = parse_cardxref(load_file(str(d / "cardxref.txt")))
    types = parse_trantype(load_file(str(d / "trantype.txt")))
    cats = parse_trancatg(load_file(str(d / "trancatg.txt")))
    if dateparm_path:
        start, end = parse_dateparm(load_file(dateparm_path))
    else:
        start, end = "2022-01-01", "2022-12-31"
    return trans, xrefs, types, cats, start, end


def build_maps(xrefs, types, cats):
    xmap = {x.card_num: x for x in xrefs}
    tmap = {t.type_cd: t for t in types}
    cmap = {(c.type_cd, c.cat_cd): c for c in cats}
    return xmap, tmap, cmap


def run_report(data_dir: str, dateparm_path: str | None = None) -> str:
    trans, xrefs, types, cats, start, end = load_from_disk(data_dir, dateparm_path)
    from .report import ReportContext, TransactionReportGenerator
    ctx = ReportContext(
        start_date=start, end_date=end,
        xref=build_maps(xrefs, types, cats)[0],
        trantypes=build_maps(xrefs, types, cats)[1],
        trancats=build_maps(xrefs, types, cats)[2],
    )
    return TransactionReportGenerator(ctx).generate(trans)
