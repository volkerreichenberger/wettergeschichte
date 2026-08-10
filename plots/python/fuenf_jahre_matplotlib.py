#!/usr/bin/env python3
"""Fünf Jahre im direkten Vergleich – "ist es dieses Jahr wirklich heißer als letztes?"

Die Frage lässt sich an rohen Tageswerten nicht beantworten, die schwanken zu
stark. Deshalb:

* oben  – 31-Tage-Mittel der Tagesmitteltemperatur, ein Verlauf je Jahr,
          dazu die Normalperiode als graue Referenzlinie
* unten – aufsummierter Niederschlag seit Jahresbeginn
* rechts – Kennzahlen, fair verglichen: alle Jahre nur bis zum Stichtag des
          aktuellen Jahres, sonst vergleicht man ein Rumpfjahr mit vollen Jahren

    python plots/python/fuenf_jahre_matplotlib.py --station 4931 --year 2026
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg


def comparable_stats(recent, cutoff_doy: int):
    """Kennzahlen je Jahr, alle nur bis zum selben Kalendertag."""
    sub = recent[recent["doy"] <= cutoff_doy]
    return (
        sub.groupby("year")
        .agg(
            temp_mean=("temp_mean_c", "mean"),
            precip=("precip_mm", "sum"),
            hot_days=("temp_max_c", lambda s: int((s >= 30).sum())),
        )
        .reset_index()
    )


def month_axis(ax, label: bool) -> None:
    for start in wg.MONTH_STARTS[1:]:
        ax.axvline(start, color=wg.GRID, lw=0.7, zorder=1)
    centers = [(a + b) / 2 for a, b in zip(wg.MONTH_STARTS, wg.MONTH_STARTS[1:] + [wg.MONTH_END])]
    ax.set_xticks(centers)
    ax.set_xticklabels(wg.MONTH_NAMES if label else [""] * 12, fontsize=11)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_xlim(1, wg.MONTH_END)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.set_facecolor(wg.BACKGROUND)


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.add_argument("--years", type=int, default=5, help="Anzahl der verglichenen Jahre")
    args = ap.parse_args(argv)

    plt.rcParams.update(
        {
            **wg.rc_font(),
            "figure.facecolor": wg.BACKGROUND,
            "savefig.facecolor": wg.BACKGROUND,
            "text.color": wg.TEXT,
        }
    )

    clim, year_df, recent, summary = wg.load(args.station, args.year, args.derived)
    years = sorted(recent["year"].unique())[-args.years :]
    recent = recent[recent["year"].isin(years)]
    colors = dict(zip(years, wg.YEAR_COLORS[-len(years) :]))
    cutoff = int(year_df["doy"].max())
    stats = comparable_stats(recent, cutoff).set_index("year")

    fig, (ax_t, ax_p) = plt.subplots(
        2, 1, figsize=(16, 10), height_ratios=[2.1, 1], sharex=True
    )
    fig.subplots_adjust(left=0.055, right=0.80, top=0.84, bottom=0.07, hspace=0.12)

    # ---- oben: geglättete Temperatur ------------------------------------- #
    # Die Normalen kommen aus der Klimatologie und decken das ganze Jahr ab –
    # nicht aus dem laufenden Jahr, das ja nur bis zum Stichtag reicht.
    ax_t.plot(clim["doy"], clim["normal_mean"], color=wg.TEXT_MUTED, lw=1.6,
              ls=(0, (5, 3)), zorder=3)
    ax_t.annotate(
        f"Normal {summary['reference_from']}–{summary['reference_to']}",
        xy=(wg.MONTH_STARTS[9], clim.loc[clim["doy"] == wg.MONTH_STARTS[9], "normal_mean"].iloc[0]),
        xytext=(0, -16), textcoords="offset points", fontsize=9.5,
        color=wg.TEXT_MUTED, ha="center", zorder=6,
    )

    for y in years:
        sub = recent[recent["year"] == y].dropna(subset=["temp_smooth"])
        current = y == years[-1]
        ax_t.plot(sub["doy"], sub["temp_smooth"], color=colors[y],
                  lw=3.2 if current else 1.9, zorder=5 if current else 4,
                  solid_capstyle="round", label=str(y))
        # Nur das laufende Jahr wird am Linienende beschriftet; die
        # abgeschlossenen Jahre laufen alle bis zum rechten Rand und würden
        # sich dort gegenseitig überschreiben – ihre Zuordnung steht in der
        # farbigen Kennzahlentabelle rechts.
        if current:
            last = sub.iloc[-1]
            ax_t.annotate(str(y), xy=(last["doy"], last["temp_smooth"]), xytext=(7, 0),
                          textcoords="offset points", color=colors[y], va="center",
                          fontsize=12, fontweight="bold", zorder=6)

    ax_t.axhline(0, color=wg.GRID, lw=0.8)
    month_axis(ax_t, label=False)
    ax_t.set_ylabel("31-Tage-Mittel der Tagesmitteltemperatur (°C)", fontsize=11,
                    color=wg.TEXT_MUTED)
    ax_t.grid(axis="y", color=wg.GRID, lw=0.5, alpha=0.7)
    ax_t.set_axisbelow(True)

    # ---- unten: kumulierter Niederschlag --------------------------------- #
    for y in years:
        sub = recent[recent["year"] == y]
        current = y == years[-1]
        ax_p.plot(sub["doy"], sub["precip_cum"], color=colors[y],
                  lw=2.8 if current else 1.7, zorder=5 if current else 4)
        if current:
            last = sub.iloc[-1]
            ax_p.annotate(str(y), xy=(last["doy"], last["precip_cum"]), xytext=(7, 0),
                          textcoords="offset points", color=colors[y], va="center",
                          fontsize=11, fontweight="bold")

    ax_p.plot(clim["doy"], clim["normal_precip"].cumsum(), color=wg.TEXT_MUTED, lw=1.6,
              ls=(0, (5, 3)), zorder=3)
    month_axis(ax_p, label=True)
    ax_p.set_ylabel("Niederschlag seit Jahresbeginn (mm)", fontsize=11, color=wg.TEXT_MUTED)
    ax_p.grid(axis="y", color=wg.GRID, lw=0.5, alpha=0.7)
    ax_p.set_axisbelow(True)

    # ---- rechts: faire Kennzahlen ---------------------------------------- #
    x0 = 0.815
    fig.text(x0, 0.80, f"1. Januar bis {wg.de_date(year_df['date'].max())}",
             fontsize=11, fontweight="bold", va="top")
    fig.text(x0, 0.772, "alle Jahre auf denselben Zeitraum gekürzt",
             fontsize=9, color=wg.TEXT_MUTED, va="top")

    head_y = 0.735
    fig.text(x0, head_y, "Jahr", fontsize=9.5, color=wg.TEXT_MUTED, va="top")
    fig.text(x0 + 0.048, head_y, "Ø °C", fontsize=9.5, color=wg.TEXT_MUTED, va="top")
    fig.text(x0 + 0.098, head_y, "Δ Vorjahr", fontsize=9.5, color=wg.TEXT_MUTED, va="top")
    fig.text(x0 + 0.163, head_y, "mm", fontsize=9.5, color=wg.TEXT_MUTED, va="top")

    for i, y in enumerate(reversed(years)):
        row_y = head_y - 0.032 - i * 0.030
        prev = stats["temp_mean"].get(y - 1)
        delta = stats.loc[y, "temp_mean"] - prev if prev is not None and y - 1 in stats.index else None
        bold = "bold" if y == years[-1] else "normal"
        fig.text(x0, row_y, str(y), fontsize=10.5, fontweight=bold, color=colors[y], va="top")
        fig.text(x0 + 0.048, row_y, wg.de_num(stats.loc[y, "temp_mean"]), fontsize=10.5,
                 fontweight=bold, va="top")
        fig.text(
            x0 + 0.098, row_y,
            "–" if delta is None else wg.de_num(delta, sign=True),
            fontsize=10.5, fontweight=bold, va="top",
            color=wg.TEXT if delta is None else (wg.WARM if delta > 0 else wg.COLD),
        )
        fig.text(x0 + 0.163, row_y, f"{stats.loc[y, 'precip']:.0f}", fontsize=10.5,
                 fontweight=bold, va="top")

    note_y = head_y - 0.032 - len(years) * 0.030 - 0.03
    newest, previous = years[-1], years[-2]
    diff = stats.loc[newest, "temp_mean"] - stats.loc[previous, "temp_mean"]
    verdict = (
        f"{newest} liegt bis hierher {wg.de_num(abs(diff))} K\n"
        f"{'über' if diff > 0 else 'unter'} {previous}.\n\n"
        f"Zwischen dem wärmsten und dem\n"
        f"kühlsten der {len(years)} Jahre liegen\n"
        f"{wg.de_num(stats['temp_mean'].max() - stats['temp_mean'].min())} K."
    )
    fig.text(x0, note_y, verdict, fontsize=10, color=wg.TEXT, va="top", linespacing=1.5)

    hot = "\n".join(
        f"{y}:  {int(stats.loc[y, 'hot_days'])} Tage ≥ 30 °C" for y in reversed(years)
    )
    fig.text(x0, note_y - 0.17, "Hitzetage\n" + hot, fontsize=9.5, color=wg.TEXT_MUTED,
             va="top", linespacing=1.6)

    # ---- Titel ------------------------------------------------------------ #
    fig.text(0.055, 0.955, f"{summary['station_name']} · die letzten {len(years)} Jahre",
             fontsize=25, fontweight="bold", va="top")
    fig.text(0.055, 0.912,
             f"Ist {newest} wirklich wärmer als {previous}? "
             f"31-Tage-Mittel der Tagesmitteltemperatur und kumulierter Niederschlag",
             fontsize=12.5, color=wg.TEXT_MUTED, va="top")
    fig.text(0.055, 0.022, wg.footer(summary) + "  ·  Grafik: matplotlib",
             fontsize=9, color=wg.TEXT_MUTED, va="top")

    path = wg.out_path("fuenf_jahre_matplotlib", args.station, args.year, args.format, args.output)
    fig.savefig(path, dpi=args.dpi)
    plt.close(fig)
    print(f"geschrieben: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
