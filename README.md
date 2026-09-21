<p align="center">
  <img src="bot-suche-2.jpg" alt=" Mediathek-Suche Banner" width="100%">
</p>


# Mediathek-Suche (offline)

Ein lokaler Webclient, der die [MediathekView]-Filmliste herunterlädt, in eine
SQLite-Volltextdatenbank umwandelt und bequem durchsuchbar macht — **vollständig
offline** nach dem ersten Download.

Der Kerngedanke: Die eingebaute Suche des Original-Webclients ist umständlich
(keine Tippfehler-Toleranz, „SciFi“ liefert oft nichts). Dieses Projekt baut eine
eigene, lokale Suche mit Teilwort-/Tippfehler-Toleranz und bietet pro Treffer
direkt Vorschau & Download in den angebotenen Qualitäten (SD / Standard / HD,
Untertitel).

[MediathekView]: https://mediathekview.de/

---

## Funktionen


- **Fuzzy-/Volltextsuche** über Titel, Thema, Beschreibung und Sender
  (SQLite FTS5 mit Trigramm-Tokenizer). Teilwörter und kleinere Verschreibungen
  werden toleriert; Synonyme wie „SciFi“ → „Science Fiction“ sind eingebaut.
- **Robuste Mehrbegriff-Suche**: Mehrere Wörter (z. B. `Spielfilm SciFi`)
  werden zuerst als striktes UND gesucht; findet das zu wenig, wird automatisch
  per OR nachgefüllt (dedupliziert, UND-Treffer zuerst). Synonyme werden pro
  Begriff expandiert, sodass „SciFi“ auch im Suchbegriff-Kontext als
  „science fiction“ zählt.
- **Sender-Anzeige pro Treffer**: Der Sender wird angezeigt — direkt aus dem
  DB-Feld, und falls dieses leer ist (liegt bei der Filmliste bei ~99 % vor),
  automatisch aus der Video-URL abgeleitet (`senders.py`, ~99 % Trefferquote).
- **Format-Wahl pro Ergebnis**: SD, Standard und HD als Vorschau (Inline-Player)
  oder Download — aufgelöst über sender-spezifische Profil-Plugins.
- **Wählbare Trefferzahl** (20 / 40 / 100 / 500 / 1000) per klickbaren
  Buttons unter dem Suchfeld — der aktive Wert ist markiert; Änderung sucht
  sofort neu, auch mitten in einer laufenden Suche.
- **Untertitel-Download**, wo die Mediathek eine URL liefert.
- **„Neu laden“** lädt auf Knopfdruck eine frische Filmliste herunter und
  indexiert neu.

---

## Voraussetzungen

- Python **3.10+** (getestet mit 3.12).
- `lzma`, `sqlite3`, `http.server` sind Teil der Standardbibliothek.
- **Keine externen Abhängigkeiten** und kein `pip install` nötig.
- optional: `tmux` **oder** `screen` für den Hintergrund-Betrieb
- `curl` nur zum gelegentlichen Testen über die API (optional)

---

## Einrichtung (Setup)

```bash
cd mediathek   # in den Projektordner wechseln
chmod +x setup.sh start.sh stop.sh
./setup.sh      # legt die virtuelle Umgebung .venv an
```

> Warum ein venv? Das Projekt hat keine externen Pakete, aber ein venv
> isoliert die Laufzeit sauber — praktisch, wenn später Pakete ergänzt
> werden (z. B. für Erweiterungen). `start.sh` nutzt `.venv/bin/python3`
> automatisch, falls die Umgebung existiert, sonst das System-Python.
> Die Datei `requirements.txt` hält zukünftige Abhängigkeiten fest und
> wird von `setup.sh` automatisch ins venv installiert, sobald sie Einträge
> enthält.

---

## Start / Stopp

Alle Befehle im Projektordner `mediathek/` ausführen.

### Server starten

```bash
cd mediathek        # in den Projektordner wechseln
./start.sh          # Standard: tmux
./start.sh screen   # alternativ in screen
```

Der Server läuft in einer **session** (tmux oder screen) namens `mediathek`,
damit er auch nach Schließen des Terminals weiterläuft. Danach:

- Webclient öffnen: <http://localhost:8080>
- von einem anderen Gerät im selben Netz: `http://<IP-des-Rechners>:8080`
  (z. B. `http://192.168.2.76:8080`)

Den Port bei Bedarf per Umgebungsvariable ändern:

```bash
PORT=8090 ./start.sh
```

### Server stoppen

```bash
./stop.sh      # erkennt automatisch, ob tmux oder screen lief
```

### Logs ansehen

```bash
tmux attach -t mediathek     # tmux-Variante
screen -r mediathek          # screen-Variante
# verlassen mit:  Strg+B dann d   (tmux)   |   Strg+A dann d   (screen)
```

---

## Erster Start / „keine Datenbank“

Beim allerersten Start ist noch keine Datenbank vorhanden. Klicke im Webclient
auf **„Neu laden“** — damit wird die Filmliste heruntergeladen und indexiert
(dauert einige Minuten; ~700 000 Einträge). Alternativ manuell:

```bash
cd mediathek        # in den Projektordner wechseln
./.venv/bin/python3 ingest.py   # oder: source .venv/bin/activate && python3 ingest.py
```

Beim späteren Neustart des Servers ist die Datenbank bereits da; es muss nur
der Server laufen (`./start.sh`).

---

## Verzeichnisstruktur

```
mediathek/
├── README.md           # diese Datei
├── konzept.md          # ursprüngliche Idee / Anforderung
├── ingest.py           # Dump laden (xz), parsen, SQLite-FTS5-DB bauen
├── server.py           # lokaler HTTP-Server (Suche, Stream-Proxy, …)
├── senders.py          # Sender aus Video-URL ableiten (falls DB-Feld leer)
├── resolver.py         # Plugin-Lader für Sender-Profile
├── profiles/           # sender-spezifische URL-Auflösungs-Plugins
│   ├── zdf.py          #   ZDF / 3sat / arte / Phoenix / KiKA
│   ├── ard.py          #   SWR, BR, WDR, NDR, MDR, hr, rbb …
│   └── fallback.py     #   generisches Muster (akamai usw.)
├── static/             # Webclient (index.html, app.js, style.css)
├── requirements.txt    # Abhängigkeiten (aktuell leer, da nur Stdlib)
├── setup.sh            # legt die virtuelle Umgebung .venv an
├── start.sh / stop.sh  # Start/Stopp in tmux oder screen
├── .venv/              # optionale virtuelle Umgebung (von setup.sh erzeugt)
└── filmliste.db        # erzeugte Datenbank (entsteht beim Ingest)
```

---

## API (kurz)

| Endpunkt | Beschreibung |
|---|---|
| `GET /` | Web-Oberfläche |
| `GET /api/search?q=SciFi&n=20` | Suche; `n` = Trefferzahl (1–1000, Standard 20); liefert `formats` (SD/Standard/HD) |
| `GET /api/stats` | Anzahl Einträge + Stand der Datenbank |
| `GET /api/check?url=…` | prüft, ob eine Video-URL erreichbar ist |
| `POST /api/refresh` | lädt frische Filmliste und indexiert neu |
| `GET /api/stream?url=…` | Inline-Stream (Vorschau, mit Range-Support) |
| `GET /api/download?url=…` | Download als Datei |

Beispiel:

```bash
curl -s "http://localhost:8080/api/search?q=sci%20fi"  | python3 -m json.tool
```

Jeder Suchtreffer liefert `sender`, `formats` (SD/Standard/HD) und `profile`
(verwendetes Sender-Profil).

---

## Wie die Suche funktioniert (robuste Mehrbegriff-Suche)

Grundlage ist SQLite **FTS5 mit Trigramm-Tokenizer**: Dadurch werden Teilwörter
und kleinere Schreibfehler toleriert (`star trek` findet auch `Star-Trek-…`).

Bei **mehreren eingegebenen Begriffen** (z. B. `Spielfilm SciFi`) läuft die Suche
in zwei Stufen, damit sie robust bleibt:

1. **Synonyme pro Begriff**: `SciFi` → `science fiction` usw. (Tabelle
   `SEARCH_SYNONYMS` in `server.py`).
2. **Zuerst striktes UND** (`Spielfilm science fiction`): Nur Einträge, die alle
   Begriffe enthalten — das liefert präzise Treffer.
3. **OR-Nachfüllen falls nötig**: Liefert das UND zu wenig (unter `n`)
   Treffer, werden weitere Treffer per OR aufgenommen (jeder Begriff einzeln),
   dedupliziert und MIT den UND-Treffern zuerst zurückgegeben.

Einzelne Begriffe mit weniger als 3 Zeichen fallen auf einen simplen LIKE-Scan
zurück (schnell, ausreichend für sehr kurze Eingaben).

---

## Sender-Erkennung (`senders.py`)

Im Dump ist das Sender-Feld bei rund 99 % der Einträge leer. Damit pro Treffer
trotzdem immer der Sender erscheint, wird er bei Bedarf aus der **Video-URL**
abgeleitet (genau wie MediathekView das intern tut):

- **Verzeichnis-Segmente zuerst** (eindeutiger): `/3sat/`, `/phoenix/`, …
- dann **Host-Muster**: `nrodlzdf-a`→ZDF, `srf-vod`→SRF, `arteptweb`→arte,
  `pdodswr-a`→SWR, `hrardmediathek`→hr, `pdvideosdaserste`→Das Erste …

Die Mapping-Tabellen stehen zentral in `senders.py` (`HOST_SENDER`,
`PATH_SENDER`) und sind leicht erweiterbar. Gemessen an 300.000 Einträgen werden
~99 % der URLs einem Sender zugeordnet; unklare Fälle bleiben leer (ehrlich
statt falsch).

---

## Neue Sender-Profile anlegen („Plugins“)

Jeder Sender hat eigene Regeln, aus den kompakten URL-Feldern (`url_klein`,
`url_hd` der Filmliste) volle URLs zu bauen. Diese Logik lebt in kleinen
Plugin-Dateien unter `profiles/`.

Ein neues Profil `profiles/<name>.py` hat diese Form:

```python
# METADATA bestimmt, wann das Profil zuständig ist.
METADATA = {
    "sender": ["BEISPIELSENDER"],        # optional: Sendernamen
    "url_regex": r"beispiel\.akamaihd\.net",   # optional: Host-Muster
}

def resolve(entry):
    """Liefere [{label, url}, ...] für einen Treffer."""
    url = entry.get("url") or ""
    if not url:
        return []
    out = [{"label": "Standard", "url": url}]
    # … sender-spezifisch SD/HD aus url_klein / url_hd bauen …
    return out
```

`entry` ist ein dict mit Feldern aus der Datenbank: `sender`, `titel`, `thema`,
`url`, `url_klein`, `url_hd`, `url_untertitel` …

Die Datei einfach in `profiles/` ablegen — der `resolver.py` lädt sie beim Start
automatisch (Dateiname = Profilname). Der Server selbst muss dafür **nicht**
angepasst werden und kann sogar einlaufen bleiben; ein Neustart genügt, damit
das neue Profil geladen wird.

---

## Hinweise & Grenzen

- **„Hörfilm/Audiodeskription“** liefert die Filmliste **nicht als eigene URL**
  mit. Die Filmliste bietet SD / Standard / HD und Untertitel. Eine separate
  Hörfilm-Tonspur ist im Video ggf. als unabhängiger Audiostream enthalten,
  wird aber nicht als eigener Download angeboten.
- Die kompakten HD/SD-Felder werden **best-effort** aufgelöst und pro Format
  kurz gegen den Server geprüft; falls eine Qualitäts-URL nicht auflösbar ist,
  bleibt die Standard-URL als sicherer Fall.
- Die Datenbankdatei `filmliste.db` darf erst nach dem ersten Ingest angefasst
  werden; während des „Neu laden“-Vorgangs einmalig längere Wartezeit
  einplanen.

#### Dieser  Code wurde mit Hilfe von KI optimiert
Powerd by ai, free-buff, DeepSeek
---

## Lizenz / License

**GNU Affero General Public License v3.0 oder später** (AGPL-3.0-or-later) —
vollständiger Text in [LICENSE](LICENSE).
Copyright (C) 2026 Olav Surawski (<https://github.com/o-valo>).

In Kurzform: benutzen, ändern und weitergeben ist frei erlaubt, solange
abgeleitete Fassungen wieder unter der AGPL stehen. Abschnitt 13 greift, wenn
eine **geänderte** Fassung als Netzdienst öffentlich erreichbar ist — dann muss
der Quellcode dieser Fassung den Nutzern zugänglich sein.

*Short version: use, modify and redistribute freely, as long as derived versions
stay under the AGPL. Section 13 applies if you make a modified version publicly
reachable as a network service.*
