#!/usr/bin/env python3
"""Fünf Jahre als Min/Max-Striche hinter den Tagesbalken des laufenden Jahres.

Die Idee: das laufende Jahr wird wie im NYT-Diagramm als Tagesbalken gezeichnet
(dunkel, mit roten und blauen Spitzen jenseits der Normalspanne). Dahinter
liegen für jeden Kalendertag die Tagesminima und -maxima der fünf Vorjahre als
schmale waagerechte Striche, die mit zunehmendem Alter heller werden.

Man sieht damit unmittelbar, ob ein warmer Tag im Rahmen der letzten Jahre
liegt oder aus ihnen herausragt – etwas, das der Vergleich geglätteter
Jahresverläufe nicht zeigen kann.

    python plots/python/fuenf_jahre_striche_matplotlib.py --station 4931 --year 2026
    python plots/python/fuenf_jahre_striche_matplotlib.py --station 4931 --months 3
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
from nyt_matplotlib import BAR_FILL, bar_width, month_axis, style, window_from_months

#: Graustufen für die Vorjahre, vom jüngsten (dunkel) zum ältesten (hell).
#: Bewusst deutlich heller als BAR_NEUTRAL, damit das laufende Jahr vorne bleibt.
PAST_GREYS = ["#7a7a7a", "#969696", "#ababab", "#c0c0c0", "#d4d4d4"]

#: Halbe Breite eines Strichs in Tagen. Etwas breiter als der Balken, damit die
#: Striche ihn wie eine Klammer einfassen statt ihn zu verdecken.
TICK_HALF_WIDTH = 0.36


def draw(clim, year_df, recent, summary, ax, window, n_past: int) -> None:
    lo, hi = window
    clim = clim[(clim["doy"] >= lo) & (clim["doy"] <= hi)]
    year_df = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)]
    recent = recent[(recent["doy"] >= lo) & (recent["doy"] <= hi)]

    current = int(summary["year"])
    past_years = [y for y in sorted(recent["year"].unique()) if y < current][-n_past:]
    greys = dict(zip(reversed(past_years), PAST_GREYS))  # jüngstes Vorjahr = dunkelstes Grau

    span = hi - lo
    lw = bar_width(ax, span)
    # Die Striche skalieren mit derselben Achsenbreite wie die Balken, sind
    # aber flach: ihre Stärke ist die Linienstärke, ihre Länge die x-Ausdehnung.
    tick_lw = max(0.7, lw * 0.45)
    half = TICK_HALF_WIDTH if span < 200 else 0.5

    ax.fill_between(clim["doy"], clim["normal_low"], clim["normal_high"],
                    color=wg.NORMAL_BAND, lw=0, alpha=0.55, zorder=2)

    # Vorjahre von alt nach jung zeichnen, damit die dunklen Striche oben liegen.
    for year in past_years:
        sub = recent[recent["year"] == year].dropna(subset=["temp_min_c", "temp_max_c"])
        colour = greys[year]
        for col in ("temp_min_c", "temp_max_c"):
            ax.hlines(sub[col], sub["doy"] - half, sub["doy"] + half,
                      color=colour, lw=tick_lw, zorder=3)

    ax.vlines(year_df["doy"], year_df["bar_low"], year_df["bar_high"],
              color=wg.BAR_NEUTRAL, lw=lw, zorder=5)
    warm = year_df.dropna(subset=["warm_from", "warm_to"])
    cold = year_df.dropna(subset=["cold_from", "cold_to"])
    ax.vlines(warm["doy"], warm["warm_from"], warm["warm_to"], color=wg.WARM, lw=lw, zorder=6)
    ax.vlines(cold["doy"], cold["cold_from"], cold["cold_to"], color=wg.COLD, lw=lw, zorder=6)

    ax.axhline(0, color=wg.GRID, lw=0.8, ls=(0, (4, 4)), zorder=2)

    past = recent[recent["year"].isin(past_years)]
    ymin = min(past["temp_min_c"].min(), year_df["temp_min_c"].min()) - 2
    ymax = max(past["temp_max_c"].max(), year_df["temp_max_c"].max()) + 4
    month_axis(ax, ymin, ymax, window)

    ticks = list(range(int(ymin // 5 * 5), int(ymax) + 5, 5))
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t}°" for t in ticks], fontsize=11)
    for t in ticks:
        ax.axhline(t, color=wg.GRID, lw=0.5, alpha=0.6, zorder=1)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.set_facecolor(wg.BACKGROUND)
    return past_years, greys


def legend(ax, summary, past_years, greys) -> None:
    handles = [
        Line2D([], [], color=wg.BAR_NEUTRAL, lw=4, label=f"Tagesspanne {summary['year']}"),
        Line2D([], [], color=wg.WARM, lw=4, label="über der Normalspanne"),
        Line2D([], [], color=wg.COLD, lw=4, label="unter der Normalspanne"),
        Patch(facecolor=wg.NORMAL_BAND, alpha=0.55,
              label=f"Normalspanne {summary['reference_from']}–{summary['reference_to']}"),
    ]
    handles += [
        Line2D([], [], color=greys[y], lw=2.5, label=f"Min/Max {y}")
        for y in reversed(past_years)
    ]
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.995),
                    frameon=True, framealpha=0.93, edgecolor=wg.GRID,
                    facecolor=wg.BACKGROUND, fontsize=9, handlelength=1.6,
                    borderpad=0.8, labelspacing=0.5)
    leg.get_frame().set_linewidth(0.6)
    leg.set_zorder(9)


def stats_line(year_df, recent, past_years, window) -> str:
    """Wie oft war das laufende Jahr wärmer als alle Vorjahre am selben Tag?"""
    lo, hi = window
    cur = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)].dropna(subset=["temp_max_c"])
    past = recent[recent["year"].isin(past_years)].dropna(subset=["temp_max_c"])
    best = past.groupby("doy")["temp_max_c"].max()
    worst = past.groupby("doy")["temp_min_c"].min()

    above = int((cur["temp_max_c"] > cur["doy"].map(best)).sum())
    below = int((cur["temp_min_c"] < cur["doy"].map(worst)).sum())
    n = len(cur)
    return (
        f"An {above} von {n} Tagen lag das Maximum über allen {len(past_years)} Vorjahren, "
        f"an {below} Tagen das Minimum darunter."
    )


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.add_argument("--years", type=int, default=5, help="Anzahl der gezeigten Vorjahre")
    ap.add_argument("--months", type=int, default=None,
                    help="nur die letzten n Monate zeigen statt des ganzen Jahres")
    args = ap.parse_args(argv)

    style()
    clim, year_df, recent, summary = wg.load(args.station, args.year, args.derived)
    window = window_from_months(year_df, args.months)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.05, right=0.98, top=0.84, bottom=0.08)

    past_years, greys = draw(clim, year_df, recent, summary, ax, window, args.years)
    legend(ax, summary, past_years, greys)

    period = f"die letzten {args.months} Monate" if args.months else str(summary["year"])
    fig.text(0.05, 0.955, f"{summary['station_name']} · {period}",
             fontsize=25, fontweight="bold", ha="left", va="top")
    fig.text(0.05, 0.912,
             f"Tagesspannen {summary['year']} vor den Min/Max-Werten der "
             f"{len(past_years)} Vorjahre {past_years[0]}–{past_years[-1]} – je älter, desto heller",
             fontsize=12.5, color=wg.TEXT_MUTED, ha="left", va="top")
    fig.text(0.05, 0.878, stats_line(year_df, recent, past_years, window),
             fontsize=11, color=wg.TEXT, ha="left", va="top")
    fig.text(0.05, 0.022, wg.footer(summary) + "  ·  Grafik: matplotlib",
             fontsize=9, color=wg.TEXT_MUTED, ha="left", va="top")

    name = "fuenf_jahre_striche" + (f"_{args.months}monate" if args.months else "")
    path = wg.out_path(name, args.station, args.year, args.format, args.output)
    fig.savefig(path, dpi=args.dpi)
    plt.close(fig)
    print(f"geschrieben: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
