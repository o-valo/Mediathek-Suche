#!/usr/bin/env python3
"""
Lokaler Web-Server für die Offline-Mediathek-Suche.

Nur Standardbibliothek (http.server + sqlite3) — kein pip install nötig.

Endpunkte:
  GET  /                     → Startseite (static/index.html)
  GET  /api/search?q=…&n=…   → Volltext-/Fuzzy-Suche (FTS5 trigram)
  GET  /api/stats            → Anzahl Einträge + Stand der Filmliste
  POST /api/refresh          → frische Filmliste herunterladen & neu indexieren
"""

import json
import os
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ingest import DB_PATH, ingest, DEFAULT_URL
from resolver import resolve_formats, sender_for
from senders import detect_sender

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SEARCH_SYNONYMS = {
    "sci": "science fiction",
    "scifi": "science fiction",
    "science fiction": "science fiction",
    "sf": "science fiction scifi",
}


class SearchEngine:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()

    def stats(self):
        self._ensure_db()
        with self._lock, sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT count(*) FROM filme").fetchone()[0]
        db_mtime = os.path.getmtime(self.db_path) if os.path.exists(self.db_path) else 0
        return {"eintraege": count, "db_datei": os.path.basename(self.db_path),
                "stand_ts": int(db_mtime)}

    def _ensure_db(self):
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                "Filmliste-Datenbank fehlt. Führe `python3 ingest.py` aus oder klicke auf ‚Neu laden‘."

            )

    _SEARCH_COLS = ["titel", "sender", "thema", "datum", "dauer", "url", "url_klein", "url_hd",
                    "url_untertitel", "website", "beschreibung"]

    def expand(self, q):
        # Synonyme auch pro Wort ersetzen (damit z. B. "Spielfilm SciFi")
        # → "Spielfilm science fiction").
        words = q.lower().split()
        out = []
        for w in words:
            out.append(SEARCH_SYNONYMS.get(w, w))
        return " ".join(out)

    def _sanitize(self, q):
        # FTS5-Query absichern: Sonderzeichen durch Leerzeichen ersetzen.
        # trigram-Matching ignoriert sie ohnehin, und ein "-" würde FTS5 sonst
        # als Spaltenfilter fehlinterpretieren ("science-fiction").
        return re.sub(r"[^0-9A-Za-zÄÖÜäöüß\s]+", " ", q).strip()

    def _fetch(self, conn, where, params, limit=500):
        sql = (
            "SELECT " + ",".join(self._SEARCH_COLS) + f", bm25(filme) "
            "FROM filme WHERE " + where + " ORDER BY bm25(filme) LIMIT ?"
        )
        cur = conn.execute(sql, params + (limit,))
        cols = list(self._SEARCH_COLS)
        out = []
        for r in cur.fetchall():
            item = dict(zip(cols, r[: len(cols)]))
            if not item.get("sender"):
                item["sender"] = detect_sender(item.get("url") or "")
            item["formats"] = resolve_formats(item)
            item["profile"] = sender_for(item)
            out.append(item)
        return out

    def search(self, q, n=20):
        self._ensure_db()
        q = q.strip()
        if not q:
            return []
        query = self.expand(q)
        safe = self._sanitize(query)
        tokens = [t for t in safe.split(" ") if t]

        with self._lock, sqlite3.connect(self.db_path) as conn:
            if not tokens or len("".join(tokens)) < 3:
                # sehr kurze Eingabe → roher LIKE-Scan
                like = f"%{q}%"
                cur = conn.execute(
                    "SELECT " + ",".join(self._SEARCH_COLS) + " "
                    "FROM filme WHERE titel LIKE ? OR beschreibung LIKE ? "
                    "ORDER BY datum DESC LIMIT ?",
                    (like, like, n),
                )
                cols = list(self._SEARCH_COLS)
                out = [dict(zip(cols, r[: len(cols)])) for r in cur.fetchall()]
                for item in out:
                    if not item.get("sender"):
                        item["sender"] = detect_sender(item.get("url") or "")
                    item["formats"] = resolve_formats(item)
                    item["profile"] = sender_for(item)
                return out

            if len(tokens) == 1:
                where, params = "filme MATCH ?", (safe,)
                return self._fetch(conn, where, params, limit=max(n, 1000))[:n]

            # Mehrere Begriffe: zuerst striktes UND (alle Begriffe im Text),
            # dann mit OR nachfüllen, damit die Suche robust bleibt.
            and_q = " ".join(tokens)          # implizites UND in FTS5
            or_q = " OR ".join(tokens)
            fetch_n = max(n, 1000)  # intern großzügig holen, damit 1000 möglich
            rows_and = self._fetch(conn, "filme MATCH ?", (and_q,), limit=fetch_n)
            if len(rows_and) >= n:
                return rows_and[:n]
            # deduplizieren (per Titel-Key) und mit OR-Ergebnissen auffüllen
            seen = set()
            merged = []
            for it in rows_and:
                key = (it["titel"], it["url"])
                if key not in seen:
                    seen.add(key); merged.append(it)
            for it in self._fetch(conn, "filme MATCH ?", (or_q,), limit=max(n, 1000)):
                key = (it["titel"], it["url"])
                if key not in seen:
                    seen.add(key); merged.append(it)
                if len(merged) >= n:
                    break
            return merged[:n]


engine = SearchEngine()


def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


_check_cache = {}
_CHECK_TTL = 900  # Sekunden (15 min)
_check_lock = threading.Lock()


def check_url(url, timeout=8):
    """HEAD-Prüfung: ist die URL erreichbar? Mit Cache (TTL 15 min)."""
    now = time.time()
    with _check_lock:
        hit = _check_cache.get(url)
        if hit and now - hit[0] < _CHECK_TTL:
            return hit[1]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = resp.status < 400
    except Exception:
        ok = False
    with _check_lock:
        _check_cache[url] = (now, ok)
    return ok


def stream_remote(handler, url, as_download=False):
    """Proxyt eine entfernte Video-/Untertitel-URL durch den lokalen Server.

    as_download=True → Content-Disposition: attachment (Download).
    Sonst → Inline-Stream mit Range-Support, damit der <video>-Player
            seeken kann.
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Range": handler.headers.get("Range", ""),
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type") or "application/octet-stream"
            clen = resp.headers.get("Content-Length")
            rng = resp.headers.get("Content-Range")

            handler.send_response(status)
            handler.send_header("Content-Type", ctype)
            if as_download:
                fname = url.split("/")[-1].split("?")[0] or "video.mp4"
                handler.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            if clen:
                handler.send_header("Content-Length", clen)
            if rng:
                handler.send_header("Content-Range", rng)
            handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                handler.wfile.write(chunk)
    except Exception as e:
        handler.send_error(502, f"Proxy-Fehler: {e}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # ruhiger
        pass

    def send_file(self, path, ctype):
        if not os.path.isfile(path):
            self.send_error(404)
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self.send_file(os.path.join(BASE_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/style.css":
            self.send_file(os.path.join(BASE_DIR, "style.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            self.send_file(os.path.join(BASE_DIR, "app.js"), "text/javascript; charset=utf-8")
        elif path == "/api/search":
            params = urllib.parse.parse_qs(parsed.query)
            q = params.get("q", [""])[0]
            try:
                n = min(max(int(params.get("n", ["20"])[0]), 1), 1000)
            except ValueError:
                n = 20
            try:
                results = engine.search(q, n)
            except FileNotFoundError:
                json_response(self, {"error": "no_db", "message": "Datenbank fehlt."}, 200)
                return
            json_response(self, {"q": q, "count": len(results), "results": results})
        elif path == "/api/check":
            params = urllib.parse.parse_qs(parsed.query)
            url = params.get("url", [""])[0]
            if not url.startswith("http://") and not url.startswith("https://"):
                json_response(self, {"url": url, "ok": False}, 200)
                return
            json_response(self, {"url": url, "ok": check_url(url)})
        elif path == "/api/stats":
            try:
                json_response(self, engine.stats())
            except FileNotFoundError:
                json_response(self, {"eintraege": 0, "db_datei": None, "stand_ts": 0, "fehlt": True})
        elif path in ("/api/stream", "/api/download"):
            params = urllib.parse.parse_qs(parsed.query)
            url = params.get("url", [""])[0]
            if not url.startswith("http://") and not url.startswith("https://"):
                json_response(self, {"error": "ungültige URL (nur http/https)"} , 400)
                return
            stream_remote(self, url, as_download=(path == "/api/download"))
        elif path == "/api/refresh":
            json_response(self, {"started": True, "message": "Refreshing… GET /api/stats für Status"}, 202)
        else:
            self.send_error(404)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path == "/api/refresh":
            def run():
                try:
                    ingest(url=DEFAULT_URL, progress=lambda m: print(m, flush=True))
                except Exception as e:  # noqa: BLE001
                    print("Refresh fehlgeschlagen:", e, flush=True)
            threading.Thread(target=run, daemon=True).start()
            json_response(self, {"started": True, "message": "Neue Filmliste wird geladen…"})
        else:
            self.send_error(404)


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[*] Mediathek-Suche läuft: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()