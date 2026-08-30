"""
ARD-Profil (SWR, WDR, NDR, BR, MDR, hr, SR, rbb …).

Die ARD-Anstalten verwenden Dateinamen mit Qualitäts-Suffix:
    http…/<id>.l.mp4    → niedrig (SD)
    http…/<id>.ml.mp4   → mittel
    http…/<id>.xxl.mp4  → hoch (HD)

Die kompakten Felder geben nur das Suffix als Namen an:
    url_klein : "<zahl>|ml.mp4"   (oder leer / schon full)
    url_hd    : "<zahl>|xxl.mp4"

Auflösung: Die Qualitäts-Endung der vollständigen Standard-URL wird durch
das jeweilige Suffix ersetzt; das Verzeichnis & der Basis-Dateiname bleiben
erhalten. Falls ein Feld schon eine volle URL enthält, wird sie direkt
verwendet.
"""

import re

METADATA = {
    "sender": ["ARD", "SWR", "BR", "WDR", "NDR", "MDR", "SR", "hr", "rbb"],
    "url_regex": r"pdodswr-a\.akamaihd\.net",
}

# endung wie ".mp4", könnte mehrfach vorkommen; wir ersetzen nur letzten
# Qualitäts-Teil: <id>.<qual>.mp4  → wir nehmen alles bis vor dem letzten ".mp4"
_QUALITY = re.compile(r"\.mp4$")


def _replace_qual(fname, suffix):
    """Ersetzt die Qualitäts-Endung des Dateinamens durch einen neuen Namen.

    z. B. "1658497.l.mp4" + "xxl.mp4" → "1658497.xxl.mp4"
    z. B. "foo.mp4"        + "bar.mp4" → "bar.mp4" (nur wenn kein Qual-Struktur)
    """
    base = _QUALITY.sub("", fname)  # ohne .mp4
    if "." in base and len(base.split("/")[-1]) > 3:
        # <id>.<qual> → andere Qualität
        return base[: base.rfind(".") + 1] + suffix
    return fname


def _plausible(url):
    if not url or not url.startswith(("https://", "http://")):
        return False
    try:
        _, rest = url.split("://", 1)
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

    # Klein / SD
    klein = entry.get("url_klein") or ""
    if klein:
        rest = klein.split("|", 1)[1].strip() if "|" in klein else klein.strip()
        if rest.startswith(("http://", "https://")):
            if _plausible(rest) and rest != url:
                out.append({"label": "SD", "url": rest})
        elif rest.endswith(".mp4"):
            sd = dirname + _replace_qual(fname, rest)
            if _plausible(sd) and sd != url:
                out.append({"label": "SD", "url": sd})

    # HD
    hd = entry.get("url_hd") or ""
    if hd:
        hrest = hd.split("|", 1)[1].strip() if "|" in hd else hd.strip()
        if hrest.startswith(("http://", "https://")):
            if _plausible(hrest) and hrest != url:
                out.append({"label": "HD", "url": hrest})
        elif hrest.endswith(".mp4"):
            hurl = dirname + _replace_qual(fname, hrest)
            if _plausible(hurl) and hurl != url:
                out.append({"label": "HD", "url": hurl})
    return out
  
