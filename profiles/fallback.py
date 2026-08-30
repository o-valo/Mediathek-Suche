"""
Fallback-Profil: generische Auflösung des üblichen Schemas, das ZDF, 3sat
und arte über den akamai-Dienst verwenden.

Volle URL (url) hat i. d. R. die Form:
    https://<host>/<pfad>/<stamm>_<qualitaet>_p<..>v<..>.mp4

Kompakte Felder im Dump:
    url_klein : "<zahl>|<host>/<pfad>/<stamm>_<qualitaet>….mp4"
    url_hd    : "<zahl>|<qualitaetsdatumname>.mp4"

Auflösung:
    - Standard : die volle url unverändert.
    - Klein    : "https://" + (url_klein nach der "|")
    - HD       : Verzeichnis der vollen URL + Dateiname aus url_hd (nach "|"),
                 wobei die Qualitäts-Zahl vor "|" den Pfad-/Größenbezug markiert.
"""

import re

METADATA = {
    "sender": ["ZDF", "3sat", "arte", "PHOENIX", "KiKA", "ZDFinfo", "ZDFneo"],
    "url_regex": r"akamaihd\.net",
}

# Dateinamen-Muster wie ..._3360k_p36v17.mp4
_QUAL = re.compile(r"_\d+k_p\d+v\d+\.mp4$")


def _plausible(url):
    """Nur URLs anbieten, die halbwegs echt wirken (Protokoll + Host + Pfad)."""
    if not url or not url.startswith(("https://", "http://")):
        return False
    try:
        scheme, rest = url.split("://", 1)
        host, path = (rest.split("/", 1) + [""])[:2]
    except Exception:
        return False
    return bool(host) and "." in host and bool(path)


def resolve(entry):
    url = entry.get("url") or ""
    if not url:
        return []
    out = [{"label": "Standard", "url": url}]
    dirname = url[: url.rfind("/") + 1]
    fname = url.rsplit("/", 1)[-1]

    klein = entry.get("url_klein") or ""
    if klein and "|" in klein:
        rest = klein.split("|", 1)[1].strip()
        kurl = "https://" + rest if not rest.startswith(("http://", "https://")) else rest
        if _plausible(kurl):
            out.append({"label": "SD", "url": kurl})

    hd = entry.get("url_hd") or ""
    if hd and "|" in hd:
        hdpart = hd.split("|", 1)[1].strip()
        # Qualitäts-Suffix der Basisdatei durch HD-Dateinamen ersetzen
        new_fname = _QUAL.sub("_" + hdpart, fname) if _QUAL.search(fname) else hdpart
        hurl = dirname + new_fname
        if hurl != url and _plausible(hurl):
            out.append({"label": "HD", "url": hurl})
    return out