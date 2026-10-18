import csv
import io
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, render_template, request, send_file

from config import APP_SECRET, ENABLE_DEBUG, INTERNAL_EXPORT_TOKEN, LOG_REQUEST_DETAILS
from db import DB_PATH, connect, init_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_PATH = os.path.join(BASE_DIR, "data", "provider_reviews.json")
LOG_PATH = os.path.join(BASE_DIR, "logs", "app.log")

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)
app.secret_key = APP_SECRET

APP_NAMES = {
    "com.sciencia.focus": "Focus AI",
    "com.sciencia.notes": "Smart Notes",
    "com.sciencia.travel": "Travel Companion",
}


def load_provider_data():
    with open(PROVIDER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def record_request():
    if LOG_REQUEST_DETAILS:
        logging.info("request path=%s args=%s", request.path, dict(request.args))


@app.before_request
def before_request():
    record_request()


@app.route("/")
def index():
    with connect() as conn:
        counts = {
            row["app_id"]: row["n"]
            for row in conn.execute("SELECT app_id, COUNT(*) AS n FROM reviews GROUP BY app_id").fetchall()
        }
    return render_template("index.html", apps=APP_NAMES, counts=counts)


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

    # Intentionally simple implementation for the sandbox.
    sql = "SELECT review_id, app_id, rating, text, created_at, app_version, user_region FROM reviews WHERE 1=1"
    if app_id:
        sql += f" AND app_id = '{app_id}'"
    if q:
        sql += f" AND text LIKE '%{q}%'"
    sql += " ORDER BY created_at DESC LIMIT 200"

    with connect() as conn:
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
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
        rows = [dict(r) for r in conn.execute("SELECT * FROM ingestion_runs ORDER BY run_id DESC LIMIT 100").fetchall()]
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
    # The token is intentionally a simple query parameter in this training sandbox.
    token = request.args.get("token")
    if token != INTERNAL_EXPORT_TOKEN:
        return jsonify({"error": "invalid token"}), 403
    return send_file(DB_PATH, as_attachment=True, download_name="reviews.db")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=ENABLE_DEBUG)
