#!/usr/bin/env python3
"""Bewölkung als Kalenderblatt – ein Feld je Tag, ein Bild je Jahr.

Die Farbe zeigt den Tagesmittelwert des Bedeckungsgrades: strahlendes Blau für
wolkenlos, Grau für bedeckt. Der DWD gibt ihn in Achteln an (0 bis 8), die
meteorologische Einheit Okta.

Der Beitrag ist ein Karussell: derselbe Monat im laufenden Jahr zuerst, dahinter
die Vorjahre in absteigender Folge. Alle Bilder teilen dieselbe Farbskala – sie
ist an die Achtel gebunden, nicht an den Wertebereich des jeweiligen Monats,
und damit ohne Zutun vergleichbar.

Vorgabe ist der **laufende** Monat: das Kalenderblatt reicht bis zum letzten Tag,
für den Daten vorliegen, der Rest bleibt als gestrichelter Umriss leer. Die
Vorjahre dahinter sind immer ganze Monate – nur so sieht man, worauf der
laufende Monat zusteuert. Der Begleittext sagt deshalb, bis wann gemessen ist,
und verkneift sich einen Rang, solange der Monat läuft.

Der Beitrag entsteht ab dem ersten gemessenen Tag – am Monatsanfang also mit
einem einzelnen Kästchen, das dann Tag für Tag Gesellschaft bekommt. Nur wenn
gar kein Tag vorliegt oder mehr als ``--max-fehlend`` Werte fehlen, endet das
Skript mit Rückgabewert 3 – ``post_daily.py`` wertet das als „nichts zu tun“
und nicht als Fehler. Ein abgeschlossener Monat,
den es schon als Ordner gibt, wird ebenfalls übersprungen; er ändert sich nicht
mehr, und ein zweiter Lauf hieße ein zweiter Beitrag. Der laufende Monat wird
dagegen bei jedem Lauf neu gezeichnet, weil täglich ein Feld dazukommt.

**Station:** Vorgabe ist 4928 Schnarrenberg, nicht 4931 wie im übrigen Projekt.
An 4931 fehlt der Bedeckungsgrad von Juni 2022 bis August 2023 vollständig.

    python plots/python/bewoelkung_matplotlib.py
    python plots/python/bewoelkung_matplotlib.py --monat 2026-06 --force
"""

from __future__ import annotations

import calendar
import sys
from datetime import date
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgb

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg

SIZE_PX = 1080

#: Rückgabewert, wenn es schlicht nichts zu tun gibt (Monat noch nicht
#: vollständig oder schon gebaut). Kein Fehler – post_daily.sh trennt das.
NICHTS_ZU_TUN = 3

#: Bewölkung wird an 4928 gemessen; 4931 hat eine 15-Monats-Lücke (2022/23).
STATION_BEWOELKUNG = 4928

#: Skalen von wolkenlos nach bedeckt, fest an 0 bis 8 Achtel gebunden.
#: „blau" liest den Himmel, „gelb" die Sonne. Gelb läuft über ein helles
#: Sandton-Mittel statt direkt ins Grau – die direkte Mischung wird kakifarben.
SKALEN = {
    "blau": ["#1f7ae0", "#7ea6cf", "#adb5bd", "#8d9296"],
    "gelb": ["#f9c22e", "#f2e3b3", "#d5d8db", "#8d9296"],
    # Himmel für den Sonnen-Stil: von klarem Blau ins Wolkengrau.
    "sonne": ["#2f80ed", "#6f9ed6", "#a8b2bb", "#8d9296"],
}
OKTA_MAX = 8

#: Farbe der Sonnenscheibe im Stil „sonne".
SONNENGELB = "#ffcc2f"


def cmap(name: str) -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list(f"bewoelkung_{name}", SKALEN[name])

#: Wie viele Tage im Monat fehlen dürfen, ohne dass der Beitrag verschoben wird.
#: Null wäre zu streng: ein einzelner Messausfall würde den Monatsbeitrag sonst
#: für immer blockieren. Fehlende Tage bleiben im Bild leer und werden im
#: Begleittext benannt.
MAX_FEHLEND = 2

#: So viele Tage muss der laufende Monat haben, bevor ein Beitrag entsteht.
#: Eins heißt: sobald ein Tag gemessen ist, gibt es den Beitrag – am
#: Monatsanfang also ein einzelnes Kästchen. Das ist gewollt; die Reihe wächst
#: dann Tag für Tag mit. Null Tage bleiben der einzige Grund auszusetzen, und
#: der tritt genau am Ersten ein, solange der DWD den Vortag noch nachschiebt.
MIN_TAGE = 1


def feld(spalte: int, zeile: int, farbe, stil: str, rand=None, strichelt=False):
    """Grundform einer Tageszelle: Kreis bei „gelb", sonst Quadrat."""
    gemeinsam = dict(facecolor=farbe,
                     edgecolor=rand or wg.BACKGROUND,
                     linewidth=1.2 if strichelt else 1.5,
                     linestyle=(0, (3, 3)) if strichelt else "solid")
    if stil == "gelb":
        return plt.Circle((spalte + 0.5, zeile + 0.5), 0.44, **gemeinsam)
    return plt.Rectangle((spalte + 0.04, zeile + 0.04), 0.92, 0.92, **gemeinsam)


#: Radius der Sonnenscheibe, als Anteil der Zellenbreite. Sie bleibt immer
#: gleich groß; verändert wird nur, wie deutlich sie zu sehen ist.
SONNE_R = 0.19


def sonnenfarbe(okta: float, himmel):
    """Sonnenfarbe bei gegebenem Bedeckungsgrad.

    Der Bedeckungsgrad in Achteln ist der Anteil des Himmels, den Wolken
    verdecken; sichtbar bleibt ``1 - okta/8``. Genau dieser Anteil wird hier
    als Deckkraft gelesen und über den Himmel gerechnet – bei 8 Achteln geht
    die Scheibe vollständig in der Wolkendecke auf.
    """
    sichtbar = max(0.0, 1.0 - okta / OKTA_MAX)
    gelb = to_rgb(SONNENGELB)
    grund = to_rgb(himmel)
    return tuple(sichtbar * g + (1 - sichtbar) * b for g, b in zip(gelb, grund))


def sonnenzelle(ax, spalte: int, zeile: int, okta: float, himmel) -> None:
    """Blaues Himmelsquadrat mit Sonne rechts oben."""
    ax.add_patch(plt.Rectangle((spalte + 0.04, zeile + 0.04), 0.92, 0.92,
                               facecolor=himmel, edgecolor=wg.BACKGROUND,
                               linewidth=1.5))
    ax.add_patch(plt.Circle((spalte + 0.70, zeile + 0.30), SONNE_R,
                            facecolor=sonnenfarbe(okta, himmel),
                            edgecolor="none", zorder=3))


def lade(data_dir: Path, station: int) -> pd.DataFrame:
    path = data_dir / "stations" / f"{station:05d}" / "daily.csv"
    if not path.exists():
        raise SystemExit(f"{path} fehlt – bitte zuerst 'python fetch_dwd.py' laufen lassen.")
    return pd.read_csv(path, parse_dates=["date"], usecols=["date", "cloud_cover_okta"])


def monatswerte(df: pd.DataFrame, monat: str) -> pd.DataFrame:
    p = pd.Period(monat, freq="M")
    sub = df[(df["date"] >= p.start_time) & (df["date"] <= p.end_time)]
    return sub.dropna(subset=["cloud_cover_okta"])


def aktueller_monat(heute: date) -> str:
    return f"{heute.year:04d}-{heute.month:02d}"


def stand_im_monat(df: pd.DataFrame, monat: str) -> int:
    """Bis zu welchem Tag des Monats Daten vorliegen.

    Maßgeblich ist der letzte Tag, an dem die Station überhaupt gemeldet hat,
    nicht der letzte Tag mit Bedeckungsgrad: fehlt der Wert von gestern, ist das
    eine Lücke im Monat und soll als leeres Feld sichtbar bleiben, nicht den
    Monat stillschweigend einen Tag früher enden lassen.
    """
    p = pd.Period(monat, freq="M")
    stand = df["date"].max()
    if pd.isna(stand) or stand >= p.end_time:
        return p.days_in_month
    if stand < p.start_time:
        return 0
    return int(stand.day)


def zeichne(sub: pd.DataFrame, monat: str, station: int, station_name: str,
            path: Path, args) -> None:
    """Ein Kalenderblatt, nur Titel und Raster.

    Bis wann der laufende Monat reicht, steht nicht im Bild: Es sagen schon
    die leeren Felder, und eine zweite Zeile unter der Ueberschrift lief in
    schmalen Schriften mit dem Titel zusammen.
    """
    skala = cmap(args.stil)
    p = pd.Period(monat, freq="M")
    werte = dict(zip(sub["date"].dt.day, sub["cloud_cover_okta"]))
    wochen = calendar.Calendar(firstweekday=0).monthdayscalendar(p.year, p.month)

    plt.rcParams.update({**wg.rc_font(),
                         "figure.facecolor": wg.BACKGROUND,
                         "savefig.facecolor": wg.BACKGROUND,
                         "text.color": wg.TEXT})

    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    ax = fig.add_axes((0.07, 0.17, 0.86, 0.60))
    ax.set_xlim(0, 7)
    ax.set_ylim(len(wochen), 0)   # erste Woche oben
    ax.axis("off")
    # Ohne gleiche Skalierung werden aus Kreisen Ellipsen, sobald ein Monat
    # sechs statt fünf Wochen hat. anchor="N" hängt das Raster oben an.
    ax.set_aspect("equal", adjustable="box", anchor="N")

    for zeile, woche in enumerate(wochen):
        for spalte, tag in enumerate(woche):
            if tag == 0:
                continue
            okta = werte.get(tag)
            if okta is None:
                # Kein Messwert: leere Form mit gestricheltem Umriss, damit sie
                # sich vom Rand des Monats unterscheidet.
                ax.add_patch(feld(spalte, zeile, wg.BACKGROUND, args.stil,
                                  rand=wg.GRID, strichelt=True))
                continue
            if args.stil == "sonne":
                sonnenzelle(ax, spalte, zeile, okta, skala(okta / OKTA_MAX))
            else:
                ax.add_patch(feld(spalte, zeile, skala(okta / OKTA_MAX), args.stil))

    for spalte, name in enumerate(wg.WEEKDAYS_SHORT):
        ax.text(spalte + 0.5, -0.18, name, ha="center", va="bottom",
                fontsize=15, color=wg.TEXT_MUTED)

    fig.text(0.07, 0.955, f"Bewölkung {wg.MONTH_NAMES_LONG[p.month - 1]} {p.year}",
             fontsize=27, fontweight="bold", va="top")

    bar = fig.add_axes((0.07, 0.085, 0.50, 0.028))
    bar.imshow([[i / 100 for i in range(101)]], aspect="auto", cmap=skala)
    bar.set_xticks([]); bar.set_yticks([])
    for seite in bar.spines.values():
        seite.set_visible(False)
    fig.text(0.07, 0.062, "wolkenlos", fontsize=11, color=wg.TEXT_MUTED, va="top")
    fig.text(0.57, 0.062, "bedeckt", fontsize=11, color=wg.TEXT_MUTED, va="top", ha="right")

    save = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(path, dpi=args.dpi, **save)
    plt.close(fig)


#: So viele Tage muss ein Monat haben, damit sein Mittel im Streifen zählt.
MIN_TAGE_STREIFEN = 25


def monatsreihe(df: pd.DataFrame, monat_nr: int) -> pd.Series:
    """Monatsmittel je Jahr, mit None für Jahre ohne belastbare Messung.

    Der Index läuft lückenlos über alle Jahre – auch über die ohne Daten. Sonst
    würde der Streifen die Zeitachse stauchen und die Lücke verschwiegen.
    """
    sub = df[df["date"].dt.month == monat_nr].dropna(subset=["cloud_cover_okta"])
    gruppe = sub.groupby(sub["date"].dt.year)["cloud_cover_okta"]
    mittel, tage = gruppe.mean(), gruppe.count()
    gueltig = mittel.where(tage >= MIN_TAGE_STREIFEN)
    return gueltig.reindex(range(int(mittel.index.min()), int(mittel.index.max()) + 1))


def zeichne_streifen(df: pd.DataFrame, monat_nr: int, jahre_wunsch, path: Path,
                     args, laufendes_jahr: int) -> None:
    """Je Jahr eine flache Zeile, ein Streifen je Tag – neuestes Jahr oben.

    Das ist der lange Blick: dieselbe Farbskala wie in den Kalenderblättern,
    aber alle gemessenen Jahre übereinander statt sechs nebeneinander. Die
    Vorjahre stehen immer als ganze Monate da; nur die oberste Zeile hört auf,
    wo die Daten des laufenden Monats aufhören.
    """
    skala = cmap(args.stil)
    name = wg.MONTH_NAMES_LONG[monat_nr - 1]

    sub = df[df["date"].dt.month == monat_nr].dropna(subset=["cloud_cover_okta"])
    sub = sub.assign(jahr=sub["date"].dt.year, tag=sub["date"].dt.day)
    tage_je_jahr = sub.groupby("jahr")["tag"].count()
    # Das laufende Jahr darf die Mindestzahl unterschreiten – es ist ja der
    # Anlass des Beitrags. Für die Vorjahre bleibt die Schwelle streng.
    genug = tage_je_jahr[(tage_je_jahr >= MIN_TAGE_STREIFEN)
                         | (tage_je_jahr.index == laufendes_jahr)]
    jahre = sorted((j for j in genug.index if j in jahre_wunsch), reverse=True)
    tage_im_monat = 31 if monat_nr in (1, 3, 5, 7, 8, 10, 12) else 30

    plt.rcParams.update({**wg.rc_font(),
                         "figure.facecolor": wg.BACKGROUND,
                         "savefig.facecolor": wg.BACKGROUND,
                         "text.color": wg.TEXT})

    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    # Höhe an die Zeilenzahl koppeln, sonst werden aus sechs Jahren Balken.
    hoehe = min(0.63, 0.055 * len(jahre) + 0.05)
    ax = fig.add_axes((0.145, 0.78 - hoehe, 0.80, hoehe))
    ax.set_xlim(1, tage_im_monat + 1)
    ax.set_ylim(len(jahre), 0)
    ax.axis("off")

    werte = {(j, tag): v for j, tag, v in
             zip(sub["jahr"], sub["tag"], sub["cloud_cover_okta"])}
    for zeile, jahr in enumerate(jahre):
        for tag in range(1, tage_im_monat + 1):
            okta = werte.get((jahr, tag))
            if okta is None:
                continue
            ax.add_patch(plt.Rectangle((tag, zeile + 0.08), 1, 0.84,
                                       facecolor=skala(okta / OKTA_MAX), linewidth=0))
        # Bei 60 Zeilen überschreiben sich Jahreszahlen an jeder Zeile.
        # Beschriftet werden deshalb nur das neueste Jahr und jedes zehnte.
        # Bei vielen Zeilen überschreiben sich die Jahreszahlen; dann nur das
        # neueste Jahr und jede volle Dekade beschriften.
        if len(jahre) <= 12 or zeile == 0 or jahr % 10 == 0:
            ax.text(0.4, zeile + 0.5, str(jahr), ha="right", va="center",
                    fontsize=13 if len(jahre) <= 12 else 11,
                    color=wg.TEXT if zeile == 0 else wg.TEXT_MUTED,
                    fontweight="bold" if zeile == 0 else "normal")

    for tag in (1, 10, 20, tage_im_monat):
        ax.text(tag + 0.5, len(jahre) + 0.35, str(tag), ha="center", va="top",
                fontsize=10, color=wg.TEXT_MUTED)

    fig.text(0.07, 0.955, f"{name} {jahre[-1]} bis {jahre[0]}",
             fontsize=27, fontweight="bold", va="top")
    fig.text(0.07, 0.876,
             "Stuttgart · eine Zeile je Jahr, ein Streifen je Tag",
             fontsize=14, color=wg.TEXT_MUTED, va="top")

    fehlend = [j for j in range(jahre[-1], jahre[0] + 1) if j not in jahre]
    if fehlend:
        fig.text(0.07, 0.128,
                 "Ohne durchgehende Messung und deshalb nicht dargestellt: "
                 + ", ".join(str(j) for j in fehlend) + ".",
                 fontsize=10.5, color=wg.TEXT_MUTED, va="top")

    bar = fig.add_axes((0.07, 0.062, 0.50, 0.026))
    bar.imshow([[i / 100 for i in range(101)]], aspect="auto", cmap=skala)
    bar.set_xticks([]); bar.set_yticks([])
    for seite in bar.spines.values():
        seite.set_visible(False)
    fig.text(0.07, 0.042, "wolkenlos", fontsize=11, color=wg.TEXT_MUTED, va="top")
    fig.text(0.57, 0.042, "bedeckt", fontsize=11, color=wg.TEXT_MUTED, va="top", ha="right")

    save = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(path, dpi=args.dpi, **save)
    plt.close(fig)


def caption(panels, monat: str, station: int, station_name: str,
            reihe: pd.Series | None = None, bis_tag: int | None = None) -> str:
    """panels: Liste (monat, DataFrame) – das laufende Jahr zuerst.

    ``bis_tag`` gesetzt heißt: der Monat läuft noch und reicht nur bis dahin.
    Die Vorjahre sind ganze Monate, der Vergleich also vorläufig – das muss im
    Text stehen, sonst liest sich ein heiterer halber Monat als heiterer Monat.
    """
    p = pd.Period(monat, freq="M")
    name = wg.MONTH_NAMES_LONG[p.month - 1]
    aktuell = panels[0][1]["cloud_cover_okta"]
    laufend = bis_tag is not None

    zeilen = []
    luecken = []
    for i, (m, sub) in enumerate(panels):
        jahr = pd.Period(m, freq="M").year
        okta = sub["cloud_cover_okta"]
        # Für den laufenden Monat zählt nur, was bis zum Datenstand fehlt.
        soll = bis_tag if (i == 0 and laufend) else pd.Period(m, freq="M").days_in_month
        fehlt = soll - len(sub)
        bis = ("" if not (i == 0 and laufend)
               else " (nur der 1.)" if bis_tag == 1 else f" (1.–{bis_tag}.)")
        zeilen.append(f"· {jahr}{bis}: {wg.de_num(okta.mean())} Achtel im Mittel, "
                      f"{int((okta <= 2).sum())} heitere und "
                      f"{int((okta >= 6).sum())} trübe Tage")
        if fehlt > 0:
            luecken.append(f"{jahr} ({fehlt} {'Tag' if fehlt == 1 else 'Tage'})")

    mittel = [sub["cloud_cover_okta"].mean() for _, sub in panels]
    rang = sum(1 for m in mittel[1:] if m < mittel[0]) + 1

    # Am 1. gäbe „reicht bis zum 1." und „1.–1." beides Unsinn.
    einzeln = laufend and bis_tag == 1
    reicht = "zeigt bisher nur den 1." if einzeln else f"reicht bis zum {bis_tag}."
    zeitraum = "nur am 1." if einzeln else f"bis zum {bis_tag}."
    stand = (f"Der {name} {p.year} läuft noch: das erste Bild {reicht} Die "
             f"übrigen Tage sind leer. Die Vorjahre dahinter stehen als ganze "
             f"Monate da.\n\n") if laufend else ""

    vergleich = (
        f"{name} {p.year} {zeitraum}: {wg.de_num(aktuell.mean())} Achtel "
        f"im Mittel. Ein Rang lässt sich daraus noch nicht ablesen – ein "
        f"angefangener Monat und ein ganzer sind nicht dasselbe.\n\n"
        if laufend else
        f"{name} {p.year}: {wg.de_num(aktuell.mean())} Achtel im Mittel — "
        f"Platz {rang} von {len(panels)}, "
        f"{'der klarste' if rang == 1 else 'der ' + str(rang) + '. klarste'} "
        f"dieser {len(panels)} Jahre.\n\n"
    )

    text = (
        f"Bewölkung im {name} – {p.year} und die {len(panels) - 1} Jahre davor\n\n"
        f"Ein Feld je Tag, von oben links nach unten rechts durch den Monat. "
        f"Je blauer, desto klarer der Himmel; je grauer, desto bedeckter. "
        f"Alle Bilder teilen dieselbe Farbskala und sind damit unmittelbar "
        f"vergleichbar – zum Blättern nach rechts wischen.\n\n"
        + stand +
        f"Gemessen wird der Bedeckungsgrad in Achteln: 0 heißt wolkenlos, "
        f"8 geschlossene Wolkendecke. Der Wert im Bild ist das Tagesmittel.\n\n"
        + vergleich
        + "\n".join(zeilen)
    )
    if luecken:
        text += ("\n\nOhne Messwert blieben einzelne Tage; im Bild sind sie leer: "
                 + ", ".join(luecken) + ".")

    if reihe is not None:
        gueltig = reihe.dropna()
        # Der laufende Monat steht noch nicht in der Reihe – sie verlangt 25
        # gemessene Tage. Dann wird eingeordnet, was abgeschlossen ist.
        if p.year in gueltig.index:
            rang = int((gueltig < gueltig.loc[p.year]).sum()) + 1
            einordnung = (
                f"{name} {p.year} war mit {wg.de_num(gueltig.loc[p.year])} Achteln "
                f"der {rang}. klarste von {len(gueltig)} gemessenen. ")
        else:
            einordnung = (
                f"Der {name} {p.year} fehlt dort noch – er wird erst gewertet, "
                f"wenn der Monat durch ist. ")
        text += (
            f"\n\nDas letzte Bild fasst alles zusammen: ein Streifen je Jahr, "
            f"jeder {name} seit {int(gueltig.index.min())}. "
            + einordnung +
            f"Am klarsten war {int(gueltig.idxmin())} mit "
            f"{wg.de_num(gueltig.min())}, am trübsten {int(gueltig.idxmax())} mit "
            f"{wg.de_num(gueltig.max())} Achteln."
        )
    text += (
        f"\n\nDiese Reihe kommt von der Station {station} {station_name} — "
        f"anders als die übrigen Beiträge des Kanals, die von Stuttgart-"
        f"Echterdingen stammen. Dort fehlt der Bedeckungsgrad von Juni 2022 "
        f"bis August 2023 vollständig.\n"
        f"Daten: DWD Climate Data Center (opendata.dwd.de).\n\n{wg.HASHTAGS}"
    )
    return text


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.set_defaults(format="jpg", station=STATION_BEWOELKUNG)
    ap.add_argument("--monat", metavar="JJJJ-MM",
                    help="welcher Monat; Vorgabe ist der laufende")
    ap.add_argument("--jahre", type=int, default=5, help="Anzahl der Vorjahre dahinter")
    ap.add_argument("--streifen-mehr", type=int, default=3,
                    help="so viele Jahre reicht das Streifenbild weiter zurück "
                         "als die Kalenderblätter")
    ap.add_argument("--stil", choices=list(SKALEN), default="sonne",
                    help="blau = Quadrate, gelb = Kreise, sonne = Himmel mit Sonne")
    ap.add_argument("--max-fehlend", type=int, default=MAX_FEHLEND,
                    help="so viele der gemeldeten Tage dürfen ohne Messwert sein")
    ap.add_argument("--min-tage", type=int, default=MIN_TAGE,
                    help="so viele Tage muss der Monat mindestens haben")
    ap.add_argument("--data-dir", type=Path, default=wg.ROOT / "data")
    ap.add_argument("--posts", type=Path, default=wg.POSTS)
    ap.add_argument("--jpeg-quality", type=int, default=92)
    ap.add_argument("--force", action="store_true",
                    help="auch bauen, wenn der Ordner schon da ist")
    args = ap.parse_args(argv)

    monat = args.monat or aktueller_monat(date.today())
    p = pd.Period(monat, freq="M")
    slug = f"bewoelkung_{args.station:05d}_{monat}"

    df = lade(args.data_dir, args.station)
    bis_tag = stand_im_monat(df, monat)
    laufend = bis_tag < p.days_in_month

    # Ein abgeschlossener Monat ändert sich nicht mehr; ihn ein zweites Mal zu
    # bauen hieße, denselben Beitrag ein zweites Mal zu veröffentlichen. Der
    # laufende Monat dagegen wächst jeden Tag und wird deshalb neu gezeichnet.
    if not laufend and (args.posts / slug).exists() and not args.force:
        print(f"{slug} gibt es schon und {monat} ist abgeschlossen – nichts zu tun.")
        return NICHTS_ZU_TUN

    if bis_tag < args.min_tage:
        print(f"{monat}: erst {bis_tag} Tag(e) gemessen, mindestens "
              f"{args.min_tage} sollen es sein – noch nichts zu tun.")
        return NICHTS_ZU_TUN

    sub = monatswerte(df, monat)
    fehlend = bis_tag - len(sub)
    if fehlend > args.max_fehlend:
        fehlende_tage = set(range(1, bis_tag + 1)) - set(sub["date"].dt.day)
        print(f"{monat}: {fehlend} von {bis_tag} gemeldeten Tagen ohne "
              f"Bedeckungsgrad ({', '.join(str(t) + '.' for t in sorted(fehlende_tage))}) "
              f"– noch nichts zu tun.")
        return NICHTS_ZU_TUN

    # Das laufende Jahr zuerst, dann rückwärts. Jahre ohne jeden Messwert
    # fallen raus, statt als leeres Raster im Karussell zu stehen.
    panels = [(monat, sub)]
    for zurueck in range(1, args.jahre + 1):
        m = f"{p.year - zurueck:04d}-{p.month:02d}"
        s = monatswerte(df, m)
        if s.empty:
            print(f"   {m}: keine Messwerte, wird übersprungen")
            continue
        panels.append((m, s))

    station_name = wg.station_name(args.station, args.data_dir)
    out = wg.post_dir(slug, args.posts)
    for alt in out.glob("bild_*.jpg"):
        alt.unlink()

    for i, (m, s) in enumerate(panels, start=1):
        bild = out / f"bild_{i}.{args.format}"
        zeichne(s, m, args.station, station_name, bild, args)
        print(f"geschrieben: {bild}  ({m})")

    reihe = monatsreihe(df, p.month)
    streifen = out / f"bild_{len(panels) + 1}.{args.format}"
    # Das Streifenbild reicht weiter zurück als die Kalenderblätter – es ist
    # der lange Blick, und ein paar Zeilen mehr kosten dort keinen Platz.
    zurueck = args.jahre + args.streifen_mehr
    jahre_streifen = {p.year - k for k in range(zurueck + 1)}
    zeichne_streifen(df, p.month, jahre_streifen, streifen, args, p.year)
    print(f"geschrieben: {streifen}  (Streifen über alle Jahre)")

    text = out / "text.txt"
    text.write_text(caption(panels, monat, args.station, station_name, reihe,
                            bis_tag if laufend else None),
                    encoding="utf-8")
    print(f"geschrieben: {text}")
    print(f"POST_DIR={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
