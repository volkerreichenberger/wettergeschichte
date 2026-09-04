#!/usr/bin/env python3
"""Zwei Grafiken für Metaxata auf Kefalonia – örtlich, nicht für den Kanal.

    ./kefalonia.py                          beide Bilder nach posts/kefalonia/
    ./kefalonia.py --nur stunden
    ./kefalonia.py --bis 2026-09-01         Fenster endet an einem frueheren Tag
    ./kefalonia.py --quelle metar           echte Flughafenmeldungen statt Modell
    ./kefalonia.py --neu                    Zwischenspeicher verwerfen

Es entstehen:

* **Stundenkurve** – Temperatur (blau) und Luftfeuchtigkeit (grau, Skala rechts)
  der letzten fünf Tage bis zum letzten vorliegenden Wert. ``--bis`` verschiebt
  das Fenster in die Vergangenheit, seine Länge bleibt.
* **NYT-Diagramm** – dasselbe Bild wie für Stuttgart, gezeichnet mit den
  Funktionen aus ``plots/python/nyt_matplotlib.py``.

Zur Quelle: In Metaxata misst niemand, der nächste Platz ist der Flughafen
Kefalonia (LGKF, Anna Pollatou), wenige Kilometer entfernt. Seine echten
METAR-Meldungen (``--quelle metar``) haben aber jede Nacht ein Loch von 01 bis
05 Uhr – der Platz ist dann geschlossen –, und sie reichen nicht weit genug
zurück für Rekorde und eine Normalperiode. Vorgabe ist deshalb Open-Meteo am
Punkt des Flughafens: ERA5-Reanalyse, lückenlos und bis 1960 zurück. Das sind
gerechnete, keine gemessenen Werte; im Bild steht, was gilt.

Absichtlich eigenständig: nichts an der Struktur des Projekts wird angefasst,
die Bilder landen unter ``posts/kefalonia/`` und die Daten unter
``data/kefalonia/`` – beides steht ohnehin in ``.gitignore``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "plots" / "python"))
sys.path.insert(0, str(ROOT))

import climatology                      # noqa: E402  – Normalen und Rekorde
import drei_tage_matplotlib as drei     # noqa: E402  – Tagesachse
import nyt_matplotlib as nyt            # noqa: E402  – NYT-Zeichenlogik
import wg_common as wg                  # noqa: E402  – Palette, Schrift, Format

# --------------------------------------------------------------------------- #
# Ort und Quellen
# --------------------------------------------------------------------------- #

ORT = "Metaxata, Kefalonia"
#: Flughafen Kefalonia „Anna Pollatou“ – die Koordinaten stammen aus den
#: METAR-Meldungen der Station selbst.
FLUGHAFEN = {"icao": "LGKF", "name": "Flughafen Kefalonia (Anna Pollatou)",
             "lat": 38.1201, "lon": 20.5005}
ZEITZONE = "Europe/Athens"

#: So weit zurück wird die Klimatologie gerechnet. ERA5 reicht bis 1940; ab
#: 1960 ist die Reihe lang genug für Rekorde, ohne die unsicheren frühen
#: Jahrzehnte mitzunehmen.
HISTORIE_AB = "1960-01-01"
REFERENZ = (1991, 2020)

#: Grau der Feuchtekurve – dunkel genug zum Lesen, blass genug, um der
#: blauen Temperaturkurve den Vortritt zu lassen.
FEUCHTE = "#8c8c8c"

#: Länge des Stundenfensters. Fünf Tage sind der Kompromiss: lang genug, um
#: den Gang des Wetters zu sehen, kurz genug, dass die einzelne Stunde noch
#: Platz auf der Achse hat und die Tagesnamen nicht aneinanderstoßen.
STUNDEN_TAGE = 5

STUNDEN_PX = 1080
CACHE = ROOT / "data" / "kefalonia"
ZIEL = ROOT / "posts" / "kefalonia"


# --------------------------------------------------------------------------- #
# Daten holen
# --------------------------------------------------------------------------- #

def hole(url: str, params: dict, dienst: str = "") -> bytes:
    """Holt eine URL und macht aus einem Netzfehler eine lesbare Meldung.

    Der METAR-Dienst (IEM) ist wiederholt überlastet gewesen; ein roher
    Traceback sagt einem dann nicht, dass ein zweiter Versuch hilft.
    """
    voll = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(voll, headers={"User-Agent": "wettergeschichte/kefalonia"})
    try:
        with urllib.request.urlopen(req, timeout=120) as antwort:
            return antwort.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{dienst or url} antwortet mit HTTP {exc.code} ({exc.reason}). "
                         f"Der Dienst ist oft nur kurz überlastet – später erneut "
                         f"versuchen.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"{dienst or url} nicht erreichbar: {exc}") from exc


def hole_json(url: str, params: dict, dienst: str = "Open-Meteo") -> dict:
    return json.loads(hole(url, params, dienst))


def stundenwerte_modell(von: str, bis: str) -> tuple[pd.DataFrame, str]:
    """Stündliche Temperatur und Feuchte aus Open-Meteo, lückenlos.

    Die Vorhersage-Schnittstelle statt des Archivs: ERA5 hinkt einige Tage
    hinterher, ``past_days`` reicht dagegen bis zur laufenden Stunde.
    """
    tage = (date.today() - date.fromisoformat(von)).days + 1
    daten = hole_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": FLUGHAFEN["lat"], "longitude": FLUGHAFEN["lon"],
        "hourly": "temperature_2m,relative_humidity_2m",
        "past_days": min(max(tage, 1), 92), "forecast_days": 1,
        "timezone": ZEITZONE,
    })
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(daten["hourly"]["time"]),
        "temp_c": daten["hourly"]["temperature_2m"],
        "rh": daten["hourly"]["relative_humidity_2m"],
    })
    # Nur bis zur letzten Stunde, für die beide Größen vorliegen: die
    # Vorhersage läuft sonst in die Zukunft weiter.
    df = df.dropna(subset=["temp_c", "rh"])
    jetzt = pd.Timestamp.now(tz=ZEITZONE).tz_localize(None).floor("h")
    # ``bis`` ist ein Tag, kein Zeitpunkt – sonst endete die Kurve um Mitternacht.
    ende = min(jetzt, pd.Timestamp(bis) + pd.Timedelta(hours=23))
    df = df[(df["timestamp"] >= pd.Timestamp(von)) & (df["timestamp"] <= ende)]
    return df.reset_index(drop=True), "Open-Meteo (ERA5 / ICON) am Punkt des Flughafens"


def stundenwerte_metar(von: str, bis: str) -> tuple[pd.DataFrame, str]:
    """Die echten Halbstundenmeldungen des Flughafens, auf volle Stunden gemittelt.

    Ehrlich mit Lücken: zwischen 01 und 05 Uhr meldet der Platz nicht, dort
    bleibt die Kurve unterbrochen statt überbrückt.
    """
    ende = date.fromisoformat(bis) + timedelta(days=1)
    roh = hole("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py", {
        "station": FLUGHAFEN["icao"], "data": ["tmpc", "relh"],
        "year1": von[:4], "month1": int(von[5:7]), "day1": int(von[8:10]),
        "year2": ende.year, "month2": ende.month, "day2": ende.day,
        "tz": ZEITZONE, "format": "onlycomma", "missing": "empty",
    }, "Das METAR-Archiv (IEM)").decode("utf-8")
    if roh.lstrip().startswith("ERROR"):
        raise SystemExit(f"IEM meldet: {roh.strip()[:200]}")

    zeilen = list(csv.DictReader(io.StringIO(roh)))
    df = pd.DataFrame([
        {"timestamp": pd.Timestamp(z["valid"]),
         "temp_c": float(z["tmpc"]) if z["tmpc"] else None,
         "rh": float(z["relh"]) if z["relh"] else None}
        for z in zeilen
    ])
    if df.empty:
        raise SystemExit("keine METAR-Meldungen im Zeitraum")
    df = df.dropna(subset=["temp_c", "rh"])
    df["timestamp"] = df["timestamp"].dt.floor("h")
    df = df.groupby("timestamp", as_index=False)[["temp_c", "rh"]].mean()

    # Fehlende Stunden als Lücke einsetzen, damit die Linie dort bricht.
    # Aufgefüllt wird ab Mitternacht des ersten Tages, auch wenn die erste
    # Meldung später kam: die Tagesachse setzt ihre Grenzen an der Stunde 0,
    # sonst bliebe der angebrochene erste Tag ohne Beschriftung.
    voll = pd.DataFrame({"timestamp": pd.date_range(pd.Timestamp(von),
                                                    df["timestamp"].max(), freq="h")})
    df = voll.merge(df, on="timestamp", how="left")
    return df.reset_index(drop=True), f"METAR-Meldungen {FLUGHAFEN['icao']} (Lücken 01–05 Uhr: Platz geschlossen)"


def tageswerte(neu: bool = False) -> pd.DataFrame:
    """Tägliche Höchst-, Tiefst- und Mittelwerte seit HISTORIE_AB.

    Das Archiv (ERA5) hinkt ein paar Tage hinterher; die fehlenden letzten
    Tage werden aus der Vorhersage-Schnittstelle nachgelegt, sonst endet das
    NYT-Diagramm mitten in der vergangenen Woche.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    datei = CACHE / "tageswerte.csv"
    if datei.exists() and not neu:
        alt = pd.read_csv(datei, parse_dates=["date"])
        if alt["date"].max().date() >= date.today() - timedelta(days=1):
            return alt

    felder = "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum"
    archiv = hole_json("https://archive-api.open-meteo.com/v1/archive", {
        "latitude": FLUGHAFEN["lat"], "longitude": FLUGHAFEN["lon"],
        "start_date": HISTORIE_AB, "end_date": date.today().isoformat(),
        "daily": felder, "timezone": ZEITZONE,
    })["daily"]
    df = pd.DataFrame({
        "date": pd.to_datetime(archiv["time"]),
        "temp_max_c": archiv["temperature_2m_max"],
        "temp_min_c": archiv["temperature_2m_min"],
        "temp_mean_c": archiv["temperature_2m_mean"],
        "precip_mm": archiv["precipitation_sum"],
    })

    nach = hole_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": FLUGHAFEN["lat"], "longitude": FLUGHAFEN["lon"],
        "daily": felder, "past_days": 14, "forecast_days": 1, "timezone": ZEITZONE,
    })["daily"]
    frisch = pd.DataFrame({
        "date": pd.to_datetime(nach["time"]),
        "temp_max_c": nach["temperature_2m_max"],
        "temp_min_c": nach["temperature_2m_min"],
        "temp_mean_c": nach["temperature_2m_mean"],
        "precip_mm": nach["precipitation_sum"],
    })
    # Das Archiv gewinnt, wo es etwas hat; die Vorhersage füllt nur den Rest.
    df = df.dropna(subset=["temp_max_c", "temp_min_c"])
    frisch = frisch[~frisch["date"].isin(df["date"])].dropna(subset=["temp_max_c", "temp_min_c"])
    df = pd.concat([df, frisch], ignore_index=True).sort_values("date").reset_index(drop=True)

    df.to_csv(datei, index=False, date_format="%Y-%m-%d")
    return df


# --------------------------------------------------------------------------- #
# Stundenkurve: Temperatur und Feuchte
# --------------------------------------------------------------------------- #

def zeichne_stunden(df: pd.DataFrame, quelle: str, pfad: Path, dpi: int) -> None:
    plt.rcParams.update({**wg.rc_font(), "figure.facecolor": wg.BACKGROUND,
                         "savefig.facecolor": wg.BACKGROUND, "text.color": wg.TEXT})

    df = df.copy().reset_index(drop=True)
    df["hour"] = df["timestamp"].dt.hour
    df["x"] = range(len(df))

    fig = plt.figure(figsize=(STUNDEN_PX / 200, STUNDEN_PX / 200), dpi=200)
    # Oben Luft für Titel und Unterzeile, unten für die zweizeiligen Tagesnamen.
    ax = fig.add_axes((0.105, 0.185, 0.795, 0.645))
    rechts = ax.twinx()

    # Feuchte zuerst und nach hinten: die Temperatur ist die Hauptaussage.
    rechts.plot(df["x"], df["rh"], color=FEUCHTE, lw=1.8, solid_capstyle="round", zorder=3)
    ax.plot(df["x"], df["temp_c"], color=wg.BACKGROUND, lw=drei.HALO_LW,
            solid_capstyle="round", zorder=9)
    ax.plot(df["x"], df["temp_c"], color=wg.CURRENT_BLUE, lw=drei.CURRENT_LW,
            solid_capstyle="round", zorder=10)

    drei.day_axis(ax, df)
    # Die Tagesachse ist auf drei Tage ausgelegt und setzt 19 Punkt. Ab dem
    # vierten Tag stoßen die Datumszeilen sonst aneinander, deshalb die Größe
    # aus der Breite ableiten, die einem Tag tatsächlich bleibt.
    marken = list(ax.get_xticks())
    namen = [b.get_text() for b in ax.get_xticklabels()]
    tage = max(1, len(marken))

    # Der letzte Tag ist meist angebrochen. Sein Name stünde dann mittig über
    # wenigen Stunden und damit halb über dem Nachbarn; rechtsbündig am Rand
    # der Achse hat er Platz. Ab einem halben Tag Breite passt er mittig.
    letzte_stunden = int((df["timestamp"].iloc[-1]
                          - df["timestamp"].iloc[-1].normalize()).total_seconds() // 3600) + 1
    angebrochen = len(marken) > 1 and letzte_stunden < 12
    if angebrochen:
        marken[-1] = len(df) - 0.5

    ax.set_xticks(marken)
    ax.set_xticklabels(namen, fontsize=max(9.0, min(19.0, 57.0 / tage)),
                       linespacing=1.4)
    if angebrochen:
        ax.get_xticklabels()[-1].set_horizontalalignment("right")
    ax.tick_params(axis="x", length=0, pad=10)
    ax.set_xlim(-0.5, len(df) - 0.5)

    # Ob die Namen nebeneinander passen, hängt nicht nur an ihrer Zahl, sondern
    # an ihrer Länge („1. September“ ist breiter als „5. Mai“) und daran, wie
    # schmal der angebrochene letzte Tag ist. Deshalb nicht geschätzt, sondern
    # nachgemessen: verkleinern, bis sich nichts mehr überlappt.
    fig.canvas.draw()

    def stossen_aneinander() -> bool:
        kaesten = [b.get_window_extent() for b in ax.get_xticklabels()]
        return any(a.x1 + 6 > b.x0 for a, b in zip(kaesten, kaesten[1:]))

    groesse = ax.get_xticklabels()[0].get_fontsize()
    while groesse > 8.0 and stossen_aneinander():
        groesse -= 0.5
        for beschriftung in ax.get_xticklabels():
            beschriftung.set_fontsize(groesse)
        fig.canvas.draw()

    ax.grid(axis="y", color=wg.GRID, lw=0.5, alpha=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("°C", rotation=0, loc="top", labelpad=-14, fontsize=11, color=wg.CURRENT_BLUE)
    ax.tick_params(axis="y", labelsize=11, colors=wg.CURRENT_BLUE, length=0)

    feucht = df["rh"].dropna()
    unten = max(0, int(feucht.min() // 10 * 10) - 5)
    oben = min(100, int(feucht.max() // 10 * 10) + 15)
    rechts.set_ylim(unten, oben)
    # Die Einheit von Hand setzen statt über set_ylabel: dort landet sie neben
    # der obersten Zahl statt über ihr, und „%100“ liest sich als ein Wort.
    rechts.annotate("%", xy=(1.0, 1.035), xycoords="axes fraction",
                    ha="left", va="bottom", fontsize=11, color=FEUCHTE)
    rechts.tick_params(axis="y", labelsize=11, colors=FEUCHTE, length=0)
    rechts.grid(False)

    for seite in ("top", "right", "bottom", "left"):
        ax.spines[seite].set_visible(False)
        rechts.spines[seite].set_visible(False)

    handles = [Line2D([], [], color=wg.CURRENT_BLUE, lw=drei.CURRENT_LW, label="Temperatur"),
               Line2D([], [], color=FEUCHTE, lw=1.8, label="Luftfeuchtigkeit")]
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.995),
                    frameon=True, framealpha=0.93, edgecolor=wg.GRID,
                    facecolor=wg.BACKGROUND, fontsize=9.5, handlelength=1.6,
                    borderpad=0.7, labelspacing=0.42)
    leg.get_frame().set_linewidth(0.5)
    leg.set_zorder(11)

    erste, letzte = df["timestamp"].iloc[0], df["timestamp"].iloc[-1]
    fig.text(0.105, 0.977, ORT, fontsize=23, fontweight="bold", ha="left", va="top")
    fig.text(0.105, 0.928,
             f"Stündliche Temperatur und Luftfeuchtigkeit, "
             f"{wg.de_date(erste)} bis {wg.de_date(letzte)} {letzte.year}",
             fontsize=11.5, color=wg.TEXT_MUTED, ha="left", va="top")
    fig.text(0.105, 0.035,
             f"{quelle}  ·  {FLUGHAFEN['lat']:.4f}° N, {FLUGHAFEN['lon']:.4f}° O  ·  "
             f"Stand {letzte:%d.%m.%Y, %H} Uhr",
             fontsize=8.5, color=wg.TEXT_MUTED, ha="left", va="top")

    pfad.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pfad, dpi=dpi)
    plt.close(fig)
    print(f"geschrieben: {pfad}")


# --------------------------------------------------------------------------- #
# NYT-Diagramm
# --------------------------------------------------------------------------- #

def zeichne_nyt(tage: pd.DataFrame, jahr: int, pfad: Path, dpi: int) -> None:
    """Dasselbe Diagramm wie für Stuttgart, mit den Funktionen von dort.

    Nur Titel und Fußzeile entstehen hier neu: die aus ``wg_common`` nennen
    fest den Deutschen Wetterdienst, und der hat mit Kefalonia nichts zu tun.
    """
    df = tage.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["doy"] = climatology.doy_no_leap(df["date"])

    clim = climatology.build_climatology(df, REFERENZ)
    jahr_df = climatology.build_year(df, clim, jahr)
    summary = climatology.summarise(jahr_df, clim, 0, jahr)
    summary["station_name"] = ORT

    nyt.style()
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.05, right=0.98, top=0.84, bottom=0.08)

    fenster = (1, int(jahr_df["doy"].max()) + 2)
    nyt.draw(clim, jahr_df, summary, ax, fenster)
    nyt.annotate_extremes(ax, jahr_df, fenster)
    nyt.legend(ax, summary)

    fig.text(0.05, 0.955, f"{ORT} · {jahr}", fontsize=25, fontweight="bold",
             ha="left", va="top")
    fig.text(0.05, 0.912,
             f"Tägliche Höchst- und Tiefsttemperaturen {jahr} im Vergleich zur "
             f"Normalperiode {REFERENZ[0]}–{REFERENZ[1]} und zu den Rekorden seit "
             f"{summary['record_from']}",
             fontsize=12.5, color=wg.TEXT_MUTED, ha="left", va="top")
    fig.text(0.05, 0.878, nyt.window_stats_line(jahr_df, clim, fenster),
             fontsize=11, color=wg.TEXT, ha="left", va="top")
    fig.text(0.05, 0.022,
             f"Datenquelle: Open-Meteo, ERA5-Reanalyse am Punkt des "
             f"{FLUGHAFEN['name']} ({FLUGHAFEN['lat']:.4f}° N, {FLUGHAFEN['lon']:.4f}° O)  ·  "
             f"gerechnete, nicht gemessene Werte  ·  Stand {summary['last_date']}",
             fontsize=9, color=wg.TEXT_MUTED, ha="left", va="top")

    pfad.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pfad, dpi=dpi)
    plt.close(fig)
    print(f"geschrieben: {pfad}")


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bis", default=date.today().isoformat(), metavar="JJJJ-MM-TT",
                    help=f"letzter Tag der Stundenkurve; gezeigt werden immer "
                         f"die {STUNDEN_TAGE} Tage bis dahin")
    ap.add_argument("--jahr", type=int, default=date.today().year,
                    help="Jahr des NYT-Diagramms")
    ap.add_argument("--quelle", choices=["modell", "metar"], default="modell",
                    help="modell = Open-Meteo lückenlos, metar = echte Flughafenmeldungen")
    ap.add_argument("--nur", choices=["stunden", "nyt"],
                    help="nur eine der beiden Grafiken bauen")
    ap.add_argument("--neu", action="store_true", help="Zwischenspeicher verwerfen")
    ap.add_argument("--output", type=Path, default=ZIEL)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--format", default="png", choices=["png", "jpg", "pdf"])
    args = ap.parse_args(argv)

    print(f"== {ORT} – Daten vom {FLUGHAFEN['name']}")

    if args.nur != "nyt":
        holen = stundenwerte_metar if args.quelle == "metar" else stundenwerte_modell
        von = (date.fromisoformat(args.bis)
               - timedelta(days=STUNDEN_TAGE - 1)).isoformat()
        df, quelle = holen(von, args.bis)
        if df["temp_c"].dropna().empty:
            raise SystemExit("keine Stundenwerte im Zeitraum")
        gueltig = df.dropna(subset=["temp_c"])
        print(f"-- Stundenkurve: {len(gueltig)} Werte, "
              f"{gueltig['timestamp'].min():%d.%m. %H} bis "
              f"{gueltig['timestamp'].max():%d.%m. %H} Uhr")
        zeichne_stunden(
            df, quelle,
            args.output / f"temperatur_feuchte_{von}_bis_"
                          f"{gueltig['timestamp'].max():%Y-%m-%d}.{args.format}",
            args.dpi)

    if args.nur != "stunden":
        tage = tageswerte(args.neu)
        print(f"-- Tageswerte: {len(tage)} Tage, "
              f"{tage['date'].min():%Y-%m-%d} bis {tage['date'].max():%Y-%m-%d}")
        zeichne_nyt(tage, args.jahr,
                    args.output / f"nyt_kefalonia_{args.jahr}.{args.format}",
                    args.dpi)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
