# Demo-only configuration for the local sandbox.
# Values in this file are not real credentials.

APP_SECRET = "sciencia-demo-secret-2026"
# Role secrets have no repository defaults. Missing/invalid pairs fail closed.
import os

VIEWER_TOKEN = os.environ.get("SCIENCIA_VIEWER_TOKEN", "")
OPERATOR_TOKEN = os.environ.get("SCIENCIA_OPERATOR_TOKEN", "")
ENABLE_DEBUG = True
LOG_REQUEST_DETAILS = True
