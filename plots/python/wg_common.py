"""Gemeinsame Farben, Texte und Datenzugriffe für alle Python-Grafiken.

Alle Varianten (matplotlib, plotnine, plotly) lesen dieselben CSVs aus
``data/derived/`` und benutzen dieselbe Palette – so unterscheiden sich die
Bilder nur in der Umsetzung, nicht in den Zahlen.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
OUTPUT = ROOT / "output"

# --------------------------------------------------------------------------- #
# Palette – an das NYT-Original angelehnt
# --------------------------------------------------------------------------- #

BACKGROUND = "#ffffff"
PANEL = "#faf8f4"
RECORD_BAND = "#e6e2d8"
NORMAL_BAND = "#b7a583"
BAR_NEUTRAL = "#4c4c4c"
WARM = "#c0392b"
COLD = "#2c6fa8"
GRID = "#d8d4cb"
TEXT = "#1a1a1a"
TEXT_MUTED = "#6b6b6b"

#: Farbverlauf für die Fünf-Jahres-Grafik: ältere Jahre blass, aktuelles Jahr kräftig.
YEAR_COLORS = ["#cfc9bd", "#a9c0d4", "#7ea6c6", "#d98b6a", "#b32d22"]

MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
MONTH_NAMES_LONG = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
#: Montag = 0, wie bei ``datetime.weekday()``.
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WEEKDAYS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

#: Farbe der aktuellen Kurve im Drei-Tages-Bild (RGB 35, 102, 202).
CURRENT_BLUE = "#2366ca"
#: Erster Tag jedes Monats im 365-Tage-Schema (siehe climatology.doy_no_leap).
MONTH_STARTS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONTH_END = 366

SOURCE_NOTE = "Datenquelle: Deutscher Wetterdienst, Climate Data Center (opendata.dwd.de)"

#: Schlusszeile aller Begleittexte – bewusst nur drei Stück.
HASHTAGS = "#wetter #wettergeschichte #stuttgart"

#: Wie die Station im Begleittext heißt. Der amtliche Name sagt Ortsfremden
#: wenig; er steht dafür weiter unten in der Quellenangabe.
DISPLAY_NAMES = {4931: "Stuttgart (Süd)"}


def display_name(station_id: int, amtlich: str | None = None) -> str:
    """Anzeigename für Überschriften; sonst der amtliche Name."""
    return DISPLAY_NAMES.get(int(station_id), amtlich or f"Station {station_id}")


def quelle(station_id: int, amtlich: str, stand: str) -> str:
    """Quellenangabe – hier steht, welche Station wirklich gemeint ist."""
    return (
        f"Gemessen wird an der Station {station_id} {amtlich} des Deutschen "
        f"Wetterdienstes.\nDaten: DWD Climate Data Center (opendata.dwd.de), "
        f"Stand {stand}."
    )

# --------------------------------------------------------------------------- #
# Schrift
# --------------------------------------------------------------------------- #

#: Erste Wahl ist Myriad Pro; die Übrigen springen ein, wo sie nicht liegt.
FONT_FAMILY = ["Myriad Pro", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

#: Zusammen mit der Familie wählt das den schmalen Schnitt aus
#: (/Library/Fonts/MyriadPro-Cond.otf). Fehlt ein schmaler Schnitt, nimmt
#: matplotlib den nächstbesten – die Grafik bricht deswegen nicht.
FONT_STRETCH = "condensed"


def rc_font() -> dict:
    """rcParams für die Schrift, für alle matplotlib-Skripte gleich."""
    return {
        "font.family": "sans-serif",
        "font.sans-serif": FONT_FAMILY,
        "font.stretch": FONT_STRETCH,
    }


# --------------------------------------------------------------------------- #
# Daten
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Deutsche Formatierung – unabhängig vom Locale des Rechners
# --------------------------------------------------------------------------- #


def de_num(value: float, decimals: int = 1, sign: bool = False) -> str:
    """Zahl mit Dezimalkomma, optional mit erzwungenem Vorzeichen."""
    fmt = f"{{:{'+' if sign else ''}.{decimals}f}}"
    return fmt.format(value).replace(".", ",")


def de_date(d) -> str:
    """'27. Juni' – ohne Abhängigkeit von einem installierten de_DE-Locale."""
    return f"{d.day}. {MONTH_NAMES_LONG[d.month - 1]}"


def load(station_id: int, year: int, derived: Path = DERIVED):
    """Liefert (climatology, year_df, recent_df, summary_dict)."""
    tag = f"{station_id:05d}"
    missing = [
        p
        for p in (
            derived / f"climatology_{tag}.csv",
            derived / f"year_{tag}_{year}.csv",
            derived / f"recent_{tag}_{year}.csv",
            derived / f"summary_{year}.csv",
        )
        if not p.exists()
    ]
    if missing:
        raise SystemExit(
            "Abgeleitete Daten fehlen:\n  "
            + "\n  ".join(str(p) for p in missing)
            + f"\nBitte 'python climatology.py --year {year}' laufen lassen."
        )

    clim = pd.read_csv(derived / f"climatology_{tag}.csv", parse_dates=["label_date"])
    year_df = pd.read_csv(derived / f"year_{tag}_{year}.csv", parse_dates=["date"])
    recent = pd.read_csv(derived / f"recent_{tag}_{year}.csv", parse_dates=["date"])
    summary_all = pd.read_csv(derived / f"summary_{year}.csv")
    summary = summary_all[summary_all["station_id"] == station_id].iloc[0].to_dict()
    return clim, year_df, recent, summary


def station_name(station_id: int, data_dir: Path = ROOT / "data") -> str:
    """Klarname der Station aus den Stammdaten; notfalls die Nummer selbst."""
    path = data_dir / "stations.csv"
    if path.exists():
        stations = pd.read_csv(path)
        hit = stations[stations["station_id"] == station_id]
        if len(hit):
            return str(hit.iloc[0]["name"])
    return f"Station {station_id}"


def subtitle(summary: dict) -> str:
    return (
        f"Tägliche Höchst- und Tiefsttemperaturen {summary['year']} "
        f"im Vergleich zur Normalperiode {summary['reference_from']}–{summary['reference_to']} "
        f"und zu den Rekorden seit {summary['record_from']}"
    )


def footer(summary: dict) -> str:
    return (
        f"{SOURCE_NOTE}  ·  Station {summary['station_id']}  ·  "
        f"Stand {summary['last_date']}"
    )


def stats_line(summary: dict) -> str:
    return (
        f"Jahresmittel bisher {de_num(summary['temp_mean'])} °C "
        f"({de_num(summary['anomaly'], sign=True)} K zur Normalperiode)   ·   "
        f"Höchstwert {de_num(summary['temp_max'])} °C   ·   "
        f"Tiefstwert {de_num(summary['temp_min'])} °C   ·   "
        f"{summary['days_above_30']} Tage ≥ 30 °C   ·   "
        f"{summary['frost_days']} Frosttage"
    )


def out_path(name: str, station_id: int, year: int, ext: str = "png", output: Path = OUTPUT) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    return output / f"{name}_{station_id:05d}_{year}.{ext}"


POSTS = ROOT / "posts"


def post_dir(slug: str, base: Path = POSTS) -> Path:
    """Ein Ordner je Beitrag – darin liegen Bild und Begleittext beieinander.

    Das spätere Upload-Skript muss dann nur noch auf das Verzeichnis zeigen.
    """
    path = base / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def cli(description: str) -> argparse.ArgumentParser:
    """Einheitliche Kommandozeile für alle Plot-Skripte."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--station", type=int, default=4931, help="DWD-Stations-ID (4928 oder 4931)")
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--derived", type=Path, default=DERIVED)
    ap.add_argument("--output", type=Path, default=OUTPUT)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    return ap
