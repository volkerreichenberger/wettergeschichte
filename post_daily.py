#!/usr/bin/env python3
"""Täglicher Ablauf: Daten holen, Beiträge bauen, Bilder ablegen, veröffentlichen.

    ./post_daily.py                      Trockenlauf – baut alles, sendet nichts
    ./post_daily.py --upload-only        Bilder ablegen, aber nicht veröffentlichen
    ./post_daily.py --publish            wirklich veröffentlichen
    ./post_daily.py --variante drei-tage --stand 2026-08-05
    ./post_daily.py --variante bewoelkung --monat 2026-01 --publish

Einstellungen kommen aus ``post_daily.conf`` (Vorlage: ``post_daily.conf.example``).
Ohne diese Datei läuft nur der Trockenlauf – Absicht, so lässt sich der ganze Weg
prüfen, bevor Zugangsdaten im Spiel sind.

Für cron eignet sich das genauso wie ein Shell-Skript:

    0 11 * * *  cd ~/Programming/wettergeschichte && ./post_daily.py --publish

Rückgabewert 0, wenn alles lief; 1, wenn mindestens eine Variante scheiterte.
"""

from __future__ import annotations

import argparse
import os
import re
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONF = ROOT / "post_daily.conf"

#: Vorgabe, wenn post_daily.conf kein VARIANTE setzt.
STANDARD_VARIANTEN = "serie drei-tage bewoelkung regen-kumulativ"

#: Bauskript je Variante. Die Station kommt getrennt dazu.
VARIANTEN: dict[str, list[str]] = {
    "serie":       ["plots/python/nyt_post_matplotlib.py", "--zeitraum", "serie"],
    "nyt-jahr":    ["plots/python/nyt_post_matplotlib.py", "--zeitraum", "jahr"],
    "nyt-quartal": ["plots/python/nyt_post_matplotlib.py", "--zeitraum", "quartal"],
    "nyt-3monate": ["plots/python/nyt_post_matplotlib.py", "--zeitraum", "monate",
                    "--months", "3"],
    "drei-tage":   ["plots/python/drei_tage_matplotlib.py"],
    "bewoelkung":  ["plots/python/bewoelkung_matplotlib.py"],
    "regen-kumulativ": ["plots/python/regen_matplotlib.py", "--art", "kumulativ"],
}

#: Varianten, die nicht die Hauptstation nehmen. An 4931 fehlt der
#: Bedeckungsgrad von Juni 2022 bis August 2023 vollständig.
EIGENE_STATION = {"bewoelkung": "BEWOELKUNG_STATION"}

#: Ein Bauskript darf so enden, wenn es schlicht nichts zu tun gibt –
#: etwa ein Monat, der erst wenige Tage alt ist. Das ist kein Fehler.
NICHTS_ZU_TUN = 3

#: Diese Varianten brauchen keine Stundenwerte.
OHNE_STUNDENWERTE = {"bewoelkung", "regen-kumulativ"}


# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #

def lade_conf(path: Path) -> dict[str, str]:
    """Liest ``SCHLÜSSEL=WERT`` je Zeile.

    Das Format bleibt mit ``set -a; . ./post_daily.conf`` auch aus der Shell
    lesbar – nur ohne ``export`` und ohne mehrzeilige Werte, die eine
    Python-seitige Auswertung unnötig verwickelt machten. ``$NAME`` und
    ``${NAME}`` werden gegen bereits gelesene Schlüssel ersetzt.
    """
    werte: dict[str, str] = {}
    if not path.exists():
        return werte
    for zeile in path.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        zeile = re.sub(r"^export\s+", "", zeile)
        if "=" not in zeile:
            continue
        schluessel, _, wert = zeile.partition("=")
        werte[schluessel.strip()] = string.Template(wert_lesen(wert)).safe_substitute(werte)
    return werte


def wert_lesen(roh: str) -> str:
    """Entfernt Anführungszeichen und einen Kommentar am Zeilenende."""
    roh = roh.strip()
    if roh[:1] in ("'", '"'):
        zeichen = roh[0]
        ende = roh.find(zeichen, 1)
        return roh[1:ende] if ende > 0 else roh[1:]
    return roh.split(" #", 1)[0].strip()


def in_conf_schreiben(path: Path, schluessel: str, wert: str) -> None:
    """Ersetzt oder ergänzt eine Zeile in der Konfiguration."""
    zeilen = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    muster = re.compile(rf"^\s*(export\s+)?{re.escape(schluessel)}\s*=")
    neu, gefunden = [], False
    for zeile in zeilen:
        if muster.match(zeile):
            neu.append(f"{schluessel}={wert}")
            gefunden = True
        else:
            neu.append(zeile)
    if not gefunden:
        neu.append(f"{schluessel}={wert}")
    path.write_text("\n".join(neu) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Werkzeuge
# --------------------------------------------------------------------------- #

def lauf(befehl: list[str], leise: bool = False) -> tuple[int, str]:
    """Führt ein Kommando aus und gibt (Rückgabewert, Ausgabe) zurück."""
    ergebnis = subprocess.run(befehl, cwd=ROOT, capture_output=True, text=True)
    ausgabe = ergebnis.stdout + ergebnis.stderr
    if not leise and ausgabe.strip():
        for z in ausgabe.rstrip().splitlines():
            print(f"   {z}")
    return ergebnis.returncode, ausgabe


def abrufen(url: str) -> tuple[int, int]:
    """Holt eine URL und liefert (Status, Anzahl Bytes)."""
    try:
        with urllib.request.urlopen(url, timeout=30) as antwort:
            return antwort.status, len(antwort.read())
    except urllib.error.HTTPError as exc:
        return exc.code, 0
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, 0


def warte_auf_bild(url: str, datei: Path, sekunden: int, takt: int) -> bool:
    """Wartet, bis die URL das Bild in der lokalen Fassung ausliefert.

    Der Größenvergleich ist nötig, weil ein ersetztes Bild unter gleichem Namen
    sofort 200 liefert – aber noch mit dem alten Inhalt, den Instagram dann
    holen würde.
    """
    erwartet = datei.stat().st_size
    print(f"-- warte, bis das Bild ausgeliefert wird (bis zu {sekunden}s)")
    start = time.monotonic()
    status = groesse = 0
    while time.monotonic() - start < sekunden:
        status, groesse = abrufen(url)
        if status == 200 and groesse == erwartet:
            print(f"   erreichbar nach {round(time.monotonic() - start)}s")
            return True
        time.sleep(takt)
    print(f"   nach {sekunden}s nicht in der erwarteten Fassung da "
          f"(HTTP {status}, {groesse} statt {erwartet} Bytes)", file=sys.stderr)
    return False


# --------------------------------------------------------------------------- #
# Schritte
# --------------------------------------------------------------------------- #

def station_fuer(variante: str, conf: dict, station: str) -> str:
    schluessel = EIGENE_STATION.get(variante)
    if schluessel:
        return conf.get(schluessel, "4928")
    return station


def token_pruefen(conf: dict, min_tage: str, publish: bool) -> bool:
    """Verlängert das Token, wenn es bald abläuft. False heißt: Abbruch."""
    if not os.environ.get("IG_ACCESS_TOKEN"):
        return True
    print("-- Zugriffstoken")
    rc, ausgabe = lauf([sys.executable, "instagram_post.py", "--ensure-token",
                        "--conf", str(CONF), "--min-days", min_tage], leise=True)
    for zeile in ausgabe.rstrip().splitlines():
        if not zeile.startswith("IG_ACCESS_TOKEN="):
            print(f"   {zeile}")
    neu = [z[len("IG_ACCESS_TOKEN="):] for z in ausgabe.splitlines()
           if z.startswith("IG_ACCESS_TOKEN=")]
    if neu:
        os.environ["IG_ACCESS_TOKEN"] = neu[-1]
        return True
    if publish:
        print("   Token konnte nicht geprüft werden – Abbruch.", file=sys.stderr)
        return False
    return True


def daten_holen(varianten: list[str], conf: dict, station: str) -> None:
    """Holt die Daten aller Stationen, die irgendeine Variante braucht."""
    stationen: list[str] = []
    for variante in varianten:
        s = station_fuer(variante, conf, station)
        if s not in stationen:
            stationen.append(s)
    print(f"-- Daten holen (Stationen: {' '.join(stationen)})")
    lauf([sys.executable, "fetch_dwd.py", "--stations", *stationen])
    if set(varianten) - OHNE_STUNDENWERTE:
        lauf([sys.executable, "fetch_hourly.py", "--stations", station])

    print("-- Kennzahlen ableiten")
    # Auch das Vorjahr: die Quartalsserie reicht bis zu drei Quartale zurück.
    for jahr in (date.today().year - 1, date.today().year):
        lauf([sys.executable, "climatology.py", "--stations", station,
              "--year", str(jahr)])


def bilder_im_ordner(ordner: Path) -> list[Path]:
    """Einzelbild heißt bild.jpg, eine Serie bild_1.jpg … bild_n.jpg."""
    einzeln = ordner / "bild.jpg"
    if einzeln.exists():
        return [einzeln]
    return sorted(ordner.glob("bild_*.jpg"),
                  key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)))


def beitrag(variante: str, args, conf: dict) -> bool | None:
    """Baut, lädt hoch und veröffentlicht eine Variante.

    True = fertig, False = gescheitert, None = es gab nichts zu tun.
    """
    station = station_fuer(variante, conf, args.station)
    print(f"\n-- Beitrag bauen: {variante} (Station {station})")

    befehl = [sys.executable, *VARIANTEN[variante], "--station", station]
    if variante == "bewoelkung":
        # Die Monatsgrafik kennt keinen Stichtag, sondern einen Monat.
        if args.monat:
            befehl += ["--monat", args.monat]
        if args.force:
            befehl += ["--force"]
    elif args.stand:
        befehl += ["--stand", args.stand]
    rc, ausgabe = lauf(befehl)
    if rc == NICHTS_ZU_TUN:
        print(f"   {variante} übersprungen.")
        return None
    if rc != 0:
        print(f"   {variante} fehlgeschlagen (Rückgabewert {rc}).", file=sys.stderr)
        return False

    ordner = next((Path(z[len("POST_DIR="):]) for z in reversed(ausgabe.splitlines())
                   if z.startswith("POST_DIR=")), None)
    if ordner is None or not ordner.is_dir():
        print(f"   Beitragsordner nicht gefunden – {variante} übersprungen.",
              file=sys.stderr)
        return False

    text = ordner / "text.txt"
    bilder = bilder_im_ordner(ordner)
    if not text.exists() or not bilder:
        print(f"   Bild oder Text fehlt in {ordner}", file=sys.stderr)
        return False
    print(f"   {len(bilder)} Bild(er)")

    urls = bilder_ablegen(bilder, ordner, args, conf)
    if urls is None:
        return False

    return veroeffentlichen(urls, text, args)


def bilder_ablegen(bilder: list[Path], ordner: Path, args, conf: dict) -> list[str] | None:
    """Schiebt die Bilder an ihren öffentlichen Ort. None heißt: Abbruch."""
    befehl_vorlage = conf.get("WG_UPLOAD_CMD")
    url_vorlage = conf.get("WG_PUBLIC_URL")
    if not (befehl_vorlage and url_vorlage):
        print("-- Kein Upload konfiguriert (WG_UPLOAD_CMD / WG_PUBLIC_URL fehlen).")
        if args.publish:
            print("   Ohne öffentlich erreichbare Bild-URL kann nicht "
                  "veröffentlicht werden.", file=sys.stderr)
            return None
        return [f"https://BITTE-NOCH-EINTRAGEN.example/{b.name}" for b in bilder]

    print("-- Bilder ablegen")
    urls = []
    for bild in bilder:
        name = f"{ordner.name}_{bild.name}"
        urls.append(url_vorlage.replace("{name}", name))
        befehl = befehl_vorlage.replace("{src}", str(bild)).replace("{name}", name)
        if not args.upload:
            print(f"   {name} (Trockenlauf – nicht ausgeführt)")
            continue
        ergebnis = subprocess.run(befehl, shell=True, cwd=ROOT,
                                  capture_output=True, text=True)
        if ergebnis.returncode != 0:
            print(f"   {name}: Ablegen fehlgeschlagen\n{ergebnis.stderr.strip()}",
                  file=sys.stderr)
            return None
        print(f"   {name}")

    # Erst nach dem letzten Schub warten: der Bildspeicher wird ohnehin auf
    # einmal aktualisiert, geprüft wird das zuletzt hinzugefügte Bild.
    if args.upload:
        wartezeit = int(conf.get("WAIT_SECONDS", 300))
        takt = int(conf.get("WAIT_INTERVAL", 10))
        if not warte_auf_bild(urls[-1], bilder[-1], wartezeit, takt) and args.publish:
            print("   Abbruch vor dem Veröffentlichen.", file=sys.stderr)
            return None
    return urls


def veroeffentlichen(urls: list[str], text: Path, args) -> bool:
    print("-- Instagram")
    befehl = [sys.executable, "instagram_post.py", "--caption-file", str(text)]
    for url in urls:
        befehl += ["--image-url", url]
    if args.publish:
        befehl.append("--publish")
    rc, _ = lauf(befehl)
    return rc == 0


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    conf = lade_conf(CONF)
    for schluessel in ("IG_USER_ID", "IG_ACCESS_TOKEN", "IG_TOKEN_EXPIRES",
                       "IG_APP_SECRET"):
        if schluessel in conf:
            os.environ.setdefault(schluessel, conf[schluessel])

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--station", default=conf.get("STATION", "4931"))
    ap.add_argument("--variante", default=conf.get("VARIANTE", STANDARD_VARIANTEN),
                    help="eine oder mehrere, durch Leerzeichen getrennt")
    ap.add_argument("--stand", metavar="JJJJ-MM-TT",
                    help="Beitrag so bauen, wie er an diesem Tag ausgesehen hätte")
    ap.add_argument("--monat", metavar="JJJJ-MM",
                    help="nur bei bewoelkung: welcher Monat statt des laufenden")
    ap.add_argument("--force", action="store_true",
                    help="nur bei bewoelkung: einen abgeschlossenen Monat neu bauen")
    ap.add_argument("--publish", action="store_true",
                    help="wirklich veröffentlichen")
    ap.add_argument("--upload-only", dest="upload_only", action="store_true",
                    help="Bilder ablegen, aber nicht veröffentlichen")
    ap.add_argument("--skip-fetch", action="store_true",
                    help="keine DWD-Abfrage, nur neu bauen")
    args = ap.parse_args(argv)
    args.upload = args.publish or args.upload_only

    varianten = args.variante.split()
    unbekannt = [v for v in varianten if v not in VARIANTEN]
    if unbekannt:
        # Erst alle prüfen: ein Tippfehler soll nicht auffallen, nachdem der
        # erste Beitrag schon veröffentlicht ist.
        print(f"unbekannte Variante: {', '.join(unbekannt)}", file=sys.stderr)
        print(f"möglich: {' '.join(VARIANTEN)}", file=sys.stderr)
        return 2

    stand = f", Stand {args.stand}" if args.stand else ""
    print(f"== Wettergeschichte, Station {args.station}{stand}")
    print(f"   Varianten: {' '.join(varianten)}")

    if not token_pruefen(conf, conf.get("TOKEN_MIN_DAYS", "14"), args.publish):
        return 1

    if args.skip_fetch:
        print("-- Daten übersprungen (--skip-fetch)")
    else:
        daten_holen(varianten, conf, args.station)

    fehler = False
    for variante in varianten:
        if beitrag(variante, args, conf) is False:
            fehler = True

    if args.upload and not args.publish:
        print("\n== Bilder abgelegt, nicht veröffentlicht (--upload-only)")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
