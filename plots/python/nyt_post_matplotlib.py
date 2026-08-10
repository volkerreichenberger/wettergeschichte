#!/usr/bin/env python3
"""NYT-Diagramm als quadratischer Beitrag: nur die Grafik, Text in eigener Datei.

Zeiträume über ``--zeitraum``:

* ``jahr``      das laufende Kalenderjahr
* ``quartal``   ein festes Kalenderquartal (Jan–Mär, Apr–Jun, Jul–Sep, Okt–Dez),
                ausgewählt über ``--zurueck`` (0 = laufendes Quartal)
* ``monate``    die letzten n Monate, gleitend, Anzahl über ``--months``
* ``serie``     das Ganzjahresbild und die vier jüngsten Quartale als
                Bilderfolge für einen Karussell-Beitrag

Die Quartale sind bewusst starr am Kalender ausgerichtet: am 1. April springt
die Scheibe um, und das neue Quartal zeigt zunächst nur einen Tag. Dafür sind
die Bilder untereinander vergleichbar, und die drei Vorgänger reichen bei
Bedarf ins Vorjahr zurück.

Das Bild trägt keinen Titel und keine Fußzeile; alles Textliche steht in der
``text.txt`` daneben. Beides landet in ``posts/<name>/``.

    python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum serie
    python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum quartal --zurueck 2
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg
from nyt_matplotlib import draw, style, window_from_months

SIZE_PX = 1080

#: Wie viele Quartale die Serie zeigt (neben dem Ganzjahresbild).
SERIE_QUARTALE = 4

QUARTAL_NAMEN = [
    "Januar bis März", "April bis Juni", "Juli bis September", "Oktober bis Dezember",
]


def quartal_window(q: int) -> tuple[int, int]:
    """Tagesbereich eines Quartals (0 = Jan–Mär) im 365-Tage-Schema."""
    start = wg.MONTH_STARTS[q * 3]
    end = wg.MONTH_STARTS[(q + 1) * 3] - 1 if q < 3 else wg.MONTH_END
    return start, end


def quartal_of(month: int) -> int:
    return (month - 1) // 3


def shift_quartal(year: int, q: int, zurueck: int) -> tuple[int, int]:
    """``zurueck`` Quartale zurückgehen – das läuft über Jahresgrenzen hinweg."""
    total = year * 4 + q - zurueck
    return total // 4, total % 4


def load_year(station: int, year: int, derived: Path):
    try:
        return wg.load(station, year, derived)
    except SystemExit as exc:
        raise SystemExit(
            f"{exc}\n\nFür Quartale, die ins Vorjahr reichen, werden auch dessen "
            f"Kennzahlen gebraucht:\n  python climatology.py --year {year}"
        ) from None


# --------------------------------------------------------------------------- #
# Zeichnen
# --------------------------------------------------------------------------- #

#: Größe des Legendenkastens als Anteil der Zeichenfläche – grob, aber genau
#: genug, um die freieste Ecke zu bestimmen.
LEGEND_W, LEGEND_H = 0.52, 0.28

LEGEND_ANCHOR = {
    "upper left": (0.005, 0.995), "upper right": (0.995, 0.995),
    "lower left": (0.005, 0.005), "lower right": (0.995, 0.005),
}


def free_corner(clim, year_df, window, ylim) -> str:
    """Sucht die Ecke, in der am wenigsten Daten liegen.

    Eine feste Ecke geht schief: über ein Winterquartal ist oben Platz, über
    ein Sommerquartal unten – mit fester Vorgabe deckt die Legende genau die
    Hitzetage zu, um die es geht.
    """
    lo, hi = window
    bottom, top = ylim
    span, height = hi - lo, top - bottom
    c = clim[(clim["doy"] >= lo) & (clim["doy"] <= hi)]
    y = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)]

    counts = {}
    for corner in LEGEND_ANCHOR:
        vertical, horizontal = corner.split()
        x_from = lo if horizontal == "left" else hi - LEGEND_W * span
        x_to = x_from + LEGEND_W * span
        if vertical == "upper":
            edge = top - LEGEND_H * height
            in_x = (c["doy"] >= x_from) & (c["doy"] <= x_to)
            hits = int((c.loc[in_x, "record_high"] >= edge).sum())
            in_xy = (y["doy"] >= x_from) & (y["doy"] <= x_to)
            hits += int((y.loc[in_xy, "temp_max_c"] >= edge).sum())
        else:
            edge = bottom + LEGEND_H * height
            in_x = (c["doy"] >= x_from) & (c["doy"] <= x_to)
            hits = int((c.loc[in_x, "record_low"] <= edge).sum())
            in_xy = (y["doy"] >= x_from) & (y["doy"] <= x_to)
            hits += int((y.loc[in_xy, "temp_min_c"] <= edge).sum())
        counts[corner] = hits
    return min(counts, key=lambda k: (counts[k], list(LEGEND_ANCHOR).index(k)))


def legend(ax, summary, loc: str) -> None:
    anchor = LEGEND_ANCHOR[loc]
    handles = [
        Patch(facecolor=wg.RECORD_BAND, label=f"Min/Max seit {summary['record_from']}"),
        Line2D([], [], color=wg.BAR_NEUTRAL, lw=3.5, label=f"Tagesspanne {summary['year']}"),
        Patch(facecolor=wg.NORMAL_BAND,
              label=f"Normal {summary['reference_from']}–{summary['reference_to']}"),
        Line2D([], [], color=wg.WARM, lw=3.5, label="über der Normalspanne"),
        Line2D([], [], marker="o", color="none", markerfacecolor=wg.WARM,
               markeredgecolor="white", markersize=6.5, label="neuer Tagesrekord"),
        Line2D([], [], color=wg.COLD, lw=3.5, label="unter der Normalspanne"),
    ]
    leg = ax.legend(handles=handles, loc=loc, bbox_to_anchor=anchor,
                    frameon=True, framealpha=0.93, edgecolor=wg.GRID,
                    facecolor=wg.BACKGROUND, fontsize=8.5, handlelength=1.5,
                    borderpad=0.7, labelspacing=0.45, ncols=2, columnspacing=1.1)
    leg.get_frame().set_linewidth(0.5)
    leg.set_zorder(9)


def render(clim, year_df, summary, window, path, args, ylim=None, mit_legende=True) -> None:
    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    # Oben Luft für die Einheit, die über der Skala steht.
    ax = fig.add_axes((0.105, 0.075, 0.875, 0.865))

    draw(clim, year_df, summary, ax, window, ylim)
    if mit_legende:
        legend(ax, summary, free_corner(clim, year_df, window, ax.get_ylim()))

    ax.set_ylabel("°C", rotation=0, loc="top", labelpad=-16, fontsize=11,
                  color=wg.TEXT_MUTED)
    # draw() setzt Gradzeichen an jeden Tick; neben der Einheit über der Skala
    # wären sie doppelt. Der oberste Tick fliegt raus, sonst schiebt er sich
    # unter das "°C".
    bottom, top = ax.get_ylim()
    ticks = [t for t in ax.get_yticks() if bottom + 0.5 <= t <= top - 1.5]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{int(t)}" for t in ticks], fontsize=11)

    save_kwargs = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(path, dpi=args.dpi, **save_kwargs)
    plt.close(fig)


def render_legende(summary, path, args) -> None:
    """Die Legende als eigenes Schlussbild der Serie.

    So bleiben die Diagramme frei von Kästen, die sonst genau die Tage
    verdecken, um die es geht. Die Beschriftungen sind länger als in einer
    eingebetteten Legende – hier ist Platz dafür.
    """
    jahre = int(summary["record_to"]) - int(summary["record_from"]) + 1
    handles = [
        # Kontur, sonst verschwindet das helle Beige auf dem weißen Grund.
        (Patch(facecolor=wg.RECORD_BAND, edgecolor=wg.GRID, linewidth=0.8),
         f"höchster und tiefster Wert dieses\nKalendertags – {jahre} Jahre seit "
         f"{summary['record_from']}"),
        (Patch(facecolor=wg.NORMAL_BAND, edgecolor=wg.GRID, linewidth=0.8),
         f"Normalbereich der Periode\n{summary['reference_from']}–{summary['reference_to']}"),
        (Line2D([], [], color=wg.BAR_NEUTRAL, lw=9),
         f"ein Tag {summary['year']}, von der Tiefst-\nbis zur Höchsttemperatur"),
        (Line2D([], [], color=wg.WARM, lw=9), "über dem Normalbereich"),
        (Line2D([], [], color=wg.COLD, lw=9), "unter dem Normalbereich"),
        (Line2D([], [], marker="o", color="none", markerfacecolor=wg.WARM,
                markeredgecolor="white", markersize=15),
         "an diesem Kalendertag war es\nnoch nie so warm"),
        (Line2D([], [], marker="o", color="none", markerfacecolor=wg.COLD,
                markeredgecolor="white", markersize=15),
         "noch nie so kalt"),
    ]

    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.axis("off")
    leg = ax.legend([h for h, _ in handles], [t for _, t in handles],
                    loc="center", frameon=False, fontsize=15, handlelength=1.8,
                    handletextpad=1.4, labelspacing=1.5, borderpad=0)
    for text in leg.get_texts():
        text.set_color(wg.TEXT)

    save_kwargs = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(path, dpi=args.dpi, **save_kwargs)
    plt.close(fig)


def common_ylim(panels) -> tuple[float, float]:
    """Eine Skala für alle Bilder der Serie – sonst täuscht das Blättern."""
    lows, highs = [], []
    for clim, year_df, _summary, (lo, hi) in panels:
        c = clim[(clim["doy"] >= lo) & (clim["doy"] <= hi)]
        y = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)]
        lows.append(min(c["record_low"].min(), y["temp_min_c"].min()))
        highs.append(max(c["record_high"].max(), y["temp_max_c"].max()))
    return min(lows) - 2, max(highs) + 6


# --------------------------------------------------------------------------- #
# Begleittext
# --------------------------------------------------------------------------- #

def erklaerung(summary) -> str:
    """Die Bildlegende in Worten – die Quartalsbilder tragen keine mehr.

    Bewusst über die Farben statt über Fachbegriffe: wer das Bild im Feed
    sieht, hat keine Legende daneben.
    """
    jahre = int(summary["record_to"]) - int(summary["record_from"]) + 1
    return (
        "So liest sich das Bild:\n"
        f"· Die hellbraune Fläche ist die Spanne zwischen dem tiefsten und dem "
        f"höchsten Wert, der an diesem Kalendertag je gemessen wurde – "
        f"{jahre} Jahre seit {summary['record_from']}.\n"
        f"· Die dunkelbraune Fläche darin ist der Normalbereich: das mittlere "
        f"Tagesminimum und -maximum der Periode {summary['reference_from']}–"
        f"{summary['reference_to']}.\n"
        "· Jeder senkrechte Balken ist ein Tag, von der Tiefst- bis zur "
        "Höchsttemperatur. Grau, solange er im Normalbereich bleibt.\n"
        "· Rot ist der Teil eines Tages oberhalb des Normalbereichs, blau der "
        "darunter.\n"
        "· Ein roter Punkt heißt: an diesem Kalendertag war es noch nie so warm. "
        "Ein blauer Punkt: noch nie so kalt."
    )


def kennzahlen(clim, year_df, summary, window) -> tuple[str, float]:
    """Aufzählung für den Begleittext plus die Abweichung zur Normalperiode."""
    lo, hi = window
    sub = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)].dropna(subset=["temp_mean_c"])
    if sub.empty:
        return "", 0.0
    normal = clim.loc[clim["doy"].isin(sub["doy"]), "normal_mean"].mean()
    mean = sub["temp_mean_c"].mean()
    hottest = sub.loc[sub["temp_max_c"].idxmax()]
    coldest = sub.loc[sub["temp_min_c"].idxmin()]
    warm = "wärmer" if mean > normal else "kühler"
    text = (
        f"· Mittel {wg.de_num(mean)} °C, {wg.de_num(abs(mean - normal))} K {warm} als normal"
        f"\n· Höchstwert {wg.de_num(hottest['temp_max_c'])} °C am {wg.de_date(hottest['date'])}"
        f"\n· Tiefstwert {wg.de_num(coldest['temp_min_c'])} °C am {wg.de_date(coldest['date'])}"
        f"\n· {int((sub['temp_max_c'] >= 30).sum())} Tage mit 30 °C oder mehr, "
        f"{int((sub['temp_min_c'] < 0).sum())} Frosttage"
        f"\n· {int(sub['precip_mm'].sum())} mm Niederschlag"
    )
    return text, float(mean - normal)


def caption_single(clim, year_df, summary, window, ueberschrift: str) -> str:
    text, _ = kennzahlen(clim, year_df, summary, window)
    lo, hi = window
    sub = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)].dropna(subset=["temp_mean_c"])
    spanne = f"{wg.de_date(sub['date'].min())} bis {wg.de_date(sub['date'].max())} {sub['date'].max().year}"
    return (
        f"{summary['station_name']}: {ueberschrift}\n\n"
        + erklaerung(summary)
        + f"\n\n{spanne}\n{text}"
        + f"\n\nDaten: Deutscher Wetterdienst, Climate Data Center (opendata.dwd.de), "
          f"Station {summary['station_id']}. Stand {summary['last_date']}."
        + f"\n\n{wg.HASHTAGS}"
    )


def caption_serie(panels, labels, summary) -> str:
    """Ein Text für den ganzen Karussell-Beitrag, Bild für Bild."""
    zeilen = []
    for (clim, year_df, s, window), label in zip(panels, labels):
        _text, abweichung = kennzahlen(clim, year_df, s, window)
        if not _text:
            zeilen.append(f"· {label}: noch keine Daten")
            continue
        richtung = "über" if abweichung > 0 else "unter"
        zeilen.append(f"· {label}: {wg.de_num(abs(abweichung))} K {richtung} dem Normalwert")

    haupt, *_ = panels
    text, _ = kennzahlen(*haupt[:3], haupt[3])
    return (
        f"{summary['station_name']}: das Jahr {summary['year']} und die vier "
        f"jüngsten Quartale\n\n"
        + erklaerung(summary)
        + "\n\nAlle Bilder teilen sich dieselbe Temperaturskala und sind damit "
          "unmittelbar vergleichbar. Zum Blättern nach rechts wischen – das "
          "laufende Quartal steht am Ende, dahinter die Legende."
        + "\n\nIm Bilderlauf:\n" + "\n".join(zeilen)
        + f"\n\n{summary['year']} bisher:\n{text}"
        + f"\n\nDaten: Deutscher Wetterdienst, Climate Data Center (opendata.dwd.de), "
          f"Station {summary['station_id']}. Stand {summary['last_date']}."
        + f"\n\n{wg.HASHTAGS}"
    )


# --------------------------------------------------------------------------- #
# Ablauf
# --------------------------------------------------------------------------- #


def build_serie(args) -> Path:
    """Ganzjahresbild plus die vier jüngsten Quartale, aktuelles Quartal zuletzt."""
    clim, year_df, _recent, summary = load_year(args.station, args.year, args.derived)
    last = year_df["date"].max()
    q_now = quartal_of(last.month)

    panels = [(clim, year_df, summary, (1, wg.MONTH_END))]
    labels = [f"das Jahr {summary['year']}"]

    # Rückwärts sammeln, danach umdrehen: das laufende Quartal soll ans Ende.
    quartale = []
    cache = {args.year: (clim, year_df, summary)}
    for zurueck in range(SERIE_QUARTALE):
        year, q = shift_quartal(int(last.year), q_now, zurueck)
        if year not in cache:
            c, y, _r, s = load_year(args.station, year, args.derived)
            cache[year] = (c, y, s)
        c, y, s = cache[year]
        quartale.append(((c, y, s, quartal_window(q)), f"{QUARTAL_NAMEN[q]} {year}"))
    for panel, label in reversed(quartale):
        panels.append(panel)
        labels.append(label)

    ylim = common_ylim(panels)

    slug = f"nyt_serie_{args.station:05d}_{summary['last_date']}"
    out = wg.post_dir(slug, args.posts)
    for alt in out.glob("bild_*.jpg"):
        alt.unlink()  # Reste eines früheren Laufs mit anderer Bildzahl

    for i, ((c, y, s, window), label) in enumerate(zip(panels, labels), start=1):
        path = out / f"bild_{i}.{args.format}"
        render(c, y, s, window, path, args, ylim, mit_legende=False)
        print(f"geschrieben: {path}  ({label})")

    # Die Legende bekommt ein eigenes Schlussbild statt eines Kastens im
    # Diagramm; im Karussell wischt man am Ende darauf.
    legende = out / f"bild_{len(panels) + 1}.{args.format}"
    render_legende(summary, legende, args)
    print(f"geschrieben: {legende}  (Legende)")

    text = out / "text.txt"
    text.write_text(caption_serie(panels, labels, summary), encoding="utf-8")
    print(f"geschrieben: {text}")
    return out


def build_single(args) -> Path:
    style()
    if args.zeitraum == "quartal":
        clim, year_df, _r, summary = load_year(args.station, args.year, args.derived)
        year, q = shift_quartal(int(year_df["date"].max().year),
                                quartal_of(year_df["date"].max().month), args.zurueck)
        if year != args.year:
            clim, year_df, _r, summary = load_year(args.station, year, args.derived)
        window = quartal_window(q)
        ueberschrift = f"{QUARTAL_NAMEN[q]} {year}"
        suffix = f"q{q + 1}_{year}"
    elif args.zeitraum == "monate":
        clim, year_df, _r, summary = load_year(args.station, args.year, args.derived)
        window = window_from_months(year_df, args.months)
        ueberschrift = f"die letzten {args.months} Monate"
        suffix = f"{args.months}monate"
    else:
        clim, year_df, _r, summary = load_year(args.station, args.year, args.derived)
        window = (1, wg.MONTH_END)
        ueberschrift = f"das Jahr {summary['year']}"
        suffix = "jahr"

    slug = f"nyt_{suffix}_{args.station:05d}_{summary['last_date']}"
    out = wg.post_dir(slug, args.posts)
    image = out / f"bild.{args.format}"
    render(clim, year_df, summary, window, image, args,
           mit_legende=(args.zeitraum == "jahr"))
    text = out / "text.txt"
    text.write_text(caption_single(clim, year_df, summary, window, ueberschrift),
                    encoding="utf-8")
    print(f"geschrieben: {image}\ngeschrieben: {text}")
    return out


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.set_defaults(format="jpg")  # Instagram nimmt nur JPEG entgegen
    ap.add_argument("--zeitraum", choices=["jahr", "quartal", "monate", "serie"],
                    default="serie")
    ap.add_argument("--zurueck", type=int, default=0,
                    help="nur bei --zeitraum quartal: wie viele Quartale zurück (0 = laufendes)")
    ap.add_argument("--months", type=int, default=3,
                    help="nur bei --zeitraum monate: Anzahl der Monate")
    ap.add_argument("--posts", type=Path, default=wg.POSTS)
    ap.add_argument("--jpeg-quality", type=int, default=92)
    args = ap.parse_args(argv)

    style()
    out = build_serie(args) if args.zeitraum == "serie" else build_single(args)
    # Letzte Zeile maschinenlesbar, damit post_daily.sh den Ordner findet.
    print(f"POST_DIR={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
