#!/usr/bin/env python3
"""
Sender-Erkennung aus Video-URLs.

Die Filmliste liefert den Sender nur in sehr wenigen Zeilen (die `sender`-
Spalte ist fast immer leer). Praktikabel: Den Sender aus dem URL-Host bzw.
Verzeichnispfad ableiten. Diese Zuordnung wird von MediathekView ebenfalls
so gehandhabt.

Reihenfolge:
  1. Host-basierte Regeln (genauer), z. B. nrodlzdf-a → ZDF, pdodswr-a → SWR.
  2. Verzeichnis-Segment-Mapping zeitlich NUR, wenn es eindeutig ist
     (nur 3sat/phoenix/etc. — nicht generische "zdf", um Falschtreffer zu meiden).
  3. sonst leer.
"""

# host-Substring → Sender (zuerst geprüft, weil zuverlässig)
HOST_SENDER = [
    # SRF
    ("srf-vod", "SRF"),
    ("srstorage01", "SRF"),
    # arte
    ("arte.tv", "arte"),
    ("arteptweb", "arte"),
    ("artemediathek", "arte"),
    ("arteedurable", "arte"),
    ("arteconcert", "arte"),
    ("arte.gl-systemhaus", "arte"),
    # ARD-Block
    ("pdodswr-a", "SWR"),
    ("swr.de", "SWR"),
    ("hrardmediathek", "hr"),
    ("mediastorage01.sr-online", "SR"),
    ("rbprogressive", "rbb"),
    ("daserste.de", "Das Erste"),
    ("ndr", "NDR"),
    ("mdr", "MDR"),
    ("br.", "BR"),
    ("wdr", "WDR"),
    ("rbb", "rbb"),
    ("planetschule", "Planet Schule"),
    # ARD-Mediensammlung (funk, Sportschau, tagesschau, avod)
    ("funk", "funk"),
    ("sportschau", "Sportschau"),
    ("tagesschau", "tagesschau.de"),
    ("avod.ard", "ARD"),
    ("ard-mcdn", "ARD"),
    # ZDF
    ("nrodlzdf-a", "ZDF"),
    ("rodlzdf-a", "ZDF"),
    ("tvdlzdf-a", "ZDF"),
    # DW
    ("dw.com", "DW"),
    ("tvdownloaddw", "DW"),
    # ARD-Feinschliff
    ("pdvideosdaserste", "Das Erste"),
    ("radiobremen", "Radio Bremen"),
    ("kika", "KiKA"),
    ("hr.gl-systemhaus", "hr"),
    ("brvod", "BR"),
]

# Verzeichnis-Segmente, die eindeutig genug sind, um sie als Sender zu werten.
# Absichtlich eng, um Falschtreffer (z. B. generisches 'zdf') zu vermeiden.
PATH_SENDER = [
    ("/3sat/", "3sat"),
    ("/phoenix/", "Phoenix"),
    ("/kika/", "KiKA"),
    ("/arte/", "arte"),
    ("/zdfinfo/", "ZDFinfo"),
    ("/zdfneo/", "ZDFneo"),
]


def detect_sender(url):
    if not url:
        return ""
    low = url.lower()
    # 1) Verzeichnis-Segmente ZUERST: sie sind eindeutiger als der Host
    #    (z. B. /dach/3sat/ trotz nrodlzdf-a-Host → 3sat, nicht ZDF).
    for needle, name in PATH_SENDER:
        if needle in low:
            return name
    # 2) Host-basiert
    for needle, name in HOST_SENDER:
        if needle in low:
            return name
    return ""


if __name__ == "__main__":
    for u in [
        "https://nrodlzdf-a.akamaihd.net/dach/3sat/24/10/x_3360k_p36v17.mp4",
        "https://pdodswr-a.akamaihd.net/swrfernsehen/aus-den-studios/1658497.xxl.mp4",
        "https://srf-vod-amd.akamaized.net/ch/hls/x/4/h.m3u8",
        "https://www.arte.tv/de/videos/RC/foo.mp4",
        "https://unbekannt.example.org/x/y.mp4",
    ]:
        print(f"{detect_sender(u):8} <- {u[:60]}")