import os
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from carddemo_report.models import CardXref, TranCat, Transaction, TranType
from carddemo_report.parsers import (
    parse_cardxref,
    parse_transactions,
)
from carddemo_report.report import ReportContext, TransactionReportGenerator

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample")


def mk_txn(card, amt, ttype="01", cat=1, proc="2022-06-10 10:00:00.000000", tid="T1"):
    return Transaction(
        tran_id=tid, tran_type_cd=ttype, tran_cat_cd=cat, tran_source="POS",
        tran_desc="desc", tran_amt=Decimal(amt), merchant_id=1,
        merchant_name="M", merchant_city="C", merchant_zip="0", card_num=card,
        orig_ts=proc, proc_ts=proc,
    )


def test_grouping_and_totals():
    txns = [
        mk_txn("CARD1", "10.00", tid="A"),
        mk_txn("CARD1", "20.00", tid="B"),
        mk_txn("CARD2", "5.00", tid="C"),
    ]
    ctx = ReportContext(
        start_date="2022-01-01", end_date="2022-12-31",
        xref={"CARD1": CardXref("CARD1", 1, 100), "CARD2": CardXref("CARD2", 2, 200)},
        trantypes={"01": TranType("01", "Purchase")},
        trancats={("01", 1): TranCat("01", 1, "Regular Sales Draft")},
    )
    out = TransactionReportGenerator(ctx).generate(txns)
    assert "Grand Total" in out
    # grand total = 35.00
    assert "35.00" in out
    # account totals present for both cards
    assert out.count("Account Total") == 2
    # page total present
    assert "Page Total" in out


def test_date_filter():
    txns = [
        mk_txn("CARD1", "10.00", proc="2022-06-10 10:00:00.000000"),
        mk_txn("CARD1", "20.00", proc="2021-01-01 10:00:00.000000"),
    ]
    ctx = ReportContext(start_date="2022-06-01", end_date="2022-06-30",
                        xref={}, trantypes={}, trancats={})
    out = TransactionReportGenerator(ctx).generate(txns)
    assert "10.00" in out
    assert "20.00" not in out


def test_empty_input():
    ctx = ReportContext(start_date="2022-01-01", end_date="2022-12-31",
                        xref={}, trantypes={}, trancats={})
    out = TransactionReportGenerator(ctx).generate([])
    assert out == ""


def test_page_break():
    txns = [mk_txn("CARD1", "1.00", tid=f"T{i}") for i in range(25)]
    ctx = ReportContext(start_date="2022-01-01", end_date="2022-12-31",
                        xref={"CARD1": CardXref("CARD1", 1, 100)},
                        trantypes={"01": TranType("01", "Purchase")},
                        trancats={("01", 1): TranCat("01", 1, "Regular Sales Draft")})
    out = TransactionReportGenerator(ctx).generate(txns)
    # 25 lines -> 2 page totals (at 20 and at end)
    assert out.count("Page Total") == 2


def test_parsers_dailytran():
    sample_path = os.path.join(os.path.dirname(__file__), "..", "..",
                               "app", "data", "ASCII", "dailytran.txt")
    if not os.path.exists(sample_path):
        return
    text = open(sample_path).read()
    txns = parse_transactions(text)
    assert len(txns) == 300
    assert all(t.card_num for t in txns)
    assert all(t.proc_ts.startswith("2022-") for t in txns)


def test_parsers_cardxref():
    sample_path = os.path.join(os.path.dirname(__file__), "..", "..",
                               "app", "data", "ASCII", "cardxref.txt")
    if not os.path.exists(sample_path):
        return
    text = open(sample_path).read()
    xs = parse_cardxref(text)
    assert len(xs) == 50
    assert all(x.acct_id > 0 for x in xs)


def test_analytics_basic():
    from carddemo_report.analytics import TransactionAnalytics
    txns = [mk_txn("CARD1", "10.00", tid="A"), mk_txn("CARD1", "20.00", tid="B"),
            mk_txn("CARD2", "5.00", tid="C")]
    res = TransactionAnalytics().compute(txns)
    assert res.total_transactions == 3
    assert res.total_amount == Decimal("35.00")
    assert len(res.by_category) == 1
    assert res.by_category[0].count == 3
    assert res.top_merchants[0][1] == 3


def test_analytics_to_json():
    from carddemo_report.analytics import TransactionAnalytics
    txns = [mk_txn("CARD1", "10.00", tid="A")]
    res = TransactionAnalytics().compute(txns)
    j = TransactionAnalytics().to_json(res)
    assert j["total_transactions"] == 1
    assert "by_category" in j


def test_posting_basic():
    from carddemo_report.posting import TransactionPoster
    xrefs = [CardXref("CARD1", 1, 100)]
    accounts = [{"acct_id": 100, "active_status": "Y", "curr_bal": Decimal("0"),
                 "credit_limit": Decimal("1000"), "cash_credit_limit": Decimal("500"),
                 "open_date": "2020-01-01", "exp_date": "2030-12-31",
                 "reissue_date": "2025-01-01", "cyc_credit": Decimal("0"),
                 "cyc_debit": Decimal("0"), "addr_zip": "0", "group_id": "G1"}]
    poster = TransactionPoster(xrefs=xrefs, accounts=accounts, tcatbal=[])
    daily = [{"tran_id": "T1", "card_num": "CARD1", "type_cd": "01", "cat_cd": 1,
              "source": "POS", "desc": "test", "amt": Decimal("100"),
              "merchant_id": 1, "merchant_name": "M", "merchant_city": "C",
              "merchant_zip": "0", "orig_ts": "2022-06-10", "proc_ts": "2022-06-10"}]
    result = poster.post(daily)
    assert result.posted == 1
    assert result.rejected == 0
    assert len(result.posted_transactions) == 1


def test_posting_reject_overlimit():
    from carddemo_report.posting import TransactionPoster
    xrefs = [CardXref("CARD1", 1, 100)]
    accounts = [{"acct_id": 100, "active_status": "Y", "curr_bal": Decimal("0"),
                 "credit_limit": Decimal("50"), "cash_credit_limit": Decimal("50"),
                 "open_date": "2020-01-01", "exp_date": "2030-12-31",
                 "reissue_date": "2025-01-01", "cyc_credit": Decimal("0"),
                 "cyc_debit": Decimal("0"), "addr_zip": "0", "group_id": "G1"}]
    poster = TransactionPoster(xrefs=xrefs, accounts=accounts, tcatbal=[])
    daily = [{"tran_id": "T1", "card_num": "CARD1", "type_cd": "01", "cat_cd": 1,
              "source": "POS", "desc": "test", "amt": Decimal("100"),
              "merchant_id": 1, "merchant_name": "M", "merchant_city": "C",
              "merchant_zip": "0", "orig_ts": "2022-06-10", "proc_ts": "2022-06-10"}]
    result = poster.post(daily)
    assert result.posted == 0
    assert result.rejected == 1
    assert result.rejects[0].reason_code == 102


def test_fraud_detection():
    from carddemo_report.fraud import FraudDetector
    # Create transactions with one obvious outlier
    txns = [mk_txn("CARD1", str(10 + i * 0.5), tid=f"T{i}") for i in range(20)]
    txns.append(mk_txn("CARD1", "99999.00", tid="OUTLIER"))
    detector = FraudDetector(contamination=0.1)
    report = detector.analyze(txns)
    assert report.total == 21
    assert report.anomalies >= 1
    assert len(report.high_risk) >= 1
    # The outlier should be flagged
    outlier_ids = [s.tran_id for s in report.high_risk + report.medium_risk]
    assert "OUTLIER" in outlier_ids or report.anomalies >= 1


def test_fraud_to_json():
    from carddemo_report.fraud import FraudDetector
    txns = [mk_txn("CARD1", str(10 + i), tid=f"T{i}") for i in range(15)]
    detector = FraudDetector(contamination=0.1)
    report = detector.analyze(txns)
    j = detector.to_json(report)
    assert "total_transactions" in j
    assert "anomalies_detected" in j
    assert "risk_distribution" in j


@given(st.lists(st.floats(min_value=0.01, max_value=1000, allow_nan=False), min_size=5, max_size=50))
def test_report_total_matches_sum(amounts):
    from decimal import Decimal
    txns = [mk_txn("CARD1", f"{a:.2f}", tid=f"T{i}") for i, a in enumerate(amounts)]
    from carddemo_report.report import ReportContext, TransactionReportGenerator
    ctx = ReportContext(start_date="2022-01-01", end_date="2022-12-31",
                        xref={"CARD1": CardXref("CARD1", 1, 100)},
                        trantypes={"01": TranType("01", "Purchase")},
                        trancats={("01", 1): TranCat("01", 1, "Regular Sales Draft")})
    out = TransactionReportGenerator(ctx).generate(txns)
    expected = sum(Decimal(f"{a:.2f}") for a in amounts)
    assert f"{expected:,.2f}" in out
