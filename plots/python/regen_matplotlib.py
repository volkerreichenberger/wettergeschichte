#!/usr/bin/env python3
"""Fünf Blicke auf den Niederschlag – quadratisch, für den Kanal.

Niederschlag verhält sich anders als Temperatur, und das bestimmt die
Darstellung: **53 % aller Tage sind völlig trocken**, die Hälfte des
Jahresregens fällt an gut zwanzig Tagen, und die Jahressummen schwanken so
stark (Standardabweichung 117 mm), dass ein linearer Trend von −58 mm über
72 Jahre darin untergeht.

Deshalb gibt es hier **kein Streifenbild wie bei der Bewölkung**: Es würde ein
Muster suggerieren, wo im Wesentlichen Zufall ist. Was stattdessen trägt:

* ``rueckstand``     kumulierter Niederschlag gegen den Normalverlauf
* ``kalender``       ein Feld je Tag – die Nullen sind die Aussage
* ``konzentration``  wie wenige Tage den Jahresregen machen
* ``trockenheit``    längste Trockenstrecke je Jahr
* ``schnee``         wie viel Winterniederschlag noch als Schnee fällt
* ``intensitaet``    wie schnell der Regen fiel – braucht Stundenwerte
* ``streifen``       jeder Tag als Streifen, eine Zeile je Jahr
* ``kumulativ``      vier Jahre gestapelt, jedes als Summenkurve

    python plots/python/regen_matplotlib.py --art konzentration
    python plots/python/regen_matplotlib.py --art schnee --station 4931
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg

SIZE_PX = 1080

#: Ab dieser Menge gilt ein Tag als Niederschlagstag. Der DWD misst in 0,1 mm;
#: alles darunter ist eine Null mit anderem Namen.
NASS_AB = 0.1

#: Von trocken nach nass. Der helle Pol ist fast der Hintergrund – ein
#: regenfreier Tag soll im Kalender nicht wie ein Messwert aussehen.
REGEN_CMAP = LinearSegmentedColormap.from_list(
    "regen", ["#eef2f5", "#9dc3e6", "#3d7fc1", "#1b4a80"]
)

#: Oberes Ende der Farbskala. Darüber wird nicht weiter unterschieden – sonst
#: drückt ein einzelner Starkregentag alle übrigen Tage ins Farblose.
MM_MAX = 25.0

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


def laengste_trockenstrecke(werte) -> int:
    lauf = beste = 0
    for v in werte:
        lauf = lauf + 1 if (v == v and v < NASS_AB) else 0
        beste = max(beste, lauf)
    return beste


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
# 2. Kalender
# --------------------------------------------------------------------------- #

def kalender(df, args, name):
    jahr = args.jahr or int(df["jahr"].max())
    sub = df[df["jahr"] == jahr].dropna(subset=["precip_mm"]).sort_values("date")
    fig = figur(f"Jeder Regentag {jahr}",
                f"{name} · ein Feld je Tag, Spalte für Spalte durch das Jahr")

    erster = pd.Timestamp(jahr, 1, 1)
    # Spalte = Kalenderwoche seit Jahresbeginn, Zeile = Wochentag.
    sub = sub.assign(woche=((sub["date"] - erster).dt.days + erster.weekday()) // 7,
                     tag=sub["date"].dt.weekday)
    # Die Felder sollen quadratisch sein. Statt die Achse nachträglich zu
    # stauchen, wird ihre Höhe gleich passend gewählt – sonst bleibt darunter
    # eine Lücke, die mit der Zahl der Wochen wächst.
    breite = 0.895
    hoehe = breite * 7 / (sub["woche"].max() + 1.5)
    ax = fig.add_axes((0.055, 0.755 - hoehe, breite, hoehe))
    for _, r in sub.iterrows():
        mm = r["precip_mm"]
        farbe = REGEN_CMAP(min(mm, MM_MAX) / MM_MAX) if mm >= NASS_AB else "#f4f6f7"
        ax.add_patch(plt.Rectangle((r["woche"] + 0.08, r["tag"] + 0.08), 0.84, 0.84,
                                   facecolor=farbe, edgecolor=wg.BACKGROUND, lw=0.6))
    ax.set_xlim(-0.5, sub["woche"].max() + 1)
    ax.set_ylim(7, 0)
    ax.set_aspect("equal", adjustable="box", anchor="N")
    ax.axis("off")

    for i, tag in enumerate(wg.WEEKDAYS_SHORT):
        if i % 2 == 0:
            ax.text(-0.7, i + 0.5, tag, ha="right", va="center",
                    fontsize=10.5, color=wg.TEXT_MUTED)
    for monat, start in enumerate(wg.MONTH_STARTS):
        woche = ((pd.Timestamp(jahr, monat + 1, 1) - erster).days + erster.weekday()) // 7
        ax.text(woche, -0.5, wg.MONTH_NAMES[monat], ha="left", va="bottom",
                fontsize=11, color=wg.TEXT_MUTED)

    trocken = int((sub["precip_mm"] < NASS_AB).sum())
    balken = fig.add_axes((0.07, 0.155, 0.42, 0.022))
    balken.imshow([[i / 100 for i in range(101)]], aspect="auto", cmap=REGEN_CMAP)
    balken.set_xticks([]); balken.set_yticks([])
    for s in balken.spines.values():
        s.set_visible(False)
    fig.text(0.07, 0.133, "trocken", fontsize=11, color=wg.TEXT_MUTED, va="top")
    fig.text(0.49, 0.133, f"{MM_MAX:.0f} mm und mehr", fontsize=11,
             color=wg.TEXT_MUTED, va="top", ha="right")
    fig.text(0.07, 0.088,
             f"{trocken} von {len(sub)} Tagen blieben trocken – "
             f"{trocken / len(sub):.0%} des Jahres.", fontsize=14, va="top")
    return fig, (f"{trocken} von {len(sub)} Tagen blieben {jahr} ganz trocken, "
                 f"das sind {trocken/len(sub):.0%} des Jahres.")


# --------------------------------------------------------------------------- #
# 3. Konzentration
# --------------------------------------------------------------------------- #

def konzentration(df, args, name):
    jahr = args.jahr or int(df["jahr"].max())
    sub = df[df["jahr"] == jahr].dropna(subset=["precip_mm"])
    werte = sub["precip_mm"].sort_values(ascending=False).reset_index(drop=True)
    anteil = werte.cumsum() / werte.sum()
    n50 = int((anteil < 0.5).sum()) + 1
    n90 = int((anteil < 0.9).sum()) + 1
    nass = int((werte >= NASS_AB).sum())

    fig = figur(f"Der Regen von {jahr} in wenigen Tagen",
                f"{name} · alle Tage nach Menge sortiert, vom nassesten zum trockensten")
    ax = fig.add_axes((0.115, 0.30, 0.845, 0.50))

    ax.bar(range(1, len(werte) + 1), werte, width=1.0, color=BLAU, linewidth=0)
    ax.set_xlim(0, len(werte))
    ax.set_ylabel("mm am Tag", fontsize=12, color=wg.TEXT_MUTED)
    ax.grid(axis="y", color=wg.GRID, lw=0.5)
    ax.set_axisbelow(True)
    aufraeumen(ax)

    # Die beiden Marken liegen dicht beieinander; ohne Höhenversatz
    # überschreiben sich ihre Beschriftungen.
    oben = ax.get_ylim()[1]
    for n, beschriftung, hoehe in ((n50, "die Hälfte", 0.95), (n90, "90 Prozent", 0.62)):
        ax.axvline(n, color=wg.WARM, lw=1.2, ls=(0, (4, 3)), zorder=5)
        ax.annotate(f"{beschriftung} des Jahresregens\nfällt an {n} Tagen",
                    xy=(n, oben * hoehe), xytext=(10, 0),
                    textcoords="offset points", fontsize=11.5, color=wg.WARM,
                    va="top", linespacing=1.4)

    fig.text(0.07, 0.20,
             f"{int(werte.sum())} mm im ganzen Jahr, gefallen an {nass} Tagen.\n"
             f"An {len(werte) - nass} Tagen fiel nichts.",
             fontsize=14, va="top", linespacing=1.5)
    return fig, (f"{jahr} fielen {int(werte.sum())} mm an {nass} Tagen. Die Hälfte "
                 f"davon kam an nur {n50} Tagen zusammen – {n50/len(werte):.0%} des "
                 f"Jahres. Für 90 Prozent brauchte es {n90} Tage.")


# --------------------------------------------------------------------------- #
# 4. Trockenheit
# --------------------------------------------------------------------------- #

def trockenheit(df, args, name):
    voll = df.dropna(subset=["precip_mm"])
    reihe = voll.groupby("jahr")["precip_mm"].apply(laengste_trockenstrecke)
    vollstaendig = voll.groupby("jahr")["precip_mm"].count() >= 350
    reihe = reihe[vollstaendig.reindex(reihe.index, fill_value=False)]
    reihe = reihe[reihe.index >= reihe.index.max() - 39]
    aktuell = int(reihe.index.max())

    fig = figur("Die längste Trockenstrecke",
                f"{name} · längste Folge von Tagen ohne messbaren Niederschlag, je Jahr")
    ax = fig.add_axes((0.115, 0.215, 0.845, 0.60))

    farben = [BLAU if j == aktuell else GRAU for j in reihe.index]
    ax.bar(reihe.index, reihe.values, color=farben, width=0.72, linewidth=0)
    ax.axhline(reihe.median(), color=wg.WARM, lw=1.2, ls=(0, (4, 3)), zorder=5)
    ax.annotate(f"Median dieser Jahre: {reihe.median():.0f} Tage",
                xy=(reihe.index.min(), reihe.median()), xytext=(0, 6),
                textcoords="offset points", fontsize=11.5, color=wg.WARM)

    ax.set_ylabel("Tage am Stück", fontsize=12, color=wg.TEXT_MUTED)
    ax.grid(axis="y", color=wg.GRID, lw=0.5)
    ax.set_axisbelow(True)
    aufraeumen(ax)

    spitze = int(reihe.idxmax())
    # Gezeigt werden nur vollständige Jahre – "bisher" wäre hier falsch.
    fig.text(0.07, 0.125,
             f"Am längsten trocken blieb es {spitze} mit {int(reihe.max())} Tagen.\n"
             f"{aktuell} waren es {int(reihe.loc[aktuell])} Tage.",
             fontsize=14, va="top", linespacing=1.5)
    return fig, (f"Die längste Trockenstrecke eines Jahres liegt in {name} im Median "
                 f"bei {reihe.median():.0f} Tagen. Der Spitzenwert der letzten "
                 f"{len(reihe)} Jahre stammt aus {spitze} mit {int(reihe.max())} "
                 f"Tagen am Stück; {aktuell} waren es "
                 f"{int(reihe.loc[aktuell])}. Gezeigt sind nur Jahre mit "
                 f"durchgehender Messung.")


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
# 6. Intensität
# --------------------------------------------------------------------------- #

#: Zeitzone der DWD-Stundenwerte. Nicht auf Ortszeit umgerechnet – die
#: Umstellung auf Sommerzeit würde die Stundenachse verzerren.
ZEITZONE = "UTC"


def lade_stunden(data_dir: Path, station: int) -> pd.DataFrame:
    path = data_dir / "stations" / f"{station:05d}" / "hourly_precipitation.csv"
    if not path.exists():
        raise SystemExit(
            f"{path} fehlt – bitte zuerst 'python fetch_hourly.py' laufen lassen."
        )
    df = pd.read_csv(path, parse_dates=["timestamp"],
                     usecols=["timestamp", "precip_mm"]).dropna(subset=["precip_mm"])
    df["tag"] = df["timestamp"].dt.normalize()
    df["stunde"] = df["timestamp"].dt.hour
    return df


def intensitaet(df, args, name):
    """Die nassesten Tage, Stunde für Stunde – gleiche Skala für alle."""
    h = lade_stunden(args.data_dir, args.station)
    tage = h.groupby("tag")["precip_mm"].agg(summe="sum", spitze="max")
    groesste = tage.sort_values("summe", ascending=False).head(6).index

    fig = figur("Wie schnell fiel der Regen?",
                f"{name} · die sechs nassesten Tage seit {h['timestamp'].min():%Y}, "
                f"Stunde für Stunde")

    # Eine Skala für alle sechs – mit je eigener sähe ein Landregen aus wie ein
    # Wolkenbruch, und genau der Unterschied ist der Gegenstand.
    oben = float(h[h["tag"].isin(groesste)]["precip_mm"].max()) * 1.15

    for i, tag in enumerate(sorted(groesste, key=lambda d: -tage.loc[d, "summe"])):
        zeile, spalte = divmod(i, 2)
        ax = fig.add_axes((0.09 + spalte * 0.47, 0.64 - zeile * 0.205, 0.38, 0.13))
        werte = (h[h["tag"] == tag].set_index("stunde")["precip_mm"]
                 .reindex(range(24), fill_value=0.0))
        ax.bar(werte.index, werte.values, width=0.9, color=BLAU, linewidth=0)
        ax.set_xlim(-0.5, 23.5)
        ax.set_ylim(0, oben)
        ax.set_xticks([0, 6, 12, 18])
        ax.set_xticklabels(["0", "6", "12", "18"] if zeile == 2 else [])
        ax.set_yticks([0, 20, 40])
        ax.set_yticklabels(["0", "20", "40"] if spalte == 0 else [])
        ax.grid(axis="y", color=wg.GRID, lw=0.5)
        ax.set_axisbelow(True)
        aufraeumen(ax)

        summe, spitze = tage.loc[tag, "summe"], tage.loc[tag, "spitze"]
        ax.set_title(f"{tag:%d.%m.%Y}   {summe:.0f} mm", fontsize=12.5,
                     fontweight="bold", loc="left", pad=6)
        ax.annotate(f"stärkste Stunde {spitze:.0f} mm ({spitze / summe:.0%})",
                    xy=(0.99, 0.86), xycoords="axes fraction", ha="right",
                    fontsize=10.5, color=wg.TEXT_MUTED)

    fig.text(0.09, 0.163, f"Stunde des Tages ({ZEITZONE}) · alle Felder mit derselben "
                          f"Skala bis {oben:.0f} mm",
             fontsize=11, color=wg.TEXT_MUTED, va="top")

    stark = tage.loc[groesste].assign(anteil=lambda d: d.spitze / d.summe)
    heftig = stark["anteil"].idxmax()
    sanft = stark["anteil"].idxmin()
    fig.text(0.09, 0.122,
             f"Am {heftig:%d.%m.%Y} fielen {stark.loc[heftig, 'anteil']:.0%} der "
             f"Tagesmenge in einer einzigen Stunde,\n"
             f"am {sanft:%d.%m.%Y} nur {stark.loc[sanft, 'anteil']:.0%}.",
             fontsize=12.5, va="top", linespacing=1.5)

    return fig, (
        f"Zwei Tage mit fast derselben Menge können völlig verschiedene "
        f"Ereignisse sein. Am {heftig:%d.%m.%Y} fielen "
        f"{tage.loc[heftig, 'summe']:.0f} mm, davon "
        f"{tage.loc[heftig, 'spitze']:.0f} mm in einer einzigen Stunde – "
        f"{stark.loc[heftig, 'anteil']:.0%} der Tagesmenge. Am "
        f"{sanft:%d.%m.%Y} verteilten sich {tage.loc[sanft, 'summe']:.0f} mm "
        f"über den ganzen Tag; die stärkste Stunde brachte nur "
        f"{stark.loc[sanft, 'anteil']:.0%}.\n\n"
        f"Über alle Regentage hinweg fällt im Median 41 Prozent der Tagesmenge "
        f"in der stärksten Stunde.\n\n"
        f"Ob solche Wolkenbrüche häufiger werden, lässt sich hier nicht sagen: "
        f"Die Stundenreihe reicht erst bis 1995 zurück, und die stärkste Stunde "
        f"eines Jahres schwankt so stark, dass kein Trend erkennbar ist. "
        f"Zeiten in {ZEITZONE}."
    )


# --------------------------------------------------------------------------- #
# 7. Streifenbild
# --------------------------------------------------------------------------- #

def streifen(df, args, name):
    """Eine Zeile je Jahr, ein Streifen je Tag – weiß heißt trocken.

    Bewusst als Tageswerte und nicht als Jahressummen: Gemittelte Jahre lägen
    alle im blassen Mittelfeld, und ein Streifen je Jahr würde überdies einen
    Trend nahelegen, den die Zahlen nicht hergeben (siehe Kopfkommentar).
    """
    voll = df.dropna(subset=["precip_mm"])
    tage_je_jahr = voll.groupby("jahr")["precip_mm"].count()
    jahre = sorted(tage_je_jahr[tage_je_jahr >= 350].index, reverse=True)
    if args.jahre:
        jahre = jahre[:args.jahre]

    fig = figur(f"Jeder Regentag seit {jahre[-1]}",
                f"{name} · eine Zeile je Jahr, ein Streifen je Tag · "
                f"weiß heißt: kein Regen")
    ax = fig.add_axes((0.115, 0.225, 0.845, 0.565))
    ax.set_xlim(1, 367)
    ax.set_ylim(len(jahre), 0)
    ax.axis("off")

    werte = {(j, d): m for j, d, m in zip(voll["jahr"], voll["date"].dt.dayofyear,
                                          voll["precip_mm"])}
    for zeile, jahr in enumerate(jahre):
        for tag in range(1, 367):
            mm = werte.get((jahr, tag))
            if mm is None or mm < NASS_AB:
                continue   # trocken bleibt weiß
            ax.add_patch(plt.Rectangle((tag, zeile + 0.06), 1, 0.88,
                                       facecolor=REGEN_CMAP(min(mm, MM_MAX) / MM_MAX),
                                       linewidth=0))
        if len(jahre) <= 12 or zeile == 0 or jahr % 10 == 0:
            ax.text(-6, zeile + 0.5, str(jahr), ha="right", va="center",
                    fontsize=11 if len(jahre) > 12 else 13,
                    color=wg.TEXT if zeile == 0 else wg.TEXT_MUTED,
                    fontweight="bold" if zeile == 0 else "normal")

    # Die Monatsnamen hängen an der Achse, nicht an der Zeilenzahl – sonst
    # wandern sie mit weniger Jahren immer weiter nach unten.
    for monat, start in enumerate(wg.MONTH_STARTS):
        ax.text(start, -0.035, wg.MONTH_NAMES[monat], ha="left", va="top",
                fontsize=11, color=wg.TEXT_MUTED,
                transform=ax.get_xaxis_transform())

    balken = fig.add_axes((0.115, 0.086, 0.42, 0.024))
    balken.imshow([[i / 100 for i in range(101)]], aspect="auto", cmap=REGEN_CMAP)
    balken.set_xticks([]); balken.set_yticks([])
    for s in balken.spines.values():
        s.set_visible(False)
    fig.text(0.115, 0.064, "wenig", fontsize=11, color=wg.TEXT_MUTED, va="top")
    fig.text(0.535, 0.064, f"{MM_MAX:.0f} mm und mehr", fontsize=11,
             color=wg.TEXT_MUTED, va="top", ha="right")

    trocken = float((voll[voll["jahr"].isin(jahre)]["precip_mm"] < NASS_AB).mean())
    fig.text(0.115, 0.152,
             f"{trocken:.0%} aller Tage blieben trocken – das Weiß ist die Mehrheit.",
             fontsize=13.5, va="top")

    summen = voll[voll["jahr"].isin(jahre)].groupby("jahr")["precip_mm"].sum()
    return fig, (
        f"Jeder Tag der letzten {len(jahre)} Jahre als Streifen, eine Zeile je "
        f"Jahr. Weiß heißt: an diesem Tag fiel nichts – und das war "
        f"{trocken:.0%} der Zeit der Fall.\n\n"
        f"Nasseste Jahre: {summen.idxmax()} mit {summen.max():.0f} mm, "
        f"trockenste: {summen.idxmin()} mit {summen.min():.0f} mm.\n\n"
        f"Anders als bei der Temperatur taugt so ein Bild beim Niederschlag "
        f"nicht als Trendaussage: Die Jahressummen schwanken um rund 117 mm, "
        f"während sich über 72 Jahre insgesamt nur etwa 58 mm verschoben haben. "
        f"Was man sieht, ist vor allem Wetter."
    )


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
    "rueckstand": (rueckstand, "Niederschlag seit Jahresbeginn"),
    "kalender": (kalender, "Regenkalender"),
    "konzentration": (konzentration, "Die wenigen Tage, die den Regen machen"),
    "trockenheit": (trockenheit, "Längste Trockenstrecke je Jahr"),
    "schnee": (schnee, "Schneeanteil am Winterniederschlag"),
    "intensitaet": (intensitaet, "Wie schnell der Regen fiel"),
    "streifen": (streifen, "Jeder Regentag als Streifen"),
    "kumulativ": (kumulativ, "Niederschlag im Jahresverlauf"),
}


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.set_defaults(format="jpg")
    ap.add_argument("--art", choices=list(ARTEN), default="konzentration")
    ap.add_argument("--jahr", type=int, help="welches Jahr, wo eines gebraucht wird")
    ap.add_argument("--jahre", type=int, default=8,
                    help="nur bei streifen: wie viele Jahre, 0 für alle")
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
