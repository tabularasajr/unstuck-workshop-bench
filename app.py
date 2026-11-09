"""A tiny workshop booking desk backed by SQLite."""
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("WORKSHOP_DB", ROOT / "workshops.sqlite3"))
WORKSHOPS = [
    (1, "Intro to Screen Printing", 2500, 8),
    (2, "Bike Repair Basics", 1550, 6),
    (3, "Build a Birdhouse", 1200, 1),
    (4, "Ceramics for Beginners", 3200, 4),
    (5, "Repair Your Jeans", 850, 10),
]


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workshops (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                price_cents INTEGER NOT NULL, seats INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY, workshop_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL, total_cents INTEGER NOT NULL,
                request_id TEXT NOT NULL
            );
        """)
        conn.executemany("INSERT OR IGNORE INTO workshops VALUES (?, ?, ?, ?)", WORKSHOPS)


def list_workshops(query):
    search = query.get("q", [""])[0].strip()
    page = int(query.get("page", ["1"])[0])
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM workshops WHERE instr(title, ?) > 0 ORDER BY id LIMIT 2 OFFSET ?",
            (search, page - 1),
        )
        return [dict(row) for row in rows]


def reserve(body, request_id):
    workshop_id = body.get("workshop_id")
    quantity = body.get("quantity")
    if type(workshop_id) is not int or type(quantity) is not int or quantity < 0:
        return 400, {"error": "Enter a workshop and a valid seat count."}
    if not request_id:
        return 400, {"error": "An Idempotency-Key header is required."}
    with connect() as conn:
        row = conn.execute("SELECT * FROM workshops WHERE id = ?", (workshop_id,)).fetchone()
        if row is None:
            return 404, {"error": "Workshop not found."}
        if row["seats"] < quantity:
            return 409, {"error": "Not enough seats left."}
        total = round(row["price_cents"] / 100) * 100 * quantity
        booking = conn.execute(
            "INSERT INTO bookings (workshop_id, quantity, total_cents, request_id) VALUES (?, ?, ?, ?)",
            (workshop_id, quantity, total, request_id),
        )
        conn.execute("UPDATE workshops SET seats = ? WHERE id = ?", (row["seats"] - quantity, workshop_id))
        return 201, {"id": booking.lastrowid, "quantity": quantity, "total_cents": total}


class Handler(BaseHTTPRequestHandler):
    def send_content(self, status, payload, mime="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def reply(self, status, data):
        self.send_content(status, json.dumps(data).encode())

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/":
            self.send_content(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/workshops":
            try:
                self.reply(200, list_workshops(parse_qs(url.query)))
            except ValueError:
                self.reply(400, {"error": "Page must be an integer."})
        else:
            self.reply(404, {"error": "Not found."})

    def do_POST(self):
        if self.path != "/api/bookings":
            self.reply(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, UnicodeError):
            self.reply(400, {"error": "Invalid booking data."})
            return
        self.reply(*reserve(body, self.headers.get("Idempotency-Key")))


if __name__ == "__main__":
    initialize()
    with ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", 8000))), Handler) as server:
        print(f"Workshop Desk running at http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
