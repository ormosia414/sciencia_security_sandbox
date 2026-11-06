import csv
import io
import json
import logging
import os
import re
from hmac import compare_digest
from collections import Counter
from datetime import datetime, timezone

from flask import Flask, Response, g, jsonify, render_template, request, send_file
from werkzeug.serving import WSGIRequestHandler

from config import APP_SECRET, ENABLE_DEBUG, LOG_REQUEST_DETAILS, VIEWER_TOKEN, OPERATOR_TOKEN
from db import DB_PATH, connect, init_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_PATH = os.path.join(BASE_DIR, "data", "provider_reviews.json")
LOG_PATH = os.path.join(BASE_DIR, "logs", "app.log")

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)
app.secret_key = APP_SECRET
app.config.update(VIEWER_TOKEN=VIEWER_TOKEN, OPERATOR_TOKEN=OPERATOR_TOKEN)

# Endpoint names are developer-defined, never supplied as role claims by clients.
ROLE_PERMISSIONS = {
    "Viewer": {"index", "reviews", "summary", "admin_runs", "export_csv"},
}
ROLE_PERMISSIONS["Operator"] = ROLE_PERMISSIONS["Viewer"] | {"ingest", "export_db"}
HISTORY_FIELDS = "run_id, app_id, started_at, fetched_count, inserted_count, status"
TOKEN_PATTERN = r"[A-Za-z0-9._~+/-]+=*"


def identify_role():
    viewer = app.config.get("VIEWER_TOKEN", "")
    operator = app.config.get("OPERATOR_TOKEN", "")
    # Validate the whole pair before authorizing either role.
    if not all(isinstance(value, str) and re.fullmatch(TOKEN_PATTERN, value)
               for value in (viewer, operator)):
        return None
    if compare_digest(viewer.encode(), operator.encode()):
        return None
    credential = re.fullmatch(r"Bearer (" + TOKEN_PATTERN + r")",
                              request.headers.get("Authorization", ""), re.IGNORECASE)
    if credential is None:
        return None
    supplied = credential.group(1).encode("utf-8")
    is_viewer = compare_digest(supplied, viewer.encode("utf-8"))
    is_operator = compare_digest(supplied, operator.encode("utf-8"))
    return "Operator" if is_operator else "Viewer" if is_viewer else None


@app.before_request
def enforce_permissions():
    # Let Flask handle unmatched routes/methods without exposing route content.
    if request.url_rule is None:
        return None
    # Only Flask-generated OPTIONS is public: it advertises methods, not data.
    if request.method == "OPTIONS" and request.url_rule.provide_automatic_options:
        return None
    if request.endpoint == "health":
        return None
    if request.endpoint == "static":
        if request.view_args.get("filename") == "style.css":
            return None
        return jsonify({"error": "not found"}), 404
    g.role = identify_role()
    if g.role is None:
        return (jsonify({"error": "authentication required"}), 401,
                {"WWW-Authenticate": "Bearer"})
    if request.endpoint not in ROLE_PERMISSIONS[g.role]:
        return jsonify({"error": "forbidden"}), 403


APP_NAMES = {
    "com.sciencia.focus": "Focus AI",
    "com.sciencia.notes": "Smart Notes",
    "com.sciencia.travel": "Travel Companion",
}


def load_provider_data():
    with open(PROVIDER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.after_request
def record_request(response):
    if LOG_REQUEST_DETAILS:
        # Never include Authorization headers or query values in request logs.
        logging.info("request method=%s path=%s status=%s",
                     request.method, request.path, response.status_code)
    return response


class CredentialSafeRequestHandler(WSGIRequestHandler):
    """Keep local development access logs useful without logging URL queries."""

    def send_error(self, code, message=None, explain=None):
        # Parser diagnostics can contain raw request lines or header values.
        # Keep the status and standard reason, before inherited logging/output.
        super().send_error(code)

    def log_request(self, code="-", size="-"):
        path = getattr(self, "path", "").split("?", 1)[0]
        message = f"{getattr(self, 'command', '-')} {path} {self.request_version}"
        message = message.translate(self._control_char_table)
        self.log("info", '"%s" %s %s', message, code, size)


@app.route("/")
def index():
    with connect() as conn:
        counts = {
            row["app_id"]: row["n"]
            for row in conn.execute("SELECT app_id, COUNT(*) AS n FROM reviews GROUP BY app_id").fetchall()
        }
    return render_template("index.html", apps=APP_NAMES, counts=counts, can_ingest=g.role == "Operator")


@app.post("/ingest")
def ingest():
    app_id = request.form.get("app_id", "")
    provider = load_provider_data()
    rows = provider.get(app_id)
    if rows is None:
        return jsonify({"error": "unknown app_id"}), 404

    inserted = 0
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO apps(app_id, display_name) VALUES (?, ?)", (app_id, APP_NAMES.get(app_id, app_id)))
        for row in rows:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO reviews(review_id, app_id, rating, text, created_at, app_version, user_region)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["review_id"], app_id, row["rating"], row["text"], row["created_at"],
                    row.get("app_version"), row.get("user_region"),
                ),
            )
            inserted += cur.rowcount

        conn.execute(
            "INSERT INTO ingestion_runs(app_id, fetched_count, inserted_count, status, message) VALUES (?, ?, ?, ?, ?)",
            (app_id, len(rows), inserted, "SUCCESS", "mock provider ingestion completed"),
        )

    return jsonify({"app_id": app_id, "fetched": len(rows), "inserted": inserted})


@app.get("/reviews")
def reviews():
    app_id = request.args.get("app_id", "")
    q = request.args.get("q", "")

    sql = "SELECT review_id, app_id, rating, text, created_at, app_version, user_region FROM reviews WHERE 1=1"
    params = []
    if app_id:
        sql += " AND app_id = ?"
        params.append(app_id)
    if q:
        sql += " AND text LIKE ?"
        # Preserve SQLite LIKE semantics: % and _ remain wildcards.
        params.append(f"%{q}%")
    sql += " ORDER BY created_at DESC LIMIT 200"

    with connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    return jsonify(rows)


@app.get("/analysis/summary")
def summary():
    app_id = request.args.get("app_id", "")
    with connect() as conn:
        if app_id:
            rows = conn.execute("SELECT rating, text FROM reviews WHERE app_id = ?", (app_id,)).fetchall()
        else:
            rows = conn.execute("SELECT rating, text FROM reviews").fetchall()

    ratings = [r["rating"] for r in rows]
    words = []
    for r in rows:
        words.extend(w.strip(".,!?()[]\"").lower() for w in r["text"].split() if len(w) > 4)
    common = Counter(words).most_common(8)

    return jsonify({
        "review_count": len(rows),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "common_terms": common,
    })


@app.get("/admin/runs")
def admin_runs():
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT " + HISTORY_FIELDS + " FROM ingestion_runs ORDER BY run_id DESC LIMIT 100").fetchall()]
    return jsonify(rows)


@app.get("/export.csv")
def export_csv():
    with connect() as conn:
        rows = conn.execute("SELECT review_id, app_id, rating, text, created_at, app_version, user_region, ingested_at FROM reviews").fetchall()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["review_id", "app_id", "rating", "text", "created_at", "app_version", "user_region", "ingested_at"])
    for row in rows:
        writer.writerow(list(row))
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=reviews.csv"})


@app.get("/export.db")
def export_db():
    # Central authorization requires Operator; no legacy credential fallback.
    return send_file(DB_PATH, as_attachment=True, download_name="reviews.db")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


def run_local_server(port=5000, *, use_reloader=None):
    """Use the project's safe access logger for its loopback development server."""
    init_db()
    app.run(host="127.0.0.1", port=port, debug=ENABLE_DEBUG,
            use_reloader=ENABLE_DEBUG if use_reloader is None else use_reloader,
            request_handler=CredentialSafeRequestHandler)


if __name__ == "__main__":
    run_local_server()
