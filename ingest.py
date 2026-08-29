#!/usr/bin/env python3
"""
Ingest-Modul: lädt die öffentliche MediathekView-Filmliste herunter,
parst das kompakte JSON und baut eine lokale SQLite-FTS5-Datenbank
(für schnelle, offline nutzbare Volltext- & Fuzzy-Suche).

Datenquelle: https://verteiler1.mediathekview.de/Filmliste-akt.xz
Format:      xz-komprimiertes JSON. Das Dokument ist EIN einziges großes
             Objekt mit Duplikat-Schlüsseln, etwa:
               {"Filmliste":[Meta…],"Filmliste":[Header…],
                "X":[…],"X":[…],"X":[…], …}
             Ein normales json.loads würde die Duplikate verwerfen und die
             gesamte Datei in den Speicher laden. Deshalb wird hier streng
             gestreamt: ein kleiner Scanner extrahiert jedes "key":[….]
             Paar einzeln.
"""

import io
import json
import lzma
import os
import sqlite3
import sys
import tempfile
import urllib.request

# Offizielle, programmatische Verteil-URL aus dem MediathekView-Projekt.
DEFAULT_URL = "https://verteiler1.mediathekview.de/Filmliste-akt.xz"

# Spaltenreihenfolge laut Headerzeile im Dump.
HEADER = [
    "sender", "thema", "titel", "datum", "zeit", "dauer", "groesse_mb",
    "beschreibung", "url", "website", "url_untertitel", "url_rtmp",
    "url_klein", "url_rtmp_klein", "url_hd", "url_rtmp_hd", "datuml",
    "url_history", "geo", "neu",
]

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "filmliste.db")


def safe_int(value):
    try:
        return int(float(value)) if value else None
    except (TypeError, ValueError):
        return None


def iter_key_arrays(stream, chunk_size=1 << 20):
    """Yields (key, [values…]) Paare aus dem kompakten, verketteten JSON.

    Wandert Zeichen für Zeichen durch den Byte-Strom und liefert jedes
    ``"key":[…]:`` als (key, geparstes Array)-Paar. Zwei Modi:
      - reine String-Werte: die üblichen Datenzeilen ({"X":[…]}),
      - Schlüssel, die selbst wieder Listen/Dicts enthalten, binden wir
        gar nicht erst ein (kommen laut Dump nicht vor).

    Der Scanner ist absichtlich naiv und schnell: er nimmt an, dass alle
    Array-Elemente Strings sind.
    """

    key = None              # aktueller Schlüssel (kleingeschrieben)
    items = []              # Elemente des gerade gelesenen Arrays
    in_str = False          # wir lesen einen String
    in_key = False          # der String ist der (noch zu formende) Schlüssel
    in_array = False        # innerhalb [ … ]
    escape = False
    buf = []                # Zeichen des aktuellen Strings (Reihenfolge)

    for chunk in iter(lambda: stream.read(chunk_size), b""):
        text = chunk.decode("utf-8", errors="replace")
        for ch in text:
            if in_str:
                if escape:
                    buf.append(ch)      # escapedes Zeichen roh behalten
                    escape = False
                elif ch == "\\":
                    buf.append(ch)      # Backslash roh anfügen
                    escape = True
                elif ch == '"':
                    raw = "".join(buf)
                    # raw ist der String-Inhalt MIT aktiven Escapes
                    value = json.loads('"' + raw + '"')
                    if in_key:
                        key = value.lower()
                        in_key = False
                    else:
                        items.append(value)
                    buf = []
                    in_str = False
                else:
                    buf.append(ch)
                continue

            if ch == '"':
                in_str = True
                buf = []
                if not in_array:
                    in_key = True
                continue

            if ch == "[":
                in_array = True
                items = []
                continue
            if ch == "]":
                # Array abgeschlossen
                if in_array:
                    yield key, items
                    key = None
                    items = []
                    in_array = False
                continue


def create_schema(conn):
    # FTS5 mit trigram-Tokenizer → Teilwort- und Tippfehler-tolerante Suche.
    # Metadaten-Spalten sind UNINDEXED (nur anzeigen, nicht durchsuchen).
    conn.executescript(
        """
        DROP TABLE IF EXISTS filme;
        CREATE VIRTUAL TABLE filme USING fts5(
            sender,
            thema,
            titel,
            beschreibung,
            datum UNINDEXED,
            zeit UNINDEXED,
            dauer UNINDEXED,
            groesse_mb UNINDEXED,
            url UNINDEXED,
            url_hd UNINDEXED,
            url_klein UNINDEXED,
            url_untertitel UNINDEXED,
            website UNINDEXED,
            geo UNINDEXED,
            tokenize='trigram'
        );
        """
    )


def _download(url):
    """Lädt url herunter und liefert Name einer temporären .xz-Datei."""
    tmp = tempfile.NamedTemporaryFile(suffix=".xz", delete=False)
    tmp_name = tmp.name
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mediathek-local-search/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, tmp:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                tmp.write(chunk)
        tmp.close()
        return tmp_name
    except Exception as e:
        os.unlink(tmp_name)
        raise RuntimeError(f"Download fehlgeschlagen: {e}")


def ingest(url=DEFAULT_URL, db_path=DB_PATH, progress=None, source_file=None):
    """Baut die SQLite-FTS5-Datenbank aus der Filmliste.

    source_file: optionaler, bereits heruntergeladener .xz-Dump — nützlich
    beim Entwickeln/Testen (nochmaliger Download entfällt). Ohne source_file
    wird frisch von `url` geladen.
    """
    if source_file:
        if progress:
            progress("Nutze lokale Datei …")
        tmp_name = source_file
        delete_source = False
    else:
        if progress:
            progress("Lade Filmliste …")
        tmp_name = _download(url)
        delete_source = True

    if progress:
        progress("Parse & indexiere …")
    print(f"[*] Dekomprimiere {tmp_name}")
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    rows = 0
    # header[i] = Position in einer Dump-Zeile, an der Feld HEADER[i] liegt.
    header = list(range(len(HEADER)))
    meta_date = None
    with open(tmp_name, "rb") as f:
        with lzma.open(f, mode="rb") as lz:
            for key, val in iter_key_arrays(lz):
                if key == "filmliste":
                    # Meta- oder Header-Zeile (beide nutzen den Schlüssel
                    # 'Filmliste'). Meta = 5 Elemente (erstes ein Datum),
                    # Header = 20 Spaltennamen.
                    if val and len(val) < 10:
                        meta_date = val[0]
                    elif val and isinstance(val[0], str) and val[0].lower() in HEADER:
                        # Dump-Position jedes HEADER-Feldes bestimmen.
                        # Der Dump nutzt Leerzeichen ("Url Untertitel"),
                        # unsere HEADER-Namen Unterstriche — daher normalisieren.
                        norm = lambda s: s.lower().replace(" ", "_")
                        dump_names = [norm(h) for h in val]
                        def _dump_index(name):
                            return dump_names.index(norm(name)) if norm(name) in dump_names else -1
                        header = [_dump_index(h) for h in HEADER]
                elif key == "x":
                    if not val:
                        continue
                    # row = Werte in HEADER-Reihenfolge (indexpositionen)
                    row = [val[i] if 0 <= i < len(val) else "" for i in header]
                    conn.execute(
                        "INSERT INTO filme (sender, thema, titel, beschreibung, datum, zeit, dauer, "
                        "groesse_mb, url, url_klein, url_hd, url_untertitel, website, geo) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            row[0],   # sender
                            row[1],   # thema
                            row[2],   # titel
                            row[7],   # beschreibung
                            row[3],   # datum
                            row[4],   # zeit
                            row[5],   # dauer
                            safe_int(row[6]),   # groesse_mb
                            row[8],   # url
                            row[12],  # url_klein
                            row[14],  # url_hd
                            row[10],  # url_untertitel
                            row[9],   # website
                            row[18],  # geo
                        ),
                    )
                    rows += 1
                    if progress and rows % 100000 == 0:
                        progress(f"… {rows:,} Einträge")
                    if rows % 20000 == 0:
                        conn.commit()

    conn.commit()
    conn.execute("INSERT INTO filme(filme) VALUES('optimize')")
    conn.commit()
    conn.close()
    if delete_source:
        os.unlink(tmp_name)
    if progress:
        progress("Fertig.")
    return {"rows": rows, "datum": meta_date, "db": db_path}


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    result = ingest(url, progress=lambda m: print(m, flush=True))
    print("Fertig:", result)