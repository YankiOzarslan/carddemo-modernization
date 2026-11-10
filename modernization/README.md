# CardDemo Modernization

This directory contains modernization work performed on top of the upstream
AWS CardDemo repository. The original COBOL/CICS/JCL sources remain
untouched under `app/` for traceability.

## Included modernizations

- `transaction-report-service/` — Python reimplementation of `CBTRN03C`
  (transaction report), runnable locally and deployable to AWS Lambda.
  See its own README.

## How to publish

1. Fork `aws-samples/aws-mainframe-modernization-carddemo` on GitHub.
2. Clone your fork.
3. Copy the `modernization/` directory into your fork.
4. Commit and push.
5. (Optional) Open a PR upstream following `CONTRIBUTING.md`.
