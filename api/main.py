"""FastAPI REST API for CardDemo transaction reports and analytics."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add modern_python to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "modern_python"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from parser import load_all, build_maps_from_data
from models import Transaction
from report_engine import ReportContext, ReportEngine

app = FastAPI(
    title="CardDemo Transaction Report API",
    description="Modernized REST API for AWS CardDemo (COBOL → Python)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.environ.get("CARDDATA_DIR", "../legacy_cobol/../modernization/transaction-report-service/data/sample")
# Fallback to sample data
if not Path(DATA_DIR).exists():
    DATA_DIR = str(Path(__file__).resolve().parent.parent / "modernization" / "transaction-report-service" / "data" / "sample")


def _load_data():
    from parser import load_all, build_maps_from_data
    data = load_all(DATA_DIR)
    xm, tm, cm = build_maps_from_data(data["xrefs"], data["trantypes"], data["trancats"])
    return data, xm, tm, cm


@app.get("/health")
def health():
    return {"status": "healthy", "service": "carddemo-report-api"}


@app.get("/report", response_class=PlainTextResponse)
def get_report(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Generate transaction report for a date range."""
    try:
        data, xm, tm, cm = _load_data()
        ctx = ReportContext(start_date=start, end_date=end, xref=xm, trantypes=tm, trancats=cm)
        engine = ReportEngine(ctx)
        report = engine.generate(data["transactions"])
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics")
def get_analytics(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Get transaction analytics (JSON) for a date range."""
    try:
        data, xm, tm, cm = _load_data()
        filtered = [t for t in data["transactions"] if start <= t.proc_date <= end]
        cat_desc = {(c.type_cd, c.cat_cd): c.cat_desc for c in data["trancats"]}

        from collections import defaultdict
        from decimal import Decimal

        by_cat = defaultdict(list)
        by_type = defaultdict(list)
        daily = defaultdict(list)
        for t in filtered:
            by_cat[(t.tran_type_cd, t.tran_cat_cd)].append(t)
            by_type[t.tran_type_cd].append(t)
            if t.proc_date:
                daily[t.proc_date].append(t)

        cat_summaries = []
        for (tc, cc), txns in by_cat.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            cat_summaries.append({
                "type": tc, "category": cc,
                "desc": cat_desc.get((tc, cc), ""),
                "count": len(txns),
                "total": str(total),
                "avg": str(total / len(txns)) if txns else "0",
            })

        type_summaries = {}
        for tc, txns in by_type.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            type_summaries[tc] = {"count": len(txns), "total": str(total)}

        daily_summary = {}
        for d, txns in daily.items():
            total = sum((x.tran_amt for x in txns), Decimal("0"))
            daily_summary[d] = {"count": len(txns), "total": str(total)}

        total_amount = sum((t.tran_amt for t in filtered), Decimal("0"))

        return {
            "total_transactions": len(filtered),
            "total_amount": str(total_amount),
            "by_category": sorted(cat_summaries, key=lambda x: abs(Decimal(x["total"])), reverse=True),
            "by_type": type_summaries,
            "daily_volume": daily_summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transactions")
def list_transactions(
    start: str = Query(None, description="Start date YYYY-MM-DD"),
    end: str = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(50, description="Max results"),
):
    """List transactions with optional date filter."""
    data, xm, tm, cm = _load_data()
    txns = data["transactions"]
    if start:
        txns = [t for t in txns if t.proc_date >= start]
    if end:
        txns = [t for t in txns if t.proc_date <= end]
    txns = txns[:limit]
    return [
        {
            "tran_id": t.tran_id,
            "card_num": t.card_num,
            "type": t.tran_type_cd,
            "amount": str(t.tran_amt),
            "source": t.tran_source,
            "proc_date": t.proc_date,
        }
        for t in txns
    ]


@app.get("/health/detailed")
def detailed_health():
    data, xm, tm, cm = _load_data()
    return {
        "status": "healthy",
        "transactions": len(data["transactions"]),
        "accounts": len(data["accounts"]),
        "xrefs": len(data["xrefs"]),
        "trantypes": len(data["trantypes"]),
        "trancats": len(data["trancats"]),
    }
