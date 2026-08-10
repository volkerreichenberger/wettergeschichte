#!/usr/bin/env python3
"""NYT-Diagramm als quadratischer Beitrag: nur die Grafik, Text in eigener Datei.

Vier Zuschnitte über ``--zeitraum``:

* ``jahr``      das ganze Kalenderjahr
* ``h1``        erstes Halbjahr (Januar bis Juni)
* ``h2``        zweites Halbjahr (Juli bis Dezember)
* ``monate``    die letzten n Monate, Anzahl über ``--months``

Das Bild trägt keinen Titel und keine Fußzeile; alles Textliche steht in der
``text.txt`` daneben. Beides landet in ``posts/<name>/``.

    python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum jahr
    python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum h1
    python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum monate --months 3
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

#: 182 ist der 1. Juli im 365-Tage-Schema – die Grenze zwischen den Halbjahren.
MIDYEAR = wg.MONTH_STARTS[6]

ZEITRAUM_LABEL = {
    "jahr": "das Jahr {year}",
    "h1": "das erste Halbjahr {year}",
    "h2": "das zweite Halbjahr {year}",
}


def resolve_window(zeitraum: str, months: int, year_df) -> tuple[int, int]:
    if zeitraum == "jahr":
        return 1, wg.MONTH_END
    if zeitraum == "h1":
        # MIDYEAR ist der 1. Juli, das erste Halbjahr endet am 30. Juni.
        return 1, MIDYEAR - 1
    if zeitraum == "h2":
        return MIDYEAR, wg.MONTH_END
    return window_from_months(year_df, months)


#: Wo im Bild ist Platz für die Legende? Über das ganze Jahr und über ein
#: Halbjahr liegt die freie Fläche unten rechts, im kurzen Ausschnitt oben links.
LEGEND_LOC = {
    "jahr": ("lower right", (0.995, 0.005)),
    "h1": ("lower right", (0.995, 0.005)),
    "h2": ("lower right", (0.995, 0.005)),
    "monate": ("upper left", (0.005, 0.995)),
}


def legend(ax, summary, zeitraum: str) -> None:
    loc, anchor = LEGEND_LOC[zeitraum]
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


def caption(clim, year_df, summary, zeitraum: str, months: int, window) -> str:
    """Alles, was früher im Bild stand – Überschrift, Einordnung, Kennzahlen, Quelle."""
    lo, hi = window
    sub = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)].dropna(subset=["temp_mean_c"])
    normal = clim.loc[clim["doy"].isin(sub["doy"]), "normal_mean"].mean()
    mean = sub["temp_mean_c"].mean()
    hottest = sub.loc[sub["temp_max_c"].idxmax()]
    coldest = sub.loc[sub["temp_min_c"].idxmin()]

    if zeitraum in ZEITRAUM_LABEL:
        was = ZEITRAUM_LABEL[zeitraum].format(year=summary["year"])
    else:
        was = f"die letzten {months} Monate"

    zeitraum_text = (
        f"{wg.de_date(sub['date'].min())} bis {wg.de_date(sub['date'].max())} "
        f"{sub['date'].max().year}"
    )
    warm = "wärmer" if mean > normal else "kühler"

    return (
        f"{summary['station_name']}: {was}\n\n"
        f"Jeder Balken ist ein Tag – von der Tiefst- bis zur Höchsttemperatur. "
        f"Die beige Fläche dahinter ist der Normalbereich der Periode "
        f"{summary['reference_from']}–{summary['reference_to']}, die helle Fläche "
        f"die Spanne zwischen dem tiefsten und dem höchsten Wert, der an diesem "
        f"Kalendertag seit {summary['record_from']} je gemessen wurde. Rot und "
        f"blau sind die Teile des Tages, die aus dem Normalbereich herausragen."
        f"\n\n{zeitraum_text}"
        f"\n· Mittel {wg.de_num(mean)} °C, {wg.de_num(abs(mean - normal))} K {warm} "
        f"als normal"
        f"\n· Höchstwert {wg.de_num(hottest['temp_max_c'])} °C am "
        f"{wg.de_date(hottest['date'])}"
        f"\n· Tiefstwert {wg.de_num(coldest['temp_min_c'])} °C am "
        f"{wg.de_date(coldest['date'])}"
        f"\n· {int((sub['temp_max_c'] >= 30).sum())} Tage mit 30 °C oder mehr, "
        f"{int((sub['temp_min_c'] < 0).sum())} Frosttage"
        f"\n· {int(sub['is_record_high'].sum())} neue Tageshöchstrekorde seit "
        f"{summary['record_from']}"
        f"\n· {int(sub['precip_mm'].sum())} mm Niederschlag"
        f"\n\nDaten: Deutscher Wetterdienst, Climate Data Center "
        f"(opendata.dwd.de), Station {summary['station_id']}. "
        f"Stand {summary['last_date']}."
        f"\n\n{wg.HASHTAGS}"
    )


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.set_defaults(format="jpg")  # Instagram nimmt nur JPEG entgegen
    ap.add_argument("--zeitraum", choices=["jahr", "h1", "h2", "monate"], default="jahr")
    ap.add_argument("--months", type=int, default=3,
                    help="nur bei --zeitraum monate: Anzahl der Monate")
    ap.add_argument("--posts", type=Path, default=wg.POSTS)
    ap.add_argument("--jpeg-quality", type=int, default=92)
    args = ap.parse_args(argv)

    style()
    clim, year_df, _recent, summary = wg.load(args.station, args.year, args.derived)
    window = resolve_window(args.zeitraum, args.months, year_df)

    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    # Oben Luft für die Einheit, die über der Skala steht.
    ax = fig.add_axes((0.105, 0.075, 0.875, 0.865))

    draw(clim, year_df, summary, ax, window)
    legend(ax, summary, args.zeitraum)

    ax.set_ylabel("°C", rotation=0, loc="top", labelpad=-16, fontsize=11,
                  color=wg.TEXT_MUTED)
    # draw() setzt Gradzeichen an jeden Tick; neben der Einheit über der Skala
    # wären sie doppelt. Der oberste Tick fliegt raus, sonst schiebt er sich
    # unter das "°C".
    bottom, top = ax.get_ylim()
    ticks = [t for t in ax.get_yticks() if bottom + 0.5 <= t <= top - 1.5]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{int(t)}" for t in ticks], fontsize=11)

    suffix = f"{args.months}monate" if args.zeitraum == "monate" else args.zeitraum
    slug = f"nyt_{suffix}_{args.station:05d}_{summary['last_date']}"
    out = wg.post_dir(slug, args.posts)

    image = out / f"bild.{args.format}"
    save_kwargs = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(image, dpi=args.dpi, **save_kwargs)
    plt.close(fig)

    text = out / "text.txt"
    text.write_text(caption(clim, year_df, summary, args.zeitraum, args.months, window),
                    encoding="utf-8")

    print(f"geschrieben: {image}\ngeschrieben: {text}")
    # Letzte Zeile maschinenlesbar, damit post_daily.sh den Ordner findet,
    # ohne den Namen selbst zusammenbauen zu müssen.
    print(f"POST_DIR={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
