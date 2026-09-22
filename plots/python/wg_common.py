"""Gemeinsame Farben, Texte und Datenzugriffe für alle Python-Grafiken.

Alle Varianten (matplotlib, plotnine, plotly) lesen dieselben CSVs aus
``data/derived/`` und benutzen dieselbe Palette – so unterscheiden sich die
Bilder nur in der Umsetzung, nicht in den Zahlen.
"""

from __future__ import annotations

import argparse
import math
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

#: Bewölkungsskalen von wolkenlos nach bedeckt, fest an 0 bis 8 Achtel
#: gebunden. „blau" liest den Himmel, „gelb" die Sonne. Gelb läuft über ein
#: helles Sandton-Mittel statt direkt ins Grau – die direkte Mischung wird
#: kakifarben. Kalenderblatt und Drei-Tage-Streifen nehmen dieselbe Quelle.
SKALEN = {
    "blau": ["#1f7ae0", "#7ea6cf", "#adb5bd", "#8d9296"],
    "gelb": ["#f9c22e", "#f2e3b3", "#d5d8db", "#8d9296"],
    # Himmel für den Sonnen-Stil: von klarem Blau ins Wolkengrau.
    "sonne": ["#2f80ed", "#6f9ed6", "#a8b2bb", "#8d9296"],
}
#: Dieselben Achtel bei Nacht: klare Nacht tiefes Nachtblau, bedeckte Nacht
#: dunkles Grau. Liegt durchweg unter dem dunkelsten Tagesgrau, damit der
#: Wechsel auch bei ganztägig bedecktem Himmel sichtbar bleibt.
NACHTSKALA = ["#0d1b3d", "#2b3a55", "#3a4048", "#33373b"]
OKTA_MAX = 8

#: Lage der Stationen aus der DWD-Stationsbeschreibung (Breite, Länge in Grad).
STATION_KOORDINATEN = {4931: (48.6883, 9.2235), 4928: (48.8281, 9.2000)}

#: Sonnenhöhe, unter der die Sonne als untergegangen gilt: Refraktion plus
#: halber Sonnendurchmesser, wie in jedem Kalender.
HORIZONT = -0.833

#: Alle Bilder und Begleittexte nennen Ortszeit (Beschluss 22.09.2026). Der
#: DWD liefert Stundenwerte in UTC; ``nach_ortszeit`` rechnet sie beim Laden um.
ORTSZEIT = "Europe/Berlin"


def nach_ortszeit(zeitpunkte: pd.Series) -> pd.Series:
    """UTC-Zeitstempel (naiv, wie der DWD sie liefert) in zonenbewusste Ortszeit.

    Zonenbewusst statt naiv, damit die doppelte Stunde beim Wechsel auf
    Winterzeit zwei verschiedene Zeitpunkte bleibt und die fehlende Stunde im
    Frühjahr keine Lücke vortäuscht.
    """
    return zeitpunkte.dt.tz_localize("UTC").dt.tz_convert(ORTSZEIT)


def utc_naiv(zeitpunkt) -> pd.Timestamp:
    """Zeitpunkt als naiver UTC-Timestamp; naive Eingaben gelten als UTC."""
    ts = pd.Timestamp(zeitpunkt)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def sonnenhoehe(zeitpunkt, breite: float, laenge: float) -> float:
    """Höhe der Sonne über dem Horizont in Grad.

    ``zeitpunkt`` darf zonenbewusst sein (dann wird nach UTC umgerechnet) oder
    naiv (dann gilt er als UTC). Sonnenposition nach den Näherungsformeln des
    Astronomical Almanac (Genauigkeit rund 0,01°, für Stundenfelder mehr als
    genug), Stundenwinkel über die Sternzeit – so braucht es keine Zeitgleichung
    und kein Paket. Achtung: ``Timestamp.to_julian_date`` ignoriert die Zone,
    deshalb vorher explizit nach UTC.
    """
    n = utc_naiv(zeitpunkt).to_julian_date() - 2451545.0
    mittlere_laenge = (280.460 + 0.9856474 * n) % 360
    anomalie = math.radians((357.528 + 0.9856003 * n) % 360)
    ekliptik = math.radians(
        mittlere_laenge + 1.915 * math.sin(anomalie) + 0.020 * math.sin(2 * anomalie)
    )
    schiefe = math.radians(23.439 - 0.0000004 * n)
    deklination = math.asin(math.sin(schiefe) * math.sin(ekliptik))
    rektaszension = math.atan2(math.cos(schiefe) * math.sin(ekliptik), math.cos(ekliptik))
    sternzeit = math.radians((280.46061837 + 360.98564736629 * n + laenge) % 360)
    stundenwinkel = sternzeit - rektaszension
    phi = math.radians(breite)
    sinus = (math.sin(phi) * math.sin(deklination)
             + math.cos(phi) * math.cos(deklination) * math.cos(stundenwinkel))
    return math.degrees(math.asin(max(-1.0, min(1.0, sinus))))


def sonnenauf_untergang(tag, breite: float, laenge: float):
    """(Aufgang, Untergang) für einen Kalendertag, in der Zone von ``tag``.

    Ein zonenbewusster ``tag`` (Ortszeit) liefert Ortszeiten und meint den
    örtlichen Kalendertag; ein naiver gilt als UTC. Sucht minütlich den
    Durchgang durch den Horizont (−0,833°) und interpoliert linear. Fehlt ein
    Durchgang (Polartag, Polarnacht), steht dort ``None``. Probe Echterdingen,
    21.09.2026 (MESZ): Aufgang 7:08, Untergang 19:23; Kalenderwerte für
    Stuttgart liegen innerhalb von drei Minuten. 21.06.: 5:20 / 21:29 MESZ,
    21.12.: 8:12 / 16:29 MEZ.
    """
    start = pd.Timestamp(tag).normalize()
    ende = start + pd.Timedelta(days=1)
    # Beim Wechsel auf Sommerzeit hat der Tag 23 Stunden, im Herbst 25 –
    # date_range in der Zone zählt das richtig.
    minuten = pd.date_range(start, ende, freq="min")
    hoehen = [sonnenhoehe(t, breite, laenge) - HORIZONT for t in minuten]
    aufgang = untergang = None
    for t0, t1, h0, h1 in zip(minuten, minuten[1:], hoehen, hoehen[1:]):
        if h0 < 0 <= h1 and aufgang is None:
            aufgang = t0 + (t1 - t0) * (h0 / (h0 - h1))
        elif h0 >= 0 > h1 and untergang is None:
            untergang = t0 + (t1 - t0) * (h0 / (h0 - h1))
    return aufgang, untergang
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

#: Schriften, mit denen die Beiträge so aussehen sollen, wie sie gedacht sind.
#: Myriad Pro liegt auf dem Mac; Fira Sans ist der Ersatz auf Linux, weil sie
#: als eine der wenigen frei verfügbaren Groteske einen echten schmalen
#: Schnitt mitbringt. „Fira Sans Condensed" steht zuerst, weil manche
#: Installationen sie als eigene Familie führen statt als Schnitt von „Fira
#: Sans" – dann greift ``font.stretch`` allein nicht.
FONT_GEWOLLT = ["Myriad Pro", "Fira Sans Condensed", "Fira Sans"]

#: Notnagel, damit eine Grafik auch auf einem nackten System entsteht. Sie
#: sieht dann anders aus als das Veröffentlichte – check_setup.py sagt es.
FONT_ERSATZ = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

FONT_FAMILY = FONT_GEWOLLT + FONT_ERSATZ

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
