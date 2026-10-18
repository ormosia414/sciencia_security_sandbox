# System Overview

The sandbox represents a simplified internal review-data workflow.

## Logical flow

Browser / user
→ Flask web application
→ mock external review provider
→ normalization logic
→ SQLite database
→ search / export / summary views

The application also writes local logs and exposes a small administrative run-history view.

## Main assets

- Review text and metadata
- Ingestion run history
- SQLite database
- Application configuration
- Local log files
- Source code and dependencies

This document intentionally provides only a high-level description. The intern is expected to inspect the code and produce their own architecture/data-flow view during the first module.
