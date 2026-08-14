#!/usr/bin/env python3
"""Drei Blicke auf den Niederschlag – quadratisch, für den Kanal.

Niederschlag verhält sich anders als Temperatur, und das bestimmt die
Darstellung: **53 % aller Tage sind völlig trocken**, die Hälfte des
Jahresregens fällt an gut zwanzig Tagen, und die Jahressummen schwanken so
stark (Standardabweichung 117 mm), dass ein linearer Trend von −58 mm über
72 Jahre darin untergeht.

Deshalb gibt es hier **kein Streifenbild wie bei der Bewölkung**: Es würde ein
Muster suggerieren, wo im Wesentlichen Zufall ist. Was trägt:

* ``kumulativ``   vier Jahre untereinander, jedes als Summenkurve
* ``rueckstand``  dieselben Summenkurven, alle in einem Feld
* ``schnee``      wie viel Winterniederschlag noch als Schnee fällt

Der Schneeanteil ist die einzige der drei Reihen mit einem klaren Signal: von
67 % auf 39 % der Winterniederschlagstage. Die beiden Summenkurven zeigen den
Stand eines Jahres, keinen Trend.

    python plots/python/regen_matplotlib.py --art kumulativ
    python plots/python/regen_matplotlib.py --art schnee --station 4931
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg

SIZE_PX = 1080

#: Ab dieser Menge gilt ein Tag als Niederschlagstag. Der DWD misst in 0,1 mm;
#: alles darunter ist eine Null mit anderem Namen.
NASS_AB = 0.1

BLAU = "#1f6fe0"
GRAU = "#9aa0a6"


# --------------------------------------------------------------------------- #
# Daten
# --------------------------------------------------------------------------- #

def lade(data_dir: Path, station: int) -> pd.DataFrame:
    path = data_dir / "stations" / f"{station:05d}" / "daily.csv"
    if not path.exists():
        raise SystemExit(f"{path} fehlt – bitte zuerst 'python fetch_dwd.py' laufen lassen.")
    df = pd.read_csv(path, parse_dates=["date"],
                     usecols=["date", "precip_mm", "precip_form"])
    df["jahr"] = df["date"].dt.year
    df["monat"] = df["date"].dt.month
    return df


def doy_ohne_schalttag(datum: pd.Series) -> pd.Series:
    """Tag im Jahr im 365-Tage-Schema der Klimatologie.

    Dort fällt der 29. Februar mit dem 28. zusammen. Ohne dieselbe Zählung
    läge die Summenkurve eines Schaltjahres um einen Tag neben dem Normal.
    """
    doy = datum.dt.dayofyear
    schalt = datum.dt.is_leap_year & (doy > 59)
    return doy.where(~schalt, doy - 1)


def normalkurve(derived: Path, station: int) -> pd.Series | None:
    """Kumulierter Normalniederschlag aus der Klimatologie, falls vorhanden."""
    path = derived / f"climatology_{station:05d}.csv"
    if not path.exists():
        return None
    clim = pd.read_csv(path, usecols=["doy", "normal_precip"])
    return clim.set_index("doy")["normal_precip"].cumsum()


def stil() -> None:
    plt.rcParams.update({**wg.rc_font(),
                         "figure.facecolor": wg.BACKGROUND,
                         "savefig.facecolor": wg.BACKGROUND,
                         "text.color": wg.TEXT})


def figur(titel: str, unterzeile: str):
    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    # Lange Überschriften laufen sonst rechts aus dem Bild.
    groesse = 26 if len(titel) <= 34 else 21
    fig.text(0.07, 0.955, titel, fontsize=groesse, fontweight="bold", va="top")
    fig.text(0.07, 0.898, unterzeile, fontsize=13.5, color=wg.TEXT_MUTED, va="top",
             linespacing=1.45)
    return fig


def aufraeumen(ax) -> None:
    for seite in ("top", "right", "bottom", "left"):
        ax.spines[seite].set_visible(False)
    ax.tick_params(length=0, labelsize=12, colors=wg.TEXT_MUTED)
    ax.set_facecolor(wg.BACKGROUND)


# --------------------------------------------------------------------------- #
# 1. Rückstand
# --------------------------------------------------------------------------- #

def rueckstand(df, args, name):
    jahre = sorted(df["jahr"].unique())[-6:]
    aktuell = jahre[-1]
    fig = figur(f"Niederschlag seit Jahresbeginn",
                f"{name} · {aktuell} gegen die fünf Vorjahre und den Normalwert")
    ax = fig.add_axes((0.115, 0.20, 0.845, 0.62))

    normal = normalkurve(args.derived, args.station)
    if normal is not None:
        ax.plot(normal.index, normal.values, color=wg.TEXT_MUTED, lw=1.6,
                ls=(0, (5, 3)), zorder=3)
        ax.annotate("Normal 1991–2020", xy=(300, normal.loc[300]), xytext=(-8, 14),
                    textcoords="offset points", fontsize=11.5, color=wg.TEXT_MUTED,
                    ha="right")

    for jahr in jahre[:-1]:
        sub = df[df["jahr"] == jahr].sort_values("date")
        ax.plot(range(1, len(sub) + 1), sub["precip_mm"].fillna(0).cumsum(),
                color=GRAU, lw=1.3, alpha=0.75, zorder=2)
    sub = df[df["jahr"] == aktuell].sort_values("date")
    summe = sub["precip_mm"].fillna(0).cumsum()
    ax.plot(range(1, len(sub) + 1), summe, color=wg.BACKGROUND, lw=5.5, zorder=9)
    ax.plot(range(1, len(sub) + 1), summe, color=BLAU, lw=2.8, zorder=10)
    ax.annotate(f"{aktuell}", xy=(len(sub), summe.iloc[-1]), xytext=(8, 0),
                textcoords="offset points", color=BLAU, fontsize=13,
                fontweight="bold", va="center")

    ax.set_xlim(1, 366)
    ax.set_xticks([(a + b) / 2 for a, b in
                   zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END])])
    ax.set_xticklabels(wg.MONTH_NAMES, fontsize=12)
    ax.set_ylabel("mm seit 1. Januar", fontsize=12, color=wg.TEXT_MUTED)
    ax.grid(axis="y", color=wg.GRID, lw=0.5)
    ax.set_axisbelow(True)
    aufraeumen(ax)

    stand = int(summe.iloc[-1])
    soll = int(normal.loc[min(len(sub), 366)]) if normal is not None else None
    text = f"Stand {stand} mm"
    if soll:
        text += f", normal wären {soll} mm ({stand - soll:+d} mm)"
    fig.text(0.07, 0.115, text, fontsize=14, va="top")
    return fig, kennzahl_rueckstand(stand, soll, aktuell, name)


def kennzahl_rueckstand(stand, soll, jahr, name):
    if soll is None:
        return f"{jahr} sind bisher {stand} mm gefallen."
    d = stand - soll
    wie = "mehr als" if d > 0 else "weniger als"
    return (f"{jahr} sind bisher {stand} mm gefallen, {abs(d)} mm {wie} normal "
            f"({soll} mm bis zu diesem Tag).")


# --------------------------------------------------------------------------- #
# 5. Schnee
# --------------------------------------------------------------------------- #

def schnee(df, args, name):
    # Winter wird dem Januarjahr zugeschlagen: Dezember zählt zum Folgejahr.
    nass = df[(df["precip_mm"] >= NASS_AB) & df["precip_form"].notna()].copy()
    nass["winter"] = np.where(nass["monat"] == 12, nass["jahr"] + 1, nass["jahr"])
    win = nass[nass["monat"].isin([12, 1, 2])]

    gruppe = win.groupby("winter")
    anteil = gruppe["precip_form"].apply(lambda s: s.isin([7, 8]).mean() * 100)
    tage = gruppe.size()
    anteil = anteil[(tage >= 30) & (anteil.index >= 1980) & (anteil.index <= df["jahr"].max())]

    fig = figur("Schnee oder Regen im Winter?",
                f"{name} · Anteil der Niederschlagstage im Dezember bis Februar,\n"
                f"an denen Schnee beteiligt war")
    ax = fig.add_axes((0.115, 0.215, 0.845, 0.57))

    ax.bar(anteil.index, anteil.values, color=GRAU, width=0.72, linewidth=0)
    glatt = anteil.rolling(10, center=True, min_periods=5).mean()
    ax.plot(glatt.index, glatt.values, color=BLAU, lw=3, solid_capstyle="round",
            zorder=5)
    ax.annotate("10-Winter-Mittel", xy=(glatt.index[-1], glatt.iloc[-1]),
                xytext=(-12, 26), textcoords="offset points", fontsize=12,
                color=BLAU, ha="right", fontweight="bold")

    ax.set_ylabel("Anteil der Niederschlagstage mit Schnee (%)", fontsize=12,
                  color=wg.TEXT_MUTED)
    ax.grid(axis="y", color=wg.GRID, lw=0.5)
    ax.set_axisbelow(True)
    aufraeumen(ax)

    frueh = anteil[anteil.index < anteil.index.min() + 10].mean()
    spaet = anteil[anteil.index > anteil.index.max() - 10].mean()
    fig.text(0.07, 0.125,
             f"Erste zehn Winter: {frueh:.0f} % · letzte zehn: {spaet:.0f} %",
             fontsize=14, va="top")
    return fig, (f"An den Niederschlagstagen der Wintermonate war zu Beginn der "
                 f"Reihe an {frueh:.0f} % der Tage Schnee beteiligt, in den letzten "
                 f"zehn Wintern an {spaet:.0f} %. Anders als bei der Regenmenge "
                 f"steckt hier ein echtes Signal: Es hängt an der Temperatur, nicht "
                 f"an der Niederschlagsmenge.")


# --------------------------------------------------------------------------- #
# 8. Vier Summenkurven übereinander
# --------------------------------------------------------------------------- #

def kumulativ(df, args, name):
    """Ein Feld je Jahr, darin die Summenkurve gegen den Normalverlauf.

    Gegenüber allen Jahren in einem Feld (``rueckstand``) gewinnt man Ruhe: Man
    sieht je Jahr, *wann* der Rückstand entstand, statt fünf Kurven zu
    entwirren. Alle Felder teilen dieselbe Skala, sonst wäre nichts vergleichbar.
    """
    voll = df.dropna(subset=["precip_mm"])
    tage = voll.groupby("jahr")["precip_mm"].count()
    # Das laufende Jahr darf unvollständig sein, die Vergleichsjahre nicht.
    jahre = sorted(voll["jahr"].unique(), reverse=True)
    jahre = [jahre[0]] + [j for j in jahre[1:] if tage[j] >= 350]
    jahre = jahre[:4]

    normal = normalkurve(args.derived, args.station)
    kurven = {}
    for jahr in jahre:
        sub = voll[voll["jahr"] == jahr].sort_values("date")
        kurven[jahr] = pd.Series(sub["precip_mm"].cumsum().values,
                                 index=doy_ohne_schalttag(sub["date"]).values)

    oben = max(k.max() for k in kurven.values())
    if normal is not None:
        oben = max(oben, float(normal.max()))
    oben *= 1.08

    fig = figur(f"Niederschlag {name}", "")

    for i, jahr in enumerate(jahre):
        ax = fig.add_axes((0.135, 0.663 - i * 0.178, 0.825, 0.138))
        if normal is not None:
            ax.plot(normal.index, normal.values, color=wg.TEXT_MUTED, lw=1.3,
                    ls=(0, (5, 3)), zorder=3)
        kurve = kurven[jahr]
        ax.fill_between(kurve.index, 0, kurve.values, color=BLAU, alpha=0.14, zorder=2)
        ax.plot(kurve.index, kurve.values, color=BLAU, lw=2.4,
                solid_capstyle="round", zorder=4)

        ax.set_xlim(1, 366)
        ax.set_ylim(0, oben)
        ax.set_yticks([0, 400, 800])
        ax.set_yticklabels(["0", "400", "800"], fontsize=10.5)
        ax.set_xticks([(a + b) / 2 for a, b in
                       zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END])])
        ax.set_xticklabels(wg.MONTH_NAMES if i == len(jahre) - 1 else [], fontsize=11)
        ax.grid(axis="y", color=wg.GRID, lw=0.5)
        ax.set_axisbelow(True)
        aufraeumen(ax)

        ax.text(0.008, 0.9, str(jahr), transform=ax.transAxes, va="top",
                fontsize=15, fontweight="bold",
                color=BLAU if i == 0 else wg.TEXT)

    zeilen = []
    for i, jahr in enumerate(jahre):
        kurve = kurven[jahr]
        ende = int(kurve.iloc[-1])
        soll = int(normal.loc[int(kurve.index[-1])]) if normal is not None else None
        # Das laufende Jahr steht mit einem Teiljahr in der Liste – das muss dran.
        bis = f" (bis {voll[voll['jahr'] == jahr]['date'].max():%d.%m.})" if i == 0 else ""
        zeilen.append(f"· {jahr}{bis}: {ende} mm"
                      + (f", {abs(ende - soll)} mm "
                         f"{'über' if ende > soll else 'unter'} normal" if soll else ""))
    laufend = jahre[0]
    return fig, (
        f"Der Niederschlag jedes Jahres, Tag für Tag aufsummiert. Die "
        f"gestrichelte Linie ist der Normalverlauf der Periode 1991–2020; wo die "
        f"blaue Kurve darunter bleibt, fehlt Regen. Alle vier Felder haben "
        f"dieselbe Skala.\n\n"
        + "\n".join(zeilen)
        + f"\n\nDie Darstellung zeigt nicht nur, wieviel fehlt, sondern auch wann "
        f"es fehlte – ein flaches Stück in der Kurve ist eine Trockenperiode. "
        f"{laufend} läuft noch, verglichen wird deshalb mit dem Normalwert bis "
        f"zum selben Kalendertag."
    )


# --------------------------------------------------------------------------- #

ARTEN = {
    "kumulativ": (kumulativ, "Niederschlag im Jahresverlauf"),
    "rueckstand": (rueckstand, "Niederschlag seit Jahresbeginn"),
    "schnee": (schnee, "Schneeanteil am Winterniederschlag"),
}


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.set_defaults(format="jpg")
    ap.add_argument("--art", choices=list(ARTEN), default="kumulativ")
    ap.add_argument("--data-dir", type=Path, default=wg.ROOT / "data")
    ap.add_argument("--posts", type=Path, default=wg.POSTS)
    ap.add_argument("--jpeg-quality", type=int, default=92)
    args = ap.parse_args(argv)

    stil()
    df = lade(args.data_dir, args.station)
    name = wg.display_name(args.station, wg.station_name(args.station, args.data_dir))
    zeichnen, _ = ARTEN[args.art]
    fig, kernsatz = zeichnen(df, args, name)

    stand = df.dropna(subset=["precip_mm"])["date"].max()
    fig.text(0.07, 0.028,
             f"Daten: DWD Climate Data Center · Station {args.station} · "
             f"Stand {stand:%d.%m.%Y}",
             fontsize=9.5, color=wg.TEXT_MUTED, va="top")

    slug = f"regen_{args.art}_{args.station:05d}_{stand:%Y-%m-%d}"
    out = wg.post_dir(slug, args.posts)
    bild = out / f"bild.{args.format}"
    save = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(bild, dpi=args.dpi, **save)
    plt.close(fig)

    amtlich = wg.station_name(args.station, args.data_dir)
    (out / "text.txt").write_text(
        f"{ARTEN[args.art][1]} – {name}\n\n{kernsatz}\n\n"
        f"{wg.quelle(args.station, amtlich, f'{stand:%d.%m.%Y}')}\n\n{wg.HASHTAGS}",
        encoding="utf-8")

    print(f"geschrieben: {bild}\ngeschrieben: {out / 'text.txt'}")
    print(f"POST_DIR={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
