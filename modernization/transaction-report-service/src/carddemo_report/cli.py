"""Command-line interface for running the modernized report."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .analytics import TransactionAnalytics
from .fraud import FraudDetector
from .io import build_maps, load_from_disk
from .parsers import parse_accounts, parse_tcatbal
from .posting import TransactionPoster
from .report import ReportContext, TransactionReportGenerator


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="CardDemo modernized (Python)")
    p.add_argument("--data-dir", required=True, help="Directory with dailytran.txt, cardxref.txt, ...")
    p.add_argument("--dateparm", help="Path to DATEPARM file (start end)")
    p.add_argument("--start", help="Start date YYYY-MM-DD (overrides dateparm)")
    p.add_argument("--end", help="End date YYYY-MM-DD (overrides dateparm)")
    p.add_argument("-o", "--output", help="Write output to file instead of stdout")
    p.add_argument("--analytics", action="store_true", help="Print JSON analytics instead of the report")
    p.add_argument("--post", action="store_true", help="Run transaction posting (CBTRN02C) and print summary")
    p.add_argument("--fraud", action="store_true", help="Run fraud/anomaly detection and print report")
    args = p.parse_args(argv)

    trans, xrefs, types, cats, default_start, default_end = load_from_disk(args.data_dir, args.dateparm)
    xm, tm, cm = build_maps(xrefs, types, cats)
    start = args.start or default_start
    end = args.end or default_end

    if args.fraud:
        detector = FraudDetector(contamination=0.05)
        report = detector.analyze(trans)
        out = detector.to_json(report)
        report = json.dumps(out, indent=2, ensure_ascii=False)
    elif args.post:
        daily = [{
            "tran_id": t.tran_id, "card_num": t.card_num,
            "type_cd": t.tran_type_cd, "cat_cd": t.tran_cat_cd,
            "source": t.tran_source, "desc": t.tran_desc,
            "amt": t.tran_amt, "merchant_id": t.merchant_id,
            "merchant_name": t.merchant_name, "merchant_city": t.merchant_city,
            "merchant_zip": t.merchant_zip, "orig_ts": t.orig_ts,
            "proc_ts": t.proc_ts,
        } for t in trans]

        accounts = []
        tcatbal = []
        acct_path = os.path.join(args.data_dir, "acctdata.txt")
        tcat_path = os.path.join(args.data_dir, "tcatbal.txt")
        if os.path.exists(acct_path):
            accounts = parse_accounts(open(acct_path).read())
        if os.path.exists(tcat_path):
            tcatbal = parse_tcatbal(open(tcat_path).read())

        poster = TransactionPoster(xrefs=xrefs, accounts=accounts, tcatbal=tcatbal)
        result = poster.post(daily)
        report = json.dumps({
            "total": result.total,
            "posted": result.posted,
            "rejected": result.rejected,
            "reject_rate": f"{result.rejected / result.total * 100:.1f}%" if result.total else "0%",
            "rejects": [{"tran_id": r.tran_id, "card": r.card_num,
                         "reason_code": r.reason_code, "reason": r.reason_desc}
                        for r in result.rejects[:20]],
        }, indent=2, ensure_ascii=False)
    elif args.analytics:
        filtered = [t for t in trans if start <= t.proc_date <= end]
        cat_desc = {(c.type_cd, c.cat_cd): c.cat_desc for c in cats}
        analytics = TransactionAnalytics(trancat_desc=cat_desc)
        result = analytics.compute(filtered)
        report = json.dumps(analytics.to_json(result), indent=2, ensure_ascii=False)
    else:
        ctx = ReportContext(start_date=start, end_date=end, xref=xm, trantypes=tm, trancats=cm)
        report = TransactionReportGenerator(ctx).generate(trans)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Output written to {args.output}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
