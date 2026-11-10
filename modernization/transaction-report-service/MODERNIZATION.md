# Modernization notes: CBTRN03C → Python

## Before (mainframe)
- **Language:** COBOL (CICS)
- **Runtime:** z/OS, CICS transaction `CR00`
- **Data:** VSAM KSDS (transactions, card xref, tran type, tran category), flat files
- **Trigger:** online CICS screen → submits JCL via intrapartition TD queue `JOBS`
- **Output:** sequential report file `TRANREPT` (133-byte records)
- **Date handling:** `CSUTLDTC` (COBOL date validation subprogram)
- **Money:** S9(09)V99 zoned decimal with overpunch sign

## After (cloud-native)
- **Language:** Python 3.10+
- **Runtime:** AWS Lambda (container or zip), or local CLI / Flask web demo
- **Data:** S3 objects (fixed-width text), or local files
- **Trigger:** S3 event on `dailytran.txt` upload, or HTTP POST / CLI
- **Output:** S3 object or stdout / HTTP response
- **Date handling:** `datetime.strptime` with validation
- **Money:** `decimal.Decimal` (no float drift)

## What changed
1. VSAM KSDS random reads → Python `dict` lookups (O(1)).
2. JCL SORT → `sorted(key=card_num)`.
3. Overpunch zoned decimal → `_decode_zoned_amount`.
4. CICS screen + TDQ job submission → Lambda + S3 event / HTTP API.
5. Hard-coded 20-line page size preserved for report fidelity.

## What stayed the same
- Record layouts (offsets match COBOL copybooks byte-for-byte).
- Report format (headers, detail, page/account/grand totals).
- Business rules (date filter, card grouping, lookups).

## Performance
- 300 transactions processed in < 0.1s locally (vs. batch job scheduling overhead on mainframe).
- No JCL, no job scheduler, no CICS region required.
