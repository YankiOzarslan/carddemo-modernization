"""Web demo: serves the transaction report + analytics as interactive HTML.

Run:  PYTHONPATH=src python -m carddemo_report.web
Then open http://localhost:8000
"""
from __future__ import annotations

import json
import os

from flask import Flask, Response, render_template_string, request

from .analytics import TransactionAnalytics
from .io import build_maps, load_from_disk
from .report import ReportContext, TransactionReportGenerator

app = Flask(__name__)

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CardDemo Transaction Report (Modernized)</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#c9d1d9; --muted:#8b949e; --accent:#58a6ff; --green:#3fb950; --red:#f85149; --yellow:#d29922; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:"SFMono-Regular",Consolas,monospace; background:var(--bg); color:var(--text); padding:24px; }
    h1 { color:var(--accent); font-size:22px; }
    h2 { color:var(--accent); font-size:16px; margin:20px 0 10px; }
    .meta { color:var(--muted); font-size:12px; margin:4px 0 16px; }
    .meta a { color:var(--accent); }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin:16px 0; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; }
    .stat { text-align:center; }
    .stat .val { font-size:28px; color:var(--green); font-weight:bold; }
    .stat .val.zero { color:var(--red); }
    .stat .lbl { color:var(--muted); font-size:11px; margin-top:4px; }
    form { display:flex; gap:8px; margin:16px 0; flex-wrap:wrap; align-items:center; }
    input, button, select { padding:8px 14px; border-radius:6px; border:1px solid var(--border); background:#21262d; color:var(--text); font-family:inherit; }
    button { background:#238636; border-color:#238636; cursor:pointer; font-weight:bold; }
    button:hover { background:#2ea043; }
    button.secondary { background:#21262d; border-color:var(--accent); color:var(--accent); }
    pre { background:var(--card); border:1px solid var(--border); padding:16px; border-radius:8px; overflow:auto; white-space:pre; font-size:12px; line-height:1.4; max-height:400px; }
    canvas { max-height:280px; }
    .charts { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin:16px 0; }
    .badge { display:inline-block; background:#21262d; border:1px solid var(--border); border-radius:4px; padding:2px 8px; font-size:11px; color:var(--muted); margin-right:6px; }
    .hint { background:#1c2128; border:1px solid var(--yellow); border-radius:8px; padding:10px 14px; margin:10px 0; color:var(--yellow); font-size:12px; }
    .warn { background:#2d1b1b; border:1px solid var(--red); border-radius:8px; padding:10px 14px; margin:10px 0; color:var(--red); font-size:12px; }
    .quick { display:flex; gap:6px; flex-wrap:wrap; margin:8px 0; }
    .quick button { padding:4px 10px; font-size:11px; }
    @media (max-width:768px){ .charts{grid-template-columns:1fr;} }
  </style>
</head>
<body>
  <h1>🏦 CardDemo Transaction Report — Modernized</h1>
  <p class="meta">
    <span class="badge">COBOL → Python</span>
    <span class="badge">AWS Lambda ready</span>
    <span class="badge">Security scanned</span>
    Python reimplementation of COBOL program CBTRN03C (AWS CardDemo)
  </p>

  <div class="hint">
    📅 Available data range: <strong>{{ data_min }}</strong> to <strong>{{ data_max }}</strong>
    ({{ total_records }} transactions). Pick a date within this range.
  </div>

  {% if zero_results %}
  <div class="warn">
    ⚠️ No transactions found for {{ start }} → {{ end }}.
    Try the available range: {{ data_min }} to {{ data_max }}.
  </div>
  {% endif %}

  <form method="post" action="/">
    <input name="start" value="{{ start }}" placeholder="Start YYYY-MM-DD">
    <input name="end" value="{{ end }}" placeholder="End YYYY-MM-DD">
    <button type="submit">Generate Report</button>
  </form>

  <div class="quick">
    <span style="color:var(--muted);font-size:11px;line-height:24px;">Quick:</span>
    <button class="secondary" onclick="setRange('{{ data_min }}','{{ data_max }}')">All data</button>
    <button class="secondary" onclick="setRange('{{ data_min }}','{{ data_min }}')">Single day</button>
  </div>

  <div class="grid">
    <div class="card stat"><div class="val {{ 'zero' if total_txns == 0 else '' }}">{{ total_txns }}</div><div class="lbl">Total Transactions</div></div>
    <div class="card stat"><div class="val {{ 'zero' if total_txns == 0 else '' }}">{{ total_amt }}</div><div class="lbl">Total Amount</div></div>
  </div>

  {% if total_txns > 0 %}
  <div class="charts">
    <div class="card"><canvas id="catChart"></canvas></div>
    <div class="card"><canvas id="dailyChart"></canvas></div>
  </div>
  {% endif %}

  <h2>Transaction Report</h2>
  <pre>{{ report }}</pre>

  <p class="meta" style="margin-top:16px;">
    <a href="/analytics?start={{ start }}&end={{ end }}">JSON Analytics</a> ·
    <a href="/posting">Transaction Posting (CBTRN02C)</a>
  </p>

  <script>
    function setRange(s, e) {
      document.querySelector('input[name="start"]').value = s;
      document.querySelector('input[name="end"]').value = e;
    }
    {% if total_txns > 0 %}
    const catData = {{ cat_json | safe }};
    const dailyData = {{ daily_json | safe }};
    new Chart(document.getElementById('catChart'), {
      type:'doughnut',
      data:{ labels: catData.labels, datasets:[{ data: catData.values, backgroundColor:['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#79c0ff'] }] },
      options:{ plugins:{ title:{ display:true, text:'By Category', color:'#c9d1d9' }, legend:{ labels:{ color:'#c9d1d9' } } } }
    });
    new Chart(document.getElementById('dailyChart'), {
      type:'bar',
      data:{ labels: dailyData.labels, datasets:[{ label:'Daily Volume', data: dailyData.values, backgroundColor:'#58a6ff' }] },
      options:{ plugins:{ title:{ display:true, text:'Daily Volume', color:'#c9d1d9' }, legend:{ labels:{ color:'#c9d1d9' } } },
               scales:{ x:{ ticks:{ color:'#8b949e' } }, y:{ ticks:{ color:'#8b949e' } } } }
    });
    {% endif %}
  </script>
</body>
</html>
"""

POSTING_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Transaction Posting (CBTRN02C)</title>
  <style>
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#c9d1d9; --muted:#8b949e; --accent:#58a6ff; --green:#3fb950; --red:#f85149; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:"SFMono-Regular",Consolas,monospace; background:var(--bg); color:var(--text); padding:24px; }
    h1 { color:var(--accent); font-size:22px; }
    .meta { color:var(--muted); font-size:12px; margin:4px 0 16px; }
    .meta a { color:var(--accent); }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin:16px 0; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; text-align:center; }
    .card .val { font-size:28px; font-weight:bold; }
    .card .val.green { color:var(--green); }
    .card .val.red { color:var(--red); }
    .card .lbl { color:var(--muted); font-size:11px; margin-top:4px; }
    button { padding:10px 20px; border-radius:6px; border:1px solid #238636; background:#238636; color:#fff; cursor:pointer; font-weight:bold; font-family:inherit; }
    button:hover { background:#2ea043; }
    pre { background:var(--card); border:1px solid var(--border); padding:16px; border-radius:8px; overflow:auto; white-space:pre; font-size:12px; line-height:1.4; max-height:400px; margin-top:16px; }
    .badge { display:inline-block; background:#21262d; border:1px solid var(--border); border-radius:4px; padding:2px 8px; font-size:11px; color:var(--muted); margin-right:6px; }
  </style>
</head>
<body>
  <h1>💳 Transaction Posting (CBTRN02C)</h1>
  <p class="meta">
    <span class="badge">Modernized</span>
    <span class="badge">Validation + Posting</span>
    Python reimplementation of COBOL program CBTRN02C
  </p>
  <p class="meta"><a href="/">← Back to Report</a></p>

  <form method="post" action="/posting">
    <button type="submit">Run Posting</button>
  </form>

  {% if result %}
  <div class="grid">
    <div class="card"><div class="val">{{ result.total }}</div><div class="lbl">Total Transactions</div></div>
    <div class="card"><div class="val green">{{ result.posted }}</div><div class="lbl">Posted</div></div>
    <div class="card"><div class="val red">{{ result.rejected }}</div><div class="lbl">Rejected</div></div>
    <div class="card"><div class="val">{{ result.reject_rate }}</div><div class="lbl">Reject Rate</div></div>
  </div>
  <h2>Rejects (first 20)</h2>
  <pre>{{ rejects }}</pre>
  {% endif %}
</body>
</html>
"""


def _data_range(data_dir):
    """Detect available date range from transaction data."""
    try:
        trans, *_ = load_from_disk(data_dir, None)
        dates = sorted(set(t.proc_date for t in trans if t.proc_date))
        return (dates[0] if dates else "2022-01-01",
                dates[-1] if dates else "2022-12-31",
                len(trans))
    except Exception:
        return "2022-01-01", "2022-12-31", 0


def _prepare(start, end, data_dir):
    trans, xrefs, types, cats, _, _ = load_from_disk(data_dir, None)
    xm, tm, cm = build_maps(xrefs, types, cats)
    ctx = ReportContext(start_date=start, end_date=end, xref=xm, trantypes=tm, trancats=cm)
    report = TransactionReportGenerator(ctx).generate(trans)
    filtered = [t for t in trans if start <= t.proc_date <= end]
    cat_desc = {(c.type_cd, c.cat_cd): c.cat_desc for c in cats}
    analytics = TransactionAnalytics(trancat_desc=cat_desc)
    result = analytics.compute(filtered)
    cat_labels = [f"{c.type_cd}-{c.cat_cd}" for c in result.by_category]
    cat_values = [float(c.total) for c in result.by_category]
    daily_labels = sorted(result.daily_volume.keys())
    daily_values = [float(result.daily_volume[d][1]) for d in daily_labels]
    return report, result, cat_labels, cat_values, daily_labels, daily_values


@app.route("/", methods=["GET", "POST"])
def index():
    data_dir = os.environ.get("CARDDATA_DIR", "data/sample")
    data_min, data_max, total_records = _data_range(data_dir)

    if request.method == "POST":
        start = request.form.get("start", data_min)
        end = request.form.get("end", data_max)
    else:
        start = request.args.get("start", data_min)
        end = request.args.get("end", data_max)

    zero_results = False
    try:
        report, result, cat_labels, cat_values, daily_labels, daily_values = _prepare(start, end, data_dir)
        zero_results = (result.total_transactions == 0)
        return render_template_string(
            TEMPLATE, report=report, start=start, end=end,
            total_txns=result.total_transactions,
            total_amt=f"{result.total_amount:,.2f}",
            cat_json=json.dumps({"labels": cat_labels, "values": cat_values}),
            daily_json=json.dumps({"labels": daily_labels, "values": daily_values}),
            data_min=data_min, data_max=data_max, total_records=total_records,
            zero_results=zero_results,
        )
    except Exception as e:
        return render_template_string(
            TEMPLATE, report=f"Error: {e}", start=start, end=end,
            total_txns=0, total_amt="0.00", cat_json="{}", daily_json="{}",
            data_min=data_min, data_max=data_max, total_records=total_records,
            zero_results=True,
        )


@app.route("/posting", methods=["GET", "POST"])
def posting_view():
    data_dir = os.environ.get("CARDDATA_DIR", "data/sample")
    result = None
    rejects = ""
    if request.method == "POST":
        try:
            import os as _os

            from .parsers import parse_accounts, parse_tcatbal
            trans, xrefs, types, cats, _, _ = load_from_disk(data_dir, None)
            accounts, tcatbal = [], []
            acct_path = _os.path.join(data_dir, "acctdata.txt")
            tcat_path = _os.path.join(data_dir, "tcatbal.txt")
            if _os.path.exists(acct_path):
                accounts = parse_accounts(open(acct_path).read())
            if _os.path.exists(tcat_path):
                tcatbal = parse_tcatbal(open(tcat_path).read())
            daily = [{
                "tran_id": t.tran_id, "card_num": t.card_num,
                "type_cd": t.tran_type_cd, "cat_cd": t.tran_cat_cd,
                "source": t.tran_source, "desc": t.tran_desc,
                "amt": t.tran_amt, "merchant_id": t.merchant_id,
                "merchant_name": t.merchant_name, "merchant_city": t.merchant_city,
                "merchant_zip": t.merchant_zip, "orig_ts": t.orig_ts,
                "proc_ts": t.proc_ts,
            } for t in trans]
            from .posting import TransactionPoster
            poster = TransactionPoster(xrefs=xrefs, accounts=accounts, tcatbal=tcatbal)
            r = poster.post(daily)
            result = {
                "total": r.total, "posted": r.posted,
                "rejected": r.rejected,
                "reject_rate": f"{r.rejected / r.total * 100:.1f}%" if r.total else "0%",
            }
            rejects = json.dumps([{"tran_id": x.tran_id, "card": x.card_num,
                                 "reason_code": x.reason_code, "reason": x.reason_desc}
                                for x in r.rejects[:20]], indent=2)
        except Exception as e:
            rejects = f"Error: {e}"
    return render_template_string(POSTING_TEMPLATE, result=result, rejects=rejects)


@app.route("/analytics")
def analytics_view():
    data_dir = os.environ.get("CARDDATA_DIR", "data/sample")
    start = request.args.get("start", "2022-06-10")
    end = request.args.get("end", "2022-06-10")
    try:
        trans, xrefs, types, cats, _, _ = load_from_disk(data_dir, None)
        filtered = [t for t in trans if start <= t.proc_date <= end]
        cat_desc = {(c.type_cd, c.cat_cd): c.cat_desc for c in cats}
        analytics = TransactionAnalytics(trancat_desc=cat_desc)
        result = analytics.compute(filtered)
        body = json.dumps(analytics.to_json(result), indent=2, ensure_ascii=False)
        return Response(body, mimetype="application/json")
    except Exception as e:
        return Response(f'{{"error": "{e}"}}', mimetype="application/json", status=500)


def main():
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
