#!/usr/bin/env python3
"""Prüft, ob auf diesem Rechner alles da ist, was der tägliche Ablauf braucht.

Gedacht für den Umzug auf einen neuen Rechner: erst hier durchlaufen lassen,
dann ``post_daily.py``. Das Skript ändert nichts und geht nur für die
Netzprüfung ins Internet.

    python3 check_setup.py
    python3 check_setup.py --keine-netzpruefung
    python3 check_setup.py --alles          # auch die Vergleichsvarianten

Drei Stufen: **fehlt** bricht den täglichen Ablauf, **Hinweis** verändert nur
das Ergebnis oder betrifft eine Nebenvariante, **ok** ist in Ordnung.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

#: Ohne diese läuft kein einziger Beitrag.
KERN = {
    "pandas": "2.0",
    "numpy": "1.24",
    "matplotlib": "3.7",
}

#: Nur für die Vergleichsvarianten aus run_all.py.
KUER = {
    "plotnine": "plots/python/nyt_plotnine.py",
    "plotly": "plots/python/nyt_plotly.py",
    "kaleido": "PNG-Export für plotly",
}

R_PAKETE = ["ggplot2", "lattice", "ragg"]

#: Schlüssel, die post_daily.conf gesetzt haben muss. Werte werden nie
#: ausgegeben – die Datei enthält Zugriffstoken und den App-Geheimcode.
CONF_PFLICHT = ["STATION", "VARIANTE", "WG_UPLOAD_CMD", "WG_PUBLIC_URL"]
CONF_ZUM_VEROEFFENTLICHEN = ["IG_ACCESS_TOKEN", "IG_USER_ID", "IG_APP_SECRET"]

MINDEST_PYTHON = (3, 10)


class Bericht:
    def __init__(self) -> None:
        self.fehlt: list[str] = []
        self.hinweise: list[str] = []

    def ok(self, was: str, zusatz: str = "") -> None:
        print(f"  ok      {was}" + (f"  ({zusatz})" if zusatz else ""))

    def hinweis(self, was: str, rat: str) -> None:
        print(f"  Hinweis {was}")
        print(f"          → {rat}")
        self.hinweise.append(was)

    def fehler(self, was: str, rat: str) -> None:
        print(f"  FEHLT   {was}")
        print(f"          → {rat}")
        self.fehlt.append(was)


def version_von(modul) -> str:
    return getattr(modul, "__version__", "?")


def zu_alt(ist: str, mindestens: str) -> bool:
    def teile(v: str):
        return [int(t) for t in v.split(".")[:2] if t.isdigit()]
    a, b = teile(ist), teile(mindestens)
    return bool(a) and a < b


# --------------------------------------------------------------------------- #

def pruefe_python(b: Bericht) -> None:
    print("\nPython")
    ist = sys.version_info[:2]
    if ist < MINDEST_PYTHON:
        b.fehler(f"Python {ist[0]}.{ist[1]}",
                 f"mindestens {MINDEST_PYTHON[0]}.{MINDEST_PYTHON[1]} – die "
                 f"Skripte benutzen 'X | None' in Typangaben")
    else:
        b.ok(f"Python {ist[0]}.{ist[1]}")


def pruefe_module(b: Bericht, alles: bool) -> None:
    print("\nPython-Pakete")
    for name, mindestens in KERN.items():
        try:
            modul = importlib.import_module(name)
        except ImportError:
            b.fehler(name, f"pip install '{name}>={mindestens}'")
            continue
        v = version_von(modul)
        if zu_alt(v, mindestens):
            b.hinweis(f"{name} {v}", f"älter als {mindestens} – "
                                     f"pip install -U '{name}>={mindestens}'")
        else:
            b.ok(name, v)

    if not alles:
        return
    for name, wofuer in KUER.items():
        try:
            modul = importlib.import_module(name)
        except ImportError:
            b.hinweis(f"{name} fehlt", f"nur für {wofuer} – pip install {name}")
        else:
            b.ok(name, version_von(modul))


def pruefe_schrift(b: Bericht) -> None:
    """Die stille Falle beim Rechnerwechsel.

    Die Beiträge sind in Myriad Pro Condensed gesetzt. Fehlt sie, nimmt
    matplotlib klaglos DejaVu Sans – die Bilder entstehen, sehen aber anders
    aus als alles bisher Veröffentlichte. Ohne Prüfung fällt das erst auf
    Instagram auf.
    """
    print("\nSchrift")
    sys.path.insert(0, str(ROOT / "plots" / "python"))
    try:
        import matplotlib.font_manager as fm
        import wg_common as wg
    except ImportError as exc:
        b.hinweis(f"Schrift nicht prüfbar ({exc})", "erst die Pakete installieren")
        return

    for name in wg.FONT_FAMILY:
        try:
            pfad = fm.findfont(fm.FontProperties(family=name, stretch=wg.FONT_STRETCH),
                               fallback_to_default=False)
        except ValueError:
            continue
        if name in wg.FONT_GEWOLLT:
            b.ok(f"{name} ({wg.FONT_STRETCH})", pfad)
        else:
            b.hinweis(
                f"nur {name} vorhanden – keine der gewollten Schriften",
                "Die Bilder entstehen trotzdem, sehen aber anders aus als die "
                "bisher veröffentlichten. Abhilfe: Fira Sans installieren "
                "(Debian/Ubuntu: 'apt search fira' oder von fonts.google.com "
                "nach ~/.local/share/fonts/), dann 'fc-cache -f' und "
                "'rm -rf ~/.cache/matplotlib'. Auf dem Mac tut es "
                "MyriadPro-Cond.otf.")
        return

    b.hinweis("keine der vorgesehenen Schriften gefunden",
              "matplotlib nimmt DejaVu Sans – siehe oben")


def pruefe_git(b: Bericht) -> None:
    print("\ngit")
    if not shutil.which("git"):
        b.fehler("git", "apt install git (oder das Äquivalent der Distribution)")
        return
    b.ok("git", subprocess.run(["git", "--version"], capture_output=True,
                               text=True).stdout.strip())

    haken = subprocess.run(["git", "config", "core.hooksPath"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if haken == "hooks":
        b.ok("pre-commit-Haken aktiv")
    else:
        b.hinweis("pre-commit-Haken nicht aktiv",
                  "git config core.hooksPath hooks — er hält Zugangsdaten aus "
                  "dem Repository heraus und wird je Arbeitskopie eingestellt")


def conf_lesen() -> dict:
    sys.path.insert(0, str(ROOT))
    from post_daily import lade_conf
    return lade_conf(ROOT / "post_daily.conf")


def pruefe_conf(b: Bericht) -> dict:
    print("\npost_daily.conf")
    pfad = ROOT / "post_daily.conf"
    if not pfad.exists():
        b.fehler("post_daily.conf fehlt",
                 "cp post_daily.conf.example post_daily.conf und ausfüllen")
        return {}

    modus = pfad.stat().st_mode & 0o077
    if modus:
        b.hinweis(f"post_daily.conf ist für andere lesbar ({oct(pfad.stat().st_mode)[-3:]})",
                  "chmod 600 post_daily.conf — die Datei enthält das Zugriffstoken")
    else:
        b.ok("Zugriffsrechte 600")

    conf = conf_lesen()
    for schluessel in CONF_PFLICHT:
        if conf.get(schluessel):
            b.ok(schluessel, "gesetzt")
        else:
            b.fehler(f"{schluessel} fehlt in post_daily.conf", "Wert eintragen")
    for schluessel in CONF_ZUM_VEROEFFENTLICHEN:
        if conf.get(schluessel):
            b.ok(schluessel, "gesetzt")
        else:
            b.hinweis(f"{schluessel} fehlt in post_daily.conf",
                      "ohne den Schlüssel laufen nur Trockenläufe")
    return conf


def pruefe_bildablage(b: Bericht, conf: dict) -> None:
    """Die Bilder liegen in einem zweiten Repository, das mitgeklont sein muss."""
    print("\nBildablage")
    ziel = conf.get("BILDER")
    if not ziel:
        if "{src}" in conf.get("WG_UPLOAD_CMD", ""):
            b.hinweis("BILDER nicht gesetzt",
                      "WG_UPLOAD_CMD verweist auf ein Verzeichnis, das in der "
                      "Konfiguration fehlt")
        return

    pfad = Path(os.path.expanduser(ziel))
    if not pfad.is_dir():
        b.fehler(f"{pfad} fehlt",
                 "git clone https://github.com/volkerreichenberger/"
                 "wettergeschichtebilder.git — und BILDER in post_daily.conf "
                 "auf den Pfad auf diesem Rechner setzen")
        return
    b.ok(f"{pfad} vorhanden")

    if not (pfad / ".git").exists():
        b.fehler(f"{pfad} ist kein git-Repository",
                 "WG_UPLOAD_CMD committet und pusht dort hinein")
        return

    remote = subprocess.run(["git", "-C", str(pfad), "remote", "-v"],
                            capture_output=True, text=True).stdout
    if "push" in remote:
        b.ok("Bildablage hat ein Remote")
    else:
        b.fehler("Bildablage hat kein Remote", "git remote add origin …")

    # Ein Push braucht hinterlegte Zugangsdaten; das lässt sich nur mit einem
    # echten Netzzugriff feststellen, deshalb hier nur der Hinweis.
    b.hinweis("Push in die Bildablage nicht geprüft",
              f"einmal von Hand testen: git -C {pfad} push — ohne "
              "hinterlegte Zugangsdaten bleibt post_daily.py hier hängen")


def pruefe_daten(b: Bericht) -> None:
    print("\nDaten")
    stationen = sorted((ROOT / "data" / "stations").glob("*/daily.csv")) \
        if (ROOT / "data" / "stations").is_dir() else []
    if not stationen:
        b.hinweis("noch keine DWD-Daten geholt",
                  "python3 fetch_dwd.py --stations 4931 4928 && "
                  "python3 fetch_hourly.py --stations 4931 — die Rohdaten "
                  "liegen nicht im Repository")
        return
    for pfad in stationen:
        b.ok(f"{pfad.parent.name}/daily.csv")

    derived = ROOT / "data" / "derived"
    if derived.is_dir() and list(derived.glob("climatology_*.csv")):
        b.ok("abgeleitete Kennzahlen vorhanden")
    else:
        b.hinweis("keine abgeleiteten Kennzahlen",
                  "python3 climatology.py --year <Jahr> — post_daily.py macht "
                  "das sonst beim ersten Lauf selbst")


def pruefe_netz(b: Bericht) -> None:
    print("\nNetz")
    for name, url in (("DWD", "https://opendata.dwd.de/climate_environment/CDC/"),
                      ("Instagram-API", "https://graph.instagram.com/")):
        try:
            with urllib.request.urlopen(url, timeout=15) as antwort:
                b.ok(name, f"HTTP {antwort.status}")
        except urllib.error.HTTPError as exc:
            # Die API antwortet ohne Token mit 4xx – erreichbar ist sie damit.
            b.ok(name, f"HTTP {exc.code}, erreichbar")
        except Exception as exc:
            b.fehler(f"{name} nicht erreichbar ({exc})", "Netzverbindung prüfen")


def pruefe_r(b: Bericht) -> None:
    print("\nR (nur für die Vergleichsvarianten)")
    if not shutil.which("Rscript"):
        b.hinweis("Rscript fehlt",
                  "nur für plots/R/* nötig; der tägliche Ablauf braucht es nicht")
        return
    b.ok("Rscript")
    for paket in R_PAKETE:
        rc = subprocess.run(["Rscript", "-e", f"library({paket})"],
                            capture_output=True).returncode
        if rc == 0:
            b.ok(f"R-Paket {paket}")
        else:
            b.hinweis(f"R-Paket {paket} fehlt",
                      f"Rscript -e 'install.packages(\"{paket}\")'")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keine-netzpruefung", action="store_true",
                    dest="ohne_netz", help="nicht ins Internet gehen")
    ap.add_argument("--alles", action="store_true",
                    help="auch die Vergleichsvarianten prüfen (plotnine, plotly, R)")
    args = ap.parse_args(argv)

    print(f"Wettergeschichte – Umgebung prüfen\n{ROOT}")
    b = Bericht()
    pruefe_python(b)
    pruefe_module(b, args.alles)
    pruefe_schrift(b)
    pruefe_git(b)
    conf = pruefe_conf(b)
    pruefe_bildablage(b, conf)
    pruefe_daten(b)
    if not args.ohne_netz:
        pruefe_netz(b)
    if args.alles:
        pruefe_r(b)

    print("\n" + "-" * 60)
    if b.fehlt:
        print(f"{len(b.fehlt)} Sache(n) fehlen – der tägliche Ablauf läuft so nicht:")
        for z in b.fehlt:
            print(f"  · {z}")
    if b.hinweise:
        print(f"{len(b.hinweise)} Hinweis(e):")
        for z in b.hinweise:
            print(f"  · {z}")
    if not b.fehlt and not b.hinweise:
        print("Alles da.")
    elif not b.fehlt:
        print("\nNichts Blockierendes. Nächster Schritt: ./post_daily.py --skip-fetch")
    return 1 if b.fehlt else 0


if __name__ == "__main__":
    sys.exit(main())
