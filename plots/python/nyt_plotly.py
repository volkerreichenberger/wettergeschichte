#!/usr/bin/env python3
"""NYT-Klimadiagramm mit plotly – statischer Export über kaleido.

plotly ist eigentlich eine Bibliothek für interaktive Grafiken; hier wird nur
das Standbild geschrieben. Der Vorteil bleibt: dieselbe Figur ließe sich ohne
Änderung auch als interaktives HTML ausgeben (``--html``).

    python plots/python/nyt_plotly.py --station 4931 --year 2026
    python plots/python/nyt_plotly.py --station 4931 --year 2026 --html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def segments(df, lo_col: str, hi_col: str):
    """Viele kurze Striche als eine einzige Spur – mit None als Trennzeichen.

    Eine Spur je Tag wäre bei 365 Tagen spürbar langsam; plotly zeichnet
    stattdessen einen Linienzug, der zwischen den Balken unterbrochen wird.
    """
    xs: list[float | None] = []
    ys: list[float | None] = []
    for _, row in df.iterrows():
        if row[lo_col] != row[lo_col] or row[hi_col] != row[hi_col]:  # NaN
            continue
        xs.extend([row["doy"], row["doy"], None])
        ys.extend([row[lo_col], row[hi_col], None])
    return xs, ys


def build(clim, year_df, summary) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=clim["doy"], y=clim["record_high"], mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=clim["doy"], y=clim["record_low"], mode="lines", fill="tonexty",
        fillcolor=wg.RECORD_BAND, line=dict(width=0),
        name=f"Rekordspanne {summary['record_from']}–{summary['record_to']}",
    ))
    fig.add_trace(go.Scatter(
        x=clim["doy"], y=clim["normal_high"], mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=clim["doy"], y=clim["normal_low"], mode="lines", fill="tonexty",
        fillcolor=wg.NORMAL_BAND, line=dict(width=0),
        name=f"Normalspanne {summary['reference_from']}–{summary['reference_to']}",
    ))

    for lo, hi, color, label in (
        ("bar_low", "bar_high", wg.BAR_NEUTRAL, f"Tagesspanne {summary['year']}"),
        ("warm_from", "warm_to", wg.WARM, "über der Normalspanne"),
        ("cold_from", "cold_to", wg.COLD, "unter der Normalspanne"),
    ):
        xs, ys = segments(year_df, lo, hi)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", line=dict(color=color, width=1.6),
            name=label, connectgaps=False,
        ))

    for mask, ycol, color, label in (
        ("is_record_high", "temp_max_c", wg.WARM, "neuer Tagesrekord (hoch)"),
        ("is_record_low", "temp_min_c", wg.COLD, "neuer Tagesrekord (tief)"),
    ):
        sub = year_df[year_df[mask]]
        fig.add_trace(go.Scatter(
            x=sub["doy"], y=sub[ycol], mode="markers", name=label,
            marker=dict(color=color, size=6, line=dict(color="white", width=1)),
        ))

    centers = [(a + b) / 2 for a, b in zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END])]
    ymin = min(clim["record_low"].min(), year_df["temp_min_c"].min()) - 2
    ymax = max(clim["record_high"].max(), year_df["temp_max_c"].max()) + 4

    for start in wg.MONTH_STARTS[1:]:
        fig.add_vline(x=start, line=dict(color=wg.GRID, width=0.7))
    fig.add_hline(y=0, line=dict(color=wg.GRID, width=1, dash="dash"))

    fig.update_layout(
        width=1600, height=900,
        template="simple_white",
        paper_bgcolor=wg.BACKGROUND, plot_bgcolor=wg.BACKGROUND,
        font=dict(family="Helvetica Neue, Helvetica, Arial, sans-serif", size=13, color=wg.TEXT),
        title=dict(
            text=(
                f"<b>{summary['station_name']} · {summary['year']}</b><br>"
                f"<span style='font-size:13px;color:{wg.TEXT_MUTED}'>{wg.subtitle(summary)}</span><br>"
                f"<span style='font-size:12px'>{wg.stats_line(summary)}</span>"
            ),
            x=0.03, xanchor="left", y=0.965, yanchor="top",
            font=dict(size=25),
        ),
        margin=dict(l=60, r=30, t=150, b=90),
        legend=dict(
            x=0.012, y=0.985, xanchor="left", yanchor="top", traceorder="normal",
            bgcolor=rgba(wg.BACKGROUND, 0.92), bordercolor=wg.GRID, borderwidth=1,
            font=dict(size=11),
        ),
        xaxis=dict(
            tickmode="array", tickvals=centers, ticktext=wg.MONTH_NAMES,
            range=[1, wg.MONTH_END], showgrid=False, ticks="", showline=False, zeroline=False,
        ),
        yaxis=dict(
            range=[ymin, ymax], dtick=5, ticksuffix="°",
            gridcolor=wg.GRID, gridwidth=0.5, showline=False, zeroline=False, ticks="",
        ),
        annotations=[dict(
            text=wg.footer(summary) + "  ·  Grafik: plotly",
            showarrow=False, xref="paper", yref="paper",
            x=0, y=-0.115, xanchor="left", font=dict(size=10, color=wg.TEXT_MUTED),
        )],
    )
    return fig


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.add_argument("--html", action="store_true", help="zusätzlich eine interaktive HTML-Datei")
    args = ap.parse_args(argv)

    clim, year_df, _recent, summary = wg.load(args.station, args.year, args.derived)
    fig = build(clim, year_df, summary)

    path = wg.out_path("nyt_plotly", args.station, args.year, args.format, args.output)
    # Maße hier noch einmal mitgeben: write_image greift sonst auf seine
    # eigenen Vorgaben (700×500) zurück statt auf das Layout.
    fig.write_image(path, width=1600, height=900, scale=args.dpi / 100)
    print(f"geschrieben: {path}")

    if args.html:
        html = wg.out_path("nyt_plotly", args.station, args.year, "html", args.output)
        fig.write_html(html, include_plotlyjs="cdn")
        print(f"geschrieben: {html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
