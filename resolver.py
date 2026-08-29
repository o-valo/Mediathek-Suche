#!/usr/bin/env python3
"""
Resolver / Plugin-System für Sender-Profile.

Jeder Sender hat eigene Schemata für die kompakten URL-Felder (url_klein,
url_hd) der Filmliste. Statt diese Senderlogik fest in den Server zu
kleben, wird sie als kleines "Profil" (Plugin) geführt:

  profiles/
    <name>.py   → Modul mit:
        METADATA = {"sender": ["ZDF", "3sat", ...]  # optionale Sender-Namen
                     oder
                    "url_regex": r"..."}            # treffer auf Host/Pfad
        def resolve(entry) -> [{label, url}, ...]

        entry ist ein dict mit Feldern aus der DB: url, url_klein, url_hd,
        url_untertitel, sender, titel …

Der Resolver lädt alle Profile in profiles/ automatisch. Bei einer
Film-Zeile wird das erste passende Profil bestimmt; existiert keins,
greift das Fallback-Profil.
"""

import importlib
import os
import pkgutil
import re

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")


class ProfileNotFoundError(Exception):
    pass


class Profile:
    """Default-Wrapper um ein Profil-Modul."""

    def __init__(self, name, module):
        self.name = name
        self.module = module
        self.senders = set(module.METADATA.get("sender", []))
        regex = module.METADATA.get("url_regex")
        self.url_regex = re.compile(regex) if regex else None

    def matches(self, url, sender):
        if self.senders and sender and sender.strip().lower() in {s.lower() for s in self.senders}:
            return True
        if url and self.url_regex:
            # Regex auf Host + Pfad anwenden (Sender-Logik ist meist hostbasiert)
            if self.url_regex.search(url):
                return True
        return False

    def resolve(self, entry):
        return self.module.resolve(entry)


def _load_profiles():
    profiles = []
    for modinfo in pkgutil.iter_modules([PROFILES_DIR]):
        if modinfo.name == "fallback":
            continue  # Fallback zuletzt
        try:
            mod = importlib.import_module(f"profiles.{modinfo.name}")
            if hasattr(mod, "METADATA") and hasattr(mod, "resolve"):
                profiles.append(Profile(modinfo.name, mod))
        except Exception as e:  # fehlerhaftes Profil nicht alles zerbrechen lassen
            print(f"[resolver] Profil {modinfo.name} übersprungen: {e}", flush=True)
    # Fallback immer ans Ende
    try:
        fallback = importlib.import_module("profiles.fallback")
        profiles.append(Profile("fallback", fallback))
    except Exception as e:
        print(f"[resolver] Fallback-Profil fehlt oder defekt: {e}", flush=True)
    return profiles


PROFILES = _load_profiles()


def resolve_formats(entry):
    """Liefert [{label, url}, ...] für eine Film-Zeile über das passende Profil."""
    url = entry.get("url") or ""
    sender = entry.get("sender") or ""
    profile = None
    for p in PROFILES:
        if p.matches(url, sender):
            profile = p
            break
    profile = profile or PROFILES[-1]
    try:
        return profile.resolve(entry)
    except Exception as e:
        print(f"[resolver] {profile.name}.resolve fehlgeschlagen: {e}", flush=True)
        # sicherer Rückfall: nur die bekannte funktionierende URL
        return [{"label": "Standard", "url": url}] if url else []


def sender_for(entry):
    """Name des Profils, das diese Zeile bearbeitet (zu Debug-Zwecken)."""
    url = entry.get("url") or ""
    sender = entry.get("sender") or ""
    for p in PROFILES:
        if p.matches(url, sender):
            return p.name
    return PROFILES[-1].name


if __name__ == "__main__":
    print("Geladene Profile:")
    for p in PROFILES:
        print(f"  - {p.name}  (Sender: {sorted(p.senders)})")
    print(f"Gesamt: {len(PROFILES)}")