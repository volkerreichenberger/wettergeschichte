#!/usr/bin/env python3
"""Instagram-taugliche Fassung des Diagramms: 1080 × 1350 (4:5) statt 16:9.

Das breite Diagramm funktioniert im Feed nicht – Instagram zeigt Querformate
klein an. Diese Variante stapelt Titel, Diagramm und Kennzahlen untereinander
und schreibt zusätzlich einen fertigen Bildtext (Caption) als .txt daneben.

    python plots/python/instagram_card.py --station 4931 --year 2026
    python plots/python/instagram_card.py --station 4931 --year 2026 --chart fuenf_jahre
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg
from nyt_matplotlib import draw as draw_nyt
from nyt_matplotlib import month_axis, style, window_from_months, window_stats_line

#: Instagram rechnet Feed-Bilder auf maximal 1080 px Breite herunter.
SIZES = {"portrait": (1080, 1350), "square": (1080, 1080)}

MONTH_INITIALS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def compact_month_labels(ax, window=(1, wg.MONTH_END)) -> None:
    """Im schmalen Format passen über zwölf Monate nur die Anfangsbuchstaben.

    Bei einem kurzen Ausschnitt bleibt es bei den Namen, die ``month_axis``
    schon gesetzt hat – da ist Platz genug.
    """
    if window[1] - window[0] > 130:
        ax.set_xticklabels(MONTH_INITIALS, fontsize=11)


def draw_five_years(ax, clim, recent, year_df, summary, years: int = 5) -> None:
    yrs = sorted(recent["year"].unique())[-years:]
    colors = dict(zip(yrs, wg.YEAR_COLORS[-len(yrs):]))

    ax.plot(clim["doy"], clim["normal_mean"], color=wg.TEXT_MUTED, lw=1.2, ls=(0, (5, 3)))
    for y in yrs:
        sub = recent[(recent["year"] == y)].dropna(subset=["temp_smooth"])
        current = y == yrs[-1]
        ax.plot(sub["doy"], sub["temp_smooth"], color=colors[y],
                lw=3.0 if current else 1.6, solid_capstyle="round")
    last = recent[recent["year"] == yrs[-1]].dropna(subset=["temp_smooth"]).iloc[-1]
    ax.annotate(str(yrs[-1]), xy=(last["doy"], last["temp_smooth"]), xytext=(5, 0),
                textcoords="offset points", color=colors[yrs[-1]], va="center",
                fontsize=11, fontweight="bold")

    for start in wg.MONTH_STARTS[1:]:
        ax.axvline(start, color=wg.GRID, lw=0.6, zorder=1)
    centers = [(a + b) / 2 for a, b in zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END])]
    ax.set_xticks(centers)
    ax.set_xlim(1, wg.MONTH_END)
    ax.grid(axis="y", color=wg.GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0, labelsize=11, colors=wg.TEXT_MUTED)

    legend = [Line2D([], [], color=colors[y], lw=3 if y == yrs[-1] else 1.8, label=str(y))
              for y in reversed(yrs)]
    legend.append(Line2D([], [], color=wg.TEXT_MUTED, lw=1.2, ls=(0, (5, 3)),
                         label=f"Normal {summary['reference_from']}–{summary['reference_to']}"))
    ax.legend(handles=legend, loc="upper left", fontsize=8.5, frameon=True,
              framealpha=0.92, edgecolor=wg.GRID, facecolor=wg.BACKGROUND,
              handlelength=1.4, borderpad=0.6, labelspacing=0.4).set_zorder(8)


def compact_legend(ax, summary) -> None:
    handles = [
        Patch(facecolor=wg.RECORD_BAND, label="Min/Max"),
        Patch(facecolor=wg.NORMAL_BAND, label="Normal"),
        Line2D([], [], color=wg.WARM, lw=3, label="zu warm"),
        Line2D([], [], color=wg.COLD, lw=3, label="zu kalt"),
    ]
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.995),
                    frameon=True, framealpha=0.92, edgecolor=wg.GRID,
                    facecolor=wg.BACKGROUND, fontsize=9, handlelength=1.3,
                    borderpad=0.6, labelspacing=0.4, ncols=2, columnspacing=1.0)
    leg.get_frame().set_linewidth(0.5)
    leg.set_zorder(8)


def window_slice(year_df, clim, window):
    """Tageswerte und passende Normalen für den gezeigten Ausschnitt."""
    lo, hi = window
    sub = year_df[(year_df["doy"] >= lo) & (year_df["doy"] <= hi)].dropna(subset=["temp_mean_c"])
    normal = clim.loc[clim["doy"].isin(sub["doy"]), "normal_mean"].mean()
    return sub, normal


def window_tiles(year_df, clim, window) -> list[tuple[str, str, str]]:
    """Kennzahlenkacheln, die sich auf den Ausschnitt beziehen statt auf das Jahr."""
    sub, normal = window_slice(year_df, clim, window)
    mean = sub["temp_mean_c"].mean()
    hottest = sub.loc[sub["temp_max_c"].idxmax()]
    return [
        ("Mittel", f"{wg.de_num(mean)} °C", f"{wg.de_num(mean - normal, sign=True)} K zur Norm"),
        ("Höchstwert", f"{wg.de_num(hottest['temp_max_c'])} °C", wg.de_date(hottest["date"])),
        ("Tage ≥ 30 °C", str(int((sub["temp_max_c"] >= 30).sum())), "im Zeitraum"),
        ("Niederschlag", f"{int(sub['precip_mm'].sum())} mm", "im Zeitraum"),
    ]


def caption(summary: dict, chart: str, year_df=None, clim=None, window=None) -> str:
    """Fertiger Bildtext – Zahlen kommen aus derselben Quelle wie die Grafik."""
    if window is not None:
        sub, normal = window_slice(year_df, clim, window)
        mean = sub["temp_mean_c"].mean()
        hottest = sub.loc[sub["temp_max_c"].idxmax()]
        coldest = sub.loc[sub["temp_min_c"].idxmin()]
        warmer = "wärmer" if mean > normal else "kühler"
        return (
            f"{summary['station_name']}, {wg.de_date(sub['date'].min())} bis "
            f"{wg.de_date(sub['date'].max())}: {wg.de_num(mean)} °C im Mittel — "
            f"{wg.de_num(abs(mean - normal))} K {warmer} als in der Normalperiode "
            f"{summary['reference_from']}–{summary['reference_to']}."
            f"\n\n· Höchstwert {wg.de_num(hottest['temp_max_c'])} °C am "
            f"{wg.de_date(hottest['date'])}"
            f"\n· Tiefstwert {wg.de_num(coldest['temp_min_c'])} °C am "
            f"{wg.de_date(coldest['date'])}"
            f"\n· {int((sub['temp_max_c'] >= 30).sum())} Tage mit 30 °C oder mehr"
            f"\n· {int(sub['is_record_high'].sum())} neue Tageshöchstrekorde seit "
            f"{summary['record_from']}"
            f"\n· {int(sub['precip_mm'].sum())} mm Niederschlag"
            f"\n\nDie hellen Flächen zeigen, was an diesem Kalendertag seit "
            f"{summary['record_from']} überhaupt schon gemessen wurde (Min/Max), "
            f"die dunkle Fläche den Normalbereich."
            f"\n\nDaten: Deutscher Wetterdienst, Station {summary['station_id']}, "
            f"Stand {summary['last_date']}."
            "\n\n#wetter #klima #stuttgart #dwd #klimawandel #datenvisualisierung "
            "#wetterdaten #opendata #climatedata"
        )

    warmer = "wärmer" if summary["anomaly"] > 0 else "kühler"
    head = (
        f"{summary['station_name']}, {summary['year']}: bisher "
        f"{wg.de_num(summary['temp_mean'])} °C im Mittel — "
        f"{wg.de_num(abs(summary['anomaly']))} K {warmer} als in der "
        f"Normalperiode {summary['reference_from']}–{summary['reference_to']}."
    )
    body = (
        f"\n\n· Höchstwert {wg.de_num(summary['temp_max'])} °C am "
        f"{wg.de_date(date.fromisoformat(summary['temp_max_date']))}"
        f"\n· Tiefstwert {wg.de_num(summary['temp_min'])} °C am "
        f"{wg.de_date(date.fromisoformat(summary['temp_min_date']))}"
        f"\n· {summary['days_above_30']} Tage mit 30 °C oder mehr"
        f"\n· {summary['frost_days']} Frosttage"
        f"\n· {summary['record_highs']} neue Tageshöchstrekorde seit {summary['record_from']}"
        f"\n· {wg.de_num(summary['precip_sum'], 0)} mm Niederschlag "
        f"(normal wären {wg.de_num(summary['precip_normal_sum'], 0)} mm)"
    )
    tail = (
        f"\n\nDaten: Deutscher Wetterdienst, Station {summary['station_id']}, "
        f"Stand {summary['last_date']}."
        "\n\n#wetter #klima #stuttgart #dwd #klimawandel #datenvisualisierung "
        "#wetterdaten #opendata #climatedata"
    )
    if chart == "fuenf_jahre":
        head = (
            f"Ist {summary['year']} in {summary['station_name']} wirklich heißer "
            f"als die Jahre davor? Fünf Jahre im direkten Vergleich, "
            f"jeweils als 31-Tage-Mittel."
        ) + " " + head
    return head + body + tail


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.add_argument("--chart", choices=["nyt", "fuenf_jahre"], default="nyt")
    ap.add_argument("--layout", choices=list(SIZES), default="portrait")
    ap.add_argument("--months", type=int, default=None,
                    help="beim NYT-Diagramm nur die letzten n Monate zeigen")
    ap.add_argument("--jpeg-quality", type=int, default=92,
                    help="Instagram nimmt nur JPEG entgegen")
    args = ap.parse_args(argv)

    style()
    clim, year_df, recent, summary = wg.load(args.station, args.year, args.derived)

    width_px, height_px = SIZES[args.layout]
    dpi = 200
    fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    # Feste Aufteilung: oben Titel, in der Mitte das Diagramm, unten die
    # Kennzahlen. Im Quadrat bleibt für das Diagramm entsprechend weniger Platz.
    ax_bottom = 0.215 if args.layout == "portrait" else 0.255
    ax_top = 0.865 if args.layout == "portrait" else 0.845
    ax = fig.add_axes((0.105, ax_bottom, 0.855, ax_top - ax_bottom))

    window = window_from_months(year_df, args.months)

    if args.chart == "nyt":
        draw_nyt(clim, year_df, summary, ax, window)
        compact_month_labels(ax, window)
        compact_legend(ax, summary)
        if args.months:
            headline = f"Die letzten {args.months} Monate"
            kicker = (
                f"{summary['station_name']} · Tagesspannen gegen die\n"
                f"Normalperiode {summary['reference_from']}–{summary['reference_to']} "
                f"und die Min/Max-Werte seit {summary['record_from']}"
            )
        else:
            headline = f"{summary['year']} in {summary['station_name']}"
            kicker = (
                f"Tagesspannen gegen Normalperiode {summary['reference_from']}–"
                f"{summary['reference_to']} und Min/Max-Werte seit {summary['record_from']}"
            )
    else:
        draw_five_years(ax, clim, recent, year_df, summary)
        compact_month_labels(ax)
        ax.set_ylabel("31-Tage-Mittel (°C)", fontsize=10, color=wg.TEXT_MUTED)
        headline = f"Fünf Jahre {summary['station_name']}"
        kicker = f"Ist {summary['year']} wirklich wärmer als die Jahre davor?"

    fig.text(0.06, 0.972, headline, fontsize=20, fontweight="bold", va="top")
    fig.text(0.06, 0.928, kicker, fontsize=10.5, color=wg.TEXT_MUTED, va="top",
             wrap=True, linespacing=1.4)

    # Kennzahlenblock unten – im Feed liest man die Zahlen, nicht die Achsen.
    tiles = window_tiles(year_df, clim, window) if args.months else [
        ("Jahresmittel", f"{wg.de_num(summary['temp_mean'])} °C",
         f"{wg.de_num(summary['anomaly'], sign=True)} K"),
        ("Höchstwert", f"{wg.de_num(summary['temp_max'])} °C",
         wg.de_date(date.fromisoformat(summary["temp_max_date"]))),
        ("Tage ≥ 30 °C", str(summary["days_above_30"]), "seit 1. Januar"),
        ("Tagesrekorde", str(summary["record_highs"]), f"seit {summary['record_from']}"),
    ]
    for i, (label, value, note) in enumerate(tiles):
        x = 0.06 + i * 0.235
        fig.text(x, 0.148, label, fontsize=9, color=wg.TEXT_MUTED, va="top")
        fig.text(x, 0.124, value, fontsize=16, fontweight="bold", va="top")
        fig.text(x, 0.079, note, fontsize=8.5, color=wg.TEXT_MUTED, va="top")

    # Kurzfassung der Fußzeile – die lange Variante passt nicht in 1080 px.
    fig.text(0.06, 0.042, f"Daten: Deutscher Wetterdienst (opendata.dwd.de), "
                          f"Station {summary['station_id']}",
             fontsize=8, color=wg.TEXT_MUTED, va="top")
    fig.text(0.06, 0.020, f"Stand {summary['last_date']}",
             fontsize=8, color=wg.TEXT_MUTED, va="top")

    name = f"instagram_{args.chart}"
    if args.months:
        name = f"instagram_{args.months}monate"
    path = wg.out_path(name, args.station, args.year, "jpg", args.output)
    fig.savefig(path, dpi=dpi, pil_kwargs={"quality": args.jpeg_quality})
    plt.close(fig)

    txt = path.with_suffix(".txt")
    txt.write_text(caption(summary, args.chart, year_df, clim, window if args.months else None),
                   encoding="utf-8")
    print(f"geschrieben: {path}\ngeschrieben: {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
