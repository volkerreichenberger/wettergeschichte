#!/usr/bin/env python3
"""Baut die komplette Auswertung: Daten holen, Kennzahlen ableiten, alle Grafiken zeichnen.

    python run_all.py                       # alles, beide Stationen, aktuelles Jahr
    python run_all.py --skip-fetch          # ohne Netzzugriff, nur neu zeichnen
    python run_all.py --only matplotlib R   # nur bestimmte Varianten
    python run_all.py --year 2025 --stations 4931

Die Grafikvarianten sind bewusst austauschbar: erst alle bauen, dann in
``output/`` vergleichen und entscheiden, welche die beste ist.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

#: (Name, Kommando-Bausteine, unterstützt --station/--year?)
VARIANTS: list[tuple[str, list[str]]] = [
    ("matplotlib · NYT",        [sys.executable, "plots/python/nyt_matplotlib.py"]),
    ("matplotlib · NYT 3 Mon.", [sys.executable, "plots/python/nyt_matplotlib.py",
                                 "--months", "3"]),
    ("plotnine · NYT",          [sys.executable, "plots/python/nyt_plotnine.py"]),
    ("plotly · NYT",            [sys.executable, "plots/python/nyt_plotly.py"]),
    ("R ggplot2 · NYT",         ["Rscript", "plots/R/nyt_ggplot2.R"]),
    ("R lattice · NYT",         ["Rscript", "plots/R/nyt_lattice.R"]),
    ("R base · NYT",            ["Rscript", "plots/R/nyt_base.R"]),
    # Beiträge: quadratisch, ohne Text im Bild, je Beitrag ein Ordner in posts/
    ("Post · 3 Tage",           [sys.executable, "plots/python/drei_tage_matplotlib.py"]),
    ("Post · NYT Serie",        [sys.executable, "plots/python/nyt_post_matplotlib.py",
                                 "--zeitraum", "serie"]),
    ("Post · NYT Jahr",         [sys.executable, "plots/python/nyt_post_matplotlib.py",
                                 "--zeitraum", "jahr"]),
    ("Post · NYT Quartal",      [sys.executable, "plots/python/nyt_post_matplotlib.py",
                                 "--zeitraum", "quartal"]),
    ("Post · NYT 3 Monate",     [sys.executable, "plots/python/nyt_post_matplotlib.py",
                                 "--zeitraum", "monate", "--months", "3"]),
    # Regen: acht Blicke auf dieselbe Reihe, gewählt über --art.
    *[(f"Regen · {art}", [sys.executable, "plots/python/regen_matplotlib.py",
                          "--art", art])
      for art in ("kumulativ", "rueckstand", "schnee")],
    ("Instagram · NYT",         [sys.executable, "plots/python/instagram_card.py"]),
    ("Instagram · NYT 3 Mon.",  [sys.executable, "plots/python/instagram_card.py",
                                 "--months", "3"]),
    ("Instagram · 5 Jahre",     [sys.executable, "plots/python/instagram_card.py",
                                 "--chart", "fuenf_jahre"]),
]


def run(label: str, cmd: list[str]) -> bool:
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    took = time.monotonic() - started
    if proc.returncode == 0:
        print(f"  ✓ {label:<24} {took:5.1f}s")
        return True
    print(f"  ✗ {label:<24} {took:5.1f}s  – Fehler:")
    for line in (proc.stderr or proc.stdout).strip().splitlines()[-8:]:
        print(f"      {line}")
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stations", type=int, nargs="+", default=[4928, 4931])
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--skip-fetch", action="store_true", help="keine DWD-Abfrage, nur neu zeichnen")
    ap.add_argument("--only", nargs="+", metavar="MUSTER",
                    help="nur Varianten, deren Name eines der Muster enthält")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args(argv)

    ok = True

    if not args.skip_fetch:
        print("Daten vom DWD holen")
        ok &= run("fetch_dwd", [sys.executable, "fetch_dwd.py",
                                "--stations", *map(str, args.stations)])
        ok &= run("fetch_hourly", [sys.executable, "fetch_hourly.py",
                                   "--stations", *map(str, args.stations)])

    print("\nKennzahlen ableiten")
    # Auch das Vorjahr: die Quartalsserie reicht bis zu drei Quartale zurück.
    for year in (args.year - 1, args.year):
        ok &= run(f"climatology {year}", [sys.executable, "climatology.py",
                                          "--year", str(year),
                                          "--stations", *map(str, args.stations)])

    variants = VARIANTS
    if args.only:
        variants = [v for v in VARIANTS if any(m.lower() in v[0].lower() for m in args.only)]
        if not variants:
            print(f"kein Treffer für --only {' '.join(args.only)}")
            return 2

    for station in args.stations:
        print(f"\nGrafiken für Station {station}, Jahr {args.year}")
        for label, cmd in variants:
            ok &= run(label, [*cmd, "--station", str(station), "--year", str(args.year),
                              "--dpi", str(args.dpi)])

    print(f"\nVergleichsbilder in {ROOT / 'output'}, "
          f"Beitraege in {ROOT / 'posts'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
