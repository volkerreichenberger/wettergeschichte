#!/usr/bin/env python3
"""NYT-Klimadiagramm mit plotnine – ggplot2-Grammatik in Python.

Gleiche Daten und Farben wie die matplotlib-Variante, aber deklarativ
zusammengesetzt: jede Ebene des Diagramms ist ein eigenes ``geom_*``.
Praktisch, wenn man das Diagramm später leicht umbauen oder facettieren will.

    python plots/python/nyt_plotnine.py --station 4931 --year 2026
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
from plotnine import (
    aes,
    element_blank,
    element_line,
    element_rect,
    element_text,
    geom_hline,
    geom_linerange,
    geom_point,
    geom_ribbon,
    geom_vline,
    ggplot,
    guide_legend,
    guides,
    labs,
    scale_color_manual,
    scale_fill_manual,
    scale_x_continuous,
    scale_y_continuous,
    theme,
    theme_minimal,
)

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg

warnings.filterwarnings("ignore", category=FutureWarning)


def long_bars(year_df: pd.DataFrame, summary: dict) -> tuple[pd.DataFrame, dict]:
    """Die drei Balkenteile in ein langes Format bringen – so entsteht die Legende von selbst."""
    neutral = f"Tagesspanne {summary['year']}"
    labels = {
        "neutral": neutral,
        "warm": "über der Normalspanne",
        "cold": "unter der Normalspanne",
    }
    parts = [
        year_df.assign(kind=labels["neutral"], lo=year_df["bar_low"], hi=year_df["bar_high"]),
        year_df.assign(kind=labels["warm"], lo=year_df["warm_from"], hi=year_df["warm_to"]),
        year_df.assign(kind=labels["cold"], lo=year_df["cold_from"], hi=year_df["cold_to"]),
    ]
    bars = pd.concat(parts, ignore_index=True).dropna(subset=["lo", "hi"])
    # Reihenfolge festhalten, damit die farbigen Spitzen über dem grauen Balken liegen.
    bars["kind"] = pd.Categorical(bars["kind"], categories=list(labels.values()), ordered=True)
    bars = bars.sort_values("kind")
    colors = {labels["neutral"]: wg.BAR_NEUTRAL, labels["warm"]: wg.WARM, labels["cold"]: wg.COLD}
    return bars, colors


def build(clim: pd.DataFrame, year_df: pd.DataFrame, summary: dict):
    rec_hi = year_df[year_df["is_record_high"]]
    rec_lo = year_df[year_df["is_record_low"]]
    bars, bar_colors = long_bars(year_df, summary)

    band_labels = {
        "record": f"Rekordspanne {summary['record_from']}–{summary['record_to']}",
        "normal": f"Normalspanne {summary['reference_from']}–{summary['reference_to']}",
    }
    bands = pd.concat(
        [
            clim.assign(band=band_labels["record"], lo=clim["record_low"], hi=clim["record_high"]),
            clim.assign(band=band_labels["normal"], lo=clim["normal_low"], hi=clim["normal_high"]),
        ],
        ignore_index=True,
    )
    bands["band"] = pd.Categorical(bands["band"], categories=list(band_labels.values()), ordered=True)
    band_colors = {band_labels["record"]: wg.RECORD_BAND, band_labels["normal"]: wg.NORMAL_BAND}

    centers = [(a + b) / 2 for a, b in zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END])]
    ymin = min(clim["record_low"].min(), year_df["temp_min_c"].min()) - 2
    ymax = max(clim["record_high"].max(), year_df["temp_max_c"].max()) + 3
    breaks = list(range(int(ymin // 5 * 5), int(ymax) + 5, 5))

    p = (
        ggplot()
        + geom_ribbon(bands, aes(x="doy", ymin="lo", ymax="hi", fill="band"))
        + geom_vline(xintercept=wg.MONTH_STARTS[1:], color=wg.GRID, size=0.3)
        + geom_hline(yintercept=0, color=wg.GRID, size=0.4, linetype="dashed")
        + geom_linerange(bars, aes(x="doy", ymin="lo", ymax="hi", color="kind"), size=0.5)
        + geom_point(rec_hi, aes(x="doy", y="temp_max_c"), color=wg.WARM, size=1.6, stroke=0.2)
        + geom_point(rec_lo, aes(x="doy", y="temp_min_c"), color=wg.COLD, size=1.6, stroke=0.2)
        + scale_fill_manual(values=band_colors, name="")
        + scale_color_manual(values=bar_colors, name="")
        + guides(
            fill=guide_legend(order=1, override_aes={"alpha": 1}),
            color=guide_legend(order=2),
        )
        + scale_x_continuous(
            breaks=centers, labels=wg.MONTH_NAMES, limits=(1, wg.MONTH_END), expand=(0, 0)
        )
        + scale_y_continuous(breaks=breaks, labels=[f"{b}°" for b in breaks], limits=(ymin, ymax))
        + labs(
            title=f"{summary['station_name']} · {summary['year']}",
            subtitle=wg.subtitle(summary) + "\n" + wg.stats_line(summary),
            caption=wg.footer(summary) + "  ·  Grafik: plotnine",
            x="",
            y="",
        )
        + theme_minimal(base_size=12)
        + theme(
            figure_size=(16, 9),
            plot_title=element_text(size=24, weight="bold", ha="left", margin={"b": 8}),
            plot_subtitle=element_text(size=12, color=wg.TEXT_MUTED, ha="left", margin={"b": 16},
                                       linespacing=1.6),
            plot_caption=element_text(size=9, color=wg.TEXT_MUTED, ha="left", margin={"t": 12}),
            panel_grid_major_y=element_line(color=wg.GRID, size=0.3),
            panel_grid_major_x=element_blank(),
            panel_grid_minor=element_blank(),
            axis_text=element_text(size=11, color=wg.TEXT_MUTED),
            plot_background=element_rect(fill=wg.BACKGROUND, color="none"),
            panel_background=element_blank(),
            legend_position=(0.13, 0.84),
            legend_direction="vertical",
            legend_key_size=14,
            legend_title=element_blank(),
            legend_text=element_text(size=9.5),
            legend_background=element_rect(fill=wg.BACKGROUND, color=wg.GRID, size=0.4),
            legend_box_margin=6,
        )
    )
    return p


def main(argv=None) -> int:
    args = wg.cli(__doc__).parse_args(argv)
    clim, year_df, _recent, summary = wg.load(args.station, args.year, args.derived)
    path = wg.out_path("nyt_plotnine", args.station, args.year, args.format, args.output)
    # plotnine rendert grundsätzlich mit dem doppelten der angegebenen dpi
    # (16 in × 100 dpi ergeben 3200 px). Halbieren, damit --dpi bei allen
    # Varianten dieselbe Pixelgröße liefert.
    build(clim, year_df, summary).save(
        path, width=16, height=9, units="in", dpi=args.dpi / 2, verbose=False
    )
    print(f"geschrieben: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
