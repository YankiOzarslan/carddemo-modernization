"""AWS Lambda entry point for the modernized transaction report.

Triggered by an S3 event (new dailytran.txt upload) or invoked directly
with a JSON payload:

    {"data_dir": "s3://bucket/prefix", "start_date": "2022-01-01",
     "end_date": "2022-07-06", "output_key": "reports/out.txt"}

For local testing, set env var CARDDATA_DIR and invoke handler(event, context).
"""
from __future__ import annotations

import json
import os
from typing import Any

from .report import ReportContext, TransactionReportGenerator


def _load_from_s3(bucket: str, prefix: str):
    import boto3
    s3 = boto3.client("s3")
    def get(key):
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8", "replace")
    base = prefix.rstrip("/") + "/"
    trans_txt = get(base + "dailytran.txt")
    xref_txt = get(base + "cardxref.txt")
    type_txt = get(base + "trantype.txt")
    cat_txt = get(base + "trancatg.txt")
    from .io import build_maps
    from .parsers import parse_cardxref, parse_trancatg, parse_transactions, parse_trantype
    trans = parse_transactions(trans_txt)
    xrefs = parse_cardxref(xref_txt)
    types = parse_trantype(type_txt)
    cats = parse_trancatg(cat_txt)
    xm, tm, cm = build_maps(xrefs, types, cats)
    return trans, xm, tm, cm


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    # Direct invocation payload
    if "start_date" in event and "end_date" in event:
        start = event["start_date"]
        end = event["end_date"]
        data_dir = event.get("data_dir") or os.environ.get("CARDDATA_DIR")
        output_key = event.get("output_key")
    else:
        # S3 event
        rec = event["Records"][0]["s3"]
        bucket = rec["bucket"]["name"]
        key = rec["object"]["key"]
        prefix = key.rsplit("/", 1)[0]
        start = event.get("start_date", "2022-01-01")
        end = event.get("end_date", "2022-12-31")
        data_dir = f"s3://{bucket}/{prefix}"
        output_key = event.get("output_key")

    if data_dir and data_dir.startswith("s3://"):
        _, _, bucket, *rest = data_dir.split("/", 3)
        prefix = rest[0] if rest else ""
        trans, xm, tm, cm = _load_from_s3(bucket, prefix)
    else:
        from .io import build_maps, load_from_disk
        trans, xrefs, types, cats, _, _ = load_from_disk(data_dir, None)
        xm, tm, cm = build_maps(xrefs, types, cats)

    ctx = ReportContext(start_date=start, end_date=end, xref=xm, trantypes=tm, trancats=cm)
    report = TransactionReportGenerator(ctx).generate(trans)

    if output_key and data_dir.startswith("s3://"):
        import boto3
        bucket = data_dir.split("/", 3)[2]
        boto3.client("s3").put_object(Bucket=bucket, Key=output_key, Body=report.encode("utf-8"))

    return {"statusCode": 200, "body": json.dumps({"lines": report.count(chr(10)), "preview": report[:500]})}
