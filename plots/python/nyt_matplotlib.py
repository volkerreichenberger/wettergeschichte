#!/usr/bin/env python3
"""NYT-Klimadiagramm mit matplotlib – die Referenzumsetzung.

Aufbau wie im Original der New York Times:

* hellgraue Fläche  – Spanne zwischen Rekordtief und Rekordhoch des Kalendertags
* beigefarbene Fläche – Normalspanne (mittleres Tagesmin./-max. der Normalperiode)
* dunkle Balken – Tagesspanne des dargestellten Jahres
* rote/blaue Spitzen – der Teil des Balkens, der die Normalspanne verlässt
* Punkte – an diesem Kalendertag wurde ein neuer Rekord aufgestellt

    python plots/python/nyt_matplotlib.py --station 4931 --year 2026
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "axes.edgecolor": wg.GRID,
            "axes.linewidth": 0.8,
            "text.color": wg.TEXT,
            "axes.labelcolor": wg.TEXT,
            "xtick.color": wg.TEXT_MUTED,
            "ytick.color": wg.TEXT_MUTED,
            "figure.facecolor": wg.BACKGROUND,
            "savefig.facecolor": wg.BACKGROUND,
        }
    )


def month_axis(ax, ymin: float, ymax: float, window=(1, wg.MONTH_END), long_names=None) -> None:
    """Monatstrennlinien und -namen, auch wenn nur ein Ausschnitt gezeigt wird."""
    lo, hi = window
    for start in wg.MONTH_STARTS[1:]:
        if lo < start < hi:
            ax.axvline(start, color=wg.GRID, lw=0.7, zorder=1)

    span = hi - lo
    # Bei kurzen Ausschnitten ist Platz für die ausgeschriebenen Monatsnamen.
    names = wg.MONTH_NAMES_LONG if (long_names or (long_names is None and span <= 130)) else wg.MONTH_NAMES
    bounds = list(zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END]))

    ticks, labels = [], []
    for name, (a, b) in zip(names, bounds):
        a, b = max(a, lo), min(b, hi)
        # Ein angeschnittener Monat bekommt nur dann ein Label, wenn er breit
        # genug ist – sonst klebt es an der Trennlinie.
        if b - a < max(8, span * 0.06):
            continue
        ticks.append((a + b) / 2)
        labels.append(name)

    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=11)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(ymin, ymax)


#: Anteil eines Tages, den der Balken ausfüllt. Bewusst deutlich unter 1: die
#: Balken dürfen sich auch im kurzen Ausschnitt nicht berühren, sonst wird aus
#: den Tageswerten eine Fläche.
BAR_FILL = 0.46


def bar_width(ax, span: int) -> float:
    """Balkenstärke in Punkt, abgeleitet aus der echten Breite der Achse.

    Eine feste Stärke geht schief, sobald sich Fensterbreite (Jahr vs. Quartal)
    oder Bildformat (16:9 vs. Instagram-Hochformat) ändern: Im Quartal auf
    1080 px sind Balken sonst so breit, dass sie zu einer Fläche verschmelzen.
    """
    axes_pt = ax.get_position().width * ax.figure.get_figwidth() * 72
    return float(min(9.0, max(0.8, axes_pt / max(span, 1) * BAR_FILL)))


def window_from_months(year_df, months: int | None) -> tuple[int, int]:
    """Fenster der letzten n Monate bis zum letzten Messtag, in Tagen im Jahr."""
    if not months:
        return 1, wg.MONTH_END
    last = year_df["date"].max()
    start = last - pd.DateOffset(months=months)
    # Reicht das Fenster ins Vorjahr, wird am Jahresanfang abgeschnitten –
    # die x-Achse dieses Diagramms kennt nur ein Kalenderjahr.
    start_doy = 1 if start.year < last.year else int(clim_doy(start))
    return max(1, start_doy), min(wg.MONTH_END, int(year_df["doy"].max()) + 2)


def clim_doy(ts) -> int:
    """Tag im Jahr im 365-Tage-Schema (29.02. fällt mit dem 28.02. zusammen)."""
    doy = ts.dayofyear
    return doy - 1 if (ts.is_leap_year and doy > 59) else doy


def draw(clim, year_df, summary, ax, window=(1, wg.MONTH_END), ylim=None) -> None:
    """``ylim`` erzwingt eine feste Temperaturskala.

    Für eine Bilderserie unverzichtbar: blättert man durch mehrere Ausschnitte
    mit je eigener Skala, sieht ein kühles Quartal aus wie ein heißes.
    """
    lo, hi = window
    clim = clim[(clim["doy"] >= lo) & (clim["doy"] <= hi)]
    year_df = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)]
    lw = bar_width(ax, hi - lo)
    doy = clim["doy"]

    ax.fill_between(
        doy, clim["record_low"], clim["record_high"],
        color=wg.RECORD_BAND, lw=0, zorder=2,
        label="Rekordspanne seit %d" % summary["record_from"],
    )
    ax.fill_between(
        doy, clim["normal_low"], clim["normal_high"],
        color=wg.NORMAL_BAND, lw=0, zorder=3, alpha=0.95,
        label="Normalspanne %d–%d" % (summary["reference_from"], summary["reference_to"]),
    )

    # Tagesbalken: erst die volle Spanne dunkel, dann die Ausreißer farbig darüber.
    ax.vlines(year_df["doy"], year_df["bar_low"], year_df["bar_high"],
              color=wg.BAR_NEUTRAL, lw=lw, zorder=4)
    warm = year_df.dropna(subset=["warm_from", "warm_to"])
    cold = year_df.dropna(subset=["cold_from", "cold_to"])
    ax.vlines(warm["doy"], warm["warm_from"], warm["warm_to"], color=wg.WARM, lw=lw, zorder=5)
    ax.vlines(cold["doy"], cold["cold_from"], cold["cold_to"], color=wg.COLD, lw=lw, zorder=5)

    rec_hi = year_df[year_df["is_record_high"]]
    rec_lo = year_df[year_df["is_record_low"]]
    marker = 22 + 4 * lw
    ax.scatter(rec_hi["doy"], rec_hi["temp_max_c"], s=marker, color=wg.WARM,
               edgecolor="white", linewidth=0.6, zorder=6)
    ax.scatter(rec_lo["doy"], rec_lo["temp_min_c"], s=marker, color=wg.COLD,
               edgecolor="white", linewidth=0.6, zorder=6)

    ax.axhline(0, color=wg.GRID, lw=0.8, ls=(0, (4, 4)), zorder=2)

    if ylim is not None:
        ymin, ymax = ylim
    else:
        ymin = min(clim["record_low"].min(), year_df["temp_min_c"].min()) - 2
        ymax = max(clim["record_high"].max(), year_df["temp_max_c"].max()) + 6
    month_axis(ax, ymin, ymax, window)

    ticks = range(int(ymin // 5 * 5), int(ymax) + 5, 5)
    ax.set_yticks(list(ticks))
    ax.set_yticklabels([f"{t}°" for t in ticks], fontsize=11)
    for t in ticks:
        ax.axhline(t, color=wg.GRID, lw=0.5, alpha=0.6, zorder=1)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.set_facecolor(wg.BACKGROUND)


def annotate_extremes(ax, year_df, window=(1, wg.MONTH_END)) -> None:
    """Höchst- und Tiefstwert beschriften – wie im Original, aber nur im Ausschnitt."""
    lo_doy, hi_doy = window
    sub = year_df[(year_df["doy"] >= lo_doy) & (year_df["doy"] <= hi_doy)]
    if sub["temp_max_c"].isna().all():
        return
    span = hi_doy - lo_doy
    dx = max(6, round(span * 0.075))  # Versatz proportional zur Fensterbreite

    hi = sub.loc[sub["temp_max_c"].idxmax()]
    lo = sub.loc[sub["temp_min_c"].idxmin()]
    # Beschriftung nach innen kippen, damit sie am Rand nicht hinausläuft.
    hi_x = hi["doy"] - dx if hi["doy"] - lo_doy > span / 2 else hi["doy"] + dx
    lo_x = lo["doy"] + dx if lo["doy"] - lo_doy < span / 2 else lo["doy"] - dx
    ax.annotate(
        f"wärmster Tag\n{wg.de_date(hi['date'])}: {wg.de_num(hi['temp_max_c'])} °C",
        xy=(hi["doy"], hi["temp_max_c"]), xytext=(hi_x, hi["temp_max_c"] + 6),
        fontsize=9.5, color=wg.WARM, ha="center", zorder=7,
        arrowprops=dict(arrowstyle="-", color=wg.WARM, lw=0.8, shrinkA=0, shrinkB=3),
    )
    ax.annotate(
        f"kältester Tag\n{wg.de_date(lo['date'])}: {wg.de_num(lo['temp_min_c'])} °C",
        xy=(lo["doy"], lo["temp_min_c"]), xytext=(lo_x, lo["temp_min_c"] - 5),
        fontsize=9.5, color=wg.COLD, ha="center", zorder=7,
        arrowprops=dict(arrowstyle="-", color=wg.COLD, lw=0.8, shrinkA=0, shrinkB=3),
    )


def window_stats_line(year_df, clim, window) -> str:
    """Kennzahlen nur für den gezeigten Ausschnitt – die Jahreszahlen passen sonst nicht."""
    lo, hi = window
    sub = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)].dropna(subset=["temp_mean_c"])
    normal = clim.loc[clim["doy"].isin(sub["doy"]), "normal_mean"].mean()
    mean = sub["temp_mean_c"].mean()
    return (
        f"{wg.de_date(sub['date'].min())} bis {wg.de_date(sub['date'].max())}:   "
        f"Mittel {wg.de_num(mean)} °C ({wg.de_num(mean - normal, sign=True)} K zur Normalperiode)"
        f"   ·   Höchstwert {wg.de_num(sub['temp_max_c'].max())} °C"
        f"   ·   Tiefstwert {wg.de_num(sub['temp_min_c'].min())} °C"
        f"   ·   {int((sub['temp_max_c'] >= 30).sum())} Tage ≥ 30 °C"
        f"   ·   {int(sub['precip_mm'].sum())} mm Niederschlag"
    )


def legend(ax, summary) -> None:
    handles = [
        Patch(facecolor=wg.RECORD_BAND, label=f"Rekordspanne {summary['record_from']}–{summary['record_to']}"),
        Patch(facecolor=wg.NORMAL_BAND, label=f"Normalspanne {summary['reference_from']}–{summary['reference_to']}"),
        Line2D([], [], color=wg.BAR_NEUTRAL, lw=3, label=f"Tagesspanne {summary['year']}"),
        Line2D([], [], color=wg.WARM, lw=3, label="über der Normalspanne"),
        Line2D([], [], color=wg.COLD, lw=3, label="unter der Normalspanne"),
        Line2D([], [], marker="o", color="none", markerfacecolor=wg.WARM,
               markeredgecolor="white", markersize=7, label="neuer Tagesrekord"),
    ]
    leg = ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.995),
        frameon=True, framealpha=0.92, edgecolor=wg.GRID, facecolor=wg.BACKGROUND,
        fontsize=9, handlelength=1.6, borderpad=0.8, labelspacing=0.55,
    )
    leg.get_frame().set_linewidth(0.6)
    leg.set_zorder(8)


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.add_argument("--months", type=int, default=None,
                    help="nur die letzten n Monate zeigen statt des ganzen Jahres")
    args = ap.parse_args(argv)
    style()
    clim, year_df, _recent, summary = wg.load(args.station, args.year, args.derived)
    window = window_from_months(year_df, args.months)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.05, right=0.98, top=0.84, bottom=0.08)

    draw(clim, year_df, summary, ax, window)
    annotate_extremes(ax, year_df, window)
    legend(ax, summary)

    if args.months:
        title = f"{summary['station_name']} · die letzten {args.months} Monate"
        subtitle = (
            f"Tägliche Höchst- und Tiefsttemperaturen gegen die Normalperiode "
            f"{summary['reference_from']}–{summary['reference_to']} und die "
            f"Min/Max-Werte seit {summary['record_from']}"
        )
        stats = window_stats_line(year_df, clim, window)
    else:
        title = f"{summary['station_name']} · {summary['year']}"
        subtitle = wg.subtitle(summary)
        stats = wg.stats_line(summary)

    fig.text(0.05, 0.955, title, fontsize=25, fontweight="bold", ha="left", va="top")
    fig.text(0.05, 0.912, subtitle, fontsize=12.5, color=wg.TEXT_MUTED, ha="left", va="top")
    fig.text(0.05, 0.878, stats, fontsize=11, color=wg.TEXT, ha="left", va="top")
    fig.text(0.05, 0.022, wg.footer(summary) + "  ·  Grafik: matplotlib",
             fontsize=9, color=wg.TEXT_MUTED, ha="left", va="top")

    name = "nyt_matplotlib" if not args.months else f"nyt_{args.months}monate_matplotlib"
    path = wg.out_path(name, args.station, args.year, args.format, args.output)
    fig.savefig(path, dpi=args.dpi)
    plt.close(fig)
    print(f"geschrieben: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
