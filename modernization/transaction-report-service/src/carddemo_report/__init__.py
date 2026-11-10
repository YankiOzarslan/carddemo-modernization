"""Modernized (Python) implementation of CardDemo's CBTRN03C transaction report.

Original: AWS CardDemo COBOL/CICS batch program (CBTRN03C) that produces a
formatted daily transaction report filtered by a date range.
This package reproduces the business logic in idiomatic Python so it can run
as an AWS Lambda function (or locally via the CLI).
"""