"""
ZDF / 3sat Profil.

Erweitert das generische Fallback: Bei ZDF kann der Host im Klein-Feld dem
vollen Host entsprechen (rodlzdf-a vs. nrodlzdf-a) — beide sprechen dieselbe
Basis an, daher ist die einfache "https://" + Rest-Regel hier korrekt.

Falls die kompakte Klein-URL nicht mit "akamaihd" beginnt, übernehmen wir
den Host der vollen URL.
"""

import re

from profiles import fallback

METADATA = {
    "sender": ["ZDF", "3sat", "ZDFinfo", "ZDFneo", "PHOENIX", "KiKA"],
    "url_regex": r"n?rodlzdf-a\.akamaihd\.net",
}


def resolve(entry):
    result = fallback.resolve(entry)
    if not result:
        return result
    full = entry.get("url") or ""
    # SD-Host prüfen: falls er gar nicht wie ein CDN aussieht, Host der vollen URL nehmen
    for fmt in result:
        if fmt["label"] == "SD" and full:
            host = full.split("/")[2]
            klein = fmt["url"]
            if "akamaihd" not in klein and host:
                fmt["url"] = klein.replace("https://", f"https://{host}/", 1) if klein.startswith("https://") else klein
    return result