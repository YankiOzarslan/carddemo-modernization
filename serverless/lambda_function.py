"""AWS Lambda function: generates transaction report on S3 upload.

Triggered by S3 event (new dailytran.txt) or invoked directly with JSON.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modern_python"))

from parser import load_all, build_maps_from_data
from report_engine import ReportContext, ReportEngine


def handler(event, context=None):
    # Direct invocation
    if "start_date" in event and "end_date" in event:
        start = event["start_date"]
        end = event["end_date"]
        data_dir = event.get("data_dir", os.environ.get("CARDDATA_DIR", "/tmp/data"))
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

    # Load data
    if data_dir.startswith("s3://"):
        import boto3
        _, _, bucket, *rest = data_dir.split("/", 3)
        prefix = rest[0] if rest else ""
        s3 = boto3.client("s3")
        def get(key):
            return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8", "replace")
        base = prefix.rstrip("/") + "/"
        data = {
            "transactions": __import__("parser").parse_transactions(get(base + "dailytran.txt")),
            "xrefs": __import__("parser").parse_cardxref(get(base + "cardxref.txt")),
            "trantypes": __import__("parser").parse_trantype(get(base + "trantype.txt")),
            "trancats": __import__("parser").parse_trancatg(get(base + "trancatg.txt")),
        }
    else:
        data = load_all(data_dir)

    xm, tm, cm = build_maps_from_data(data["xrefs"], data["trantypes"], data["trancats"])
    ctx = ReportContext(start_date=start, end_date=end, xref=xm, trantypes=tm, trancats=cm)
    report = ReportEngine(ctx).generate(data["transactions"])

    # Upload to S3 if output_key provided
    if output_key and data_dir.startswith("s3://"):
        import boto3
        bucket = data_dir.split("/", 3)[2]
        boto3.client("s3").put_object(Bucket=bucket, Key=output_key, Body=report.encode("utf-8"))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "lines": report.count("\n"),
            "preview": report[:300],
        }),
    }
