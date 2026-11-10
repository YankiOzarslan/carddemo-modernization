"""Simple performance benchmark for the modernized report."""
import time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carddemo_report.io import load_from_disk, build_maps
from carddemo_report.report import ReportContext, TransactionReportGenerator

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    data_dir = os.path.join(repo_root, "app", "data", "ASCII")
    trans, xrefs, types, cats, s, e = load_from_disk(data_dir, None)
    xm, tm, cm = build_maps(xrefs, types, cats)

    # warmup
    ctx = ReportContext(start_date="2022-06-01", end_date="2022-06-30", xref=xm, trantypes=tm, trancats=cm)
    TransactionReportGenerator(ctx).generate(trans)

    N = 100
    t0 = time.perf_counter()
    for _ in range(N):
        ctx = ReportContext(start_date="2022-06-01", end_date="2022-06-30", xref=xm, trantypes=tm, trancats=cm)
        TransactionReportGenerator(ctx).generate(trans)
    dt = (time.perf_counter() - t0) / N
    print(f"Transactions: {len(trans)}")
    print(f"Avg per run: {dt*1000:.2f} ms  ({1/dt:.0f} reports/sec)")
    print(f"Throughput: {len(trans)/dt:,.0f} txn/sec")

if __name__ == "__main__":
    main()
