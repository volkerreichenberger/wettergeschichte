#!/usr/bin/env python3
"""Die letzten drei Tage im Stundenverlauf, dahinter dieselben Tage der Vorjahre.

Die aktuelle Kurve steht in Blau (RGB 35, 102, 202), die fünf
Vorjahre dahinter in Grau, das mit dem Alter heller wird (Grauwerte 80, 120,
160, 200, 240).

Grundlage sind Stundenwerte (``fetch_hourly.py``), nicht die Tageswerte: drei
Tage wären sonst drei Punkte. Die Vorjahre werden über Monat, Tag und Stunde
zugeordnet, liegen also kalendarisch exakt untereinander.

    python plots/python/drei_tage_matplotlib.py --station 4931
    python plots/python/drei_tage_matplotlib.py --station 4928 --days 5 --years 3
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).parent))
import wg_common as wg

#: Grauwert des jüngsten Vorjahres; jedes ältere Jahr wird um GREY_STEP heller.
#: 80 – 120 – 160 – 200 – 240 spreizt die fünf Jahre über den ganzen Bereich
#: zwischen fast schwarz und fast weiß.
GREY_START = 80
GREY_STEP = 40

#: Strichstärke der aktuellen Kurve und ihres weißen Sockels darunter. Der
#: Sockel trennt sie von den grauen Vorjahren, auch wo sie sich kreuzen.
CURRENT_LW = 2.8
HALO_LW = CURRENT_LW + 3.0

SIZE_PX = 1080


def grey(index: int) -> str:
    """Grauton für das index-te Vorjahr (0 = das jüngste)."""
    value = min(255, GREY_START + GREY_STEP * index)
    return f"#{value:02x}{value:02x}{value:02x}"


def load_hourly(data_dir: Path, station_id: int) -> pd.DataFrame:
    path = data_dir / "stations" / f"{station_id:05d}" / "hourly_air_temperature.csv"
    if not path.exists():
        raise SystemExit(
            f"{path} fehlt – bitte zuerst 'python fetch_hourly.py' laufen lassen."
        )
    df = pd.read_csv(path, parse_dates=["timestamp"], usecols=["timestamp", "temp_c"])
    return df.dropna(subset=["temp_c"])


def build_window(df: pd.DataFrame, days: int, years: int, stand: str | None = None):
    """Aktuelles Fenster plus die deckungsgleichen Fenster der Vorjahre.

    Zugeordnet wird über (Monat, Tag, Stunde). Fällt ein 29. Februar ins
    Fenster, fehlt er in Nicht-Schaltjahren schlicht – die Kurve hat dort
    eine Lücke, was ehrlicher ist als ein verschobener Wert.

    ``stand`` beschneidet die Reihe auf einen Stichtag; damit lässt sich das
    Bild so bauen, wie es an einem früheren Tag ausgesehen hätte.
    """
    if stand:
        cut = pd.Timestamp(stand) + pd.Timedelta(hours=23)
        df = df[df["timestamp"] <= cut]
        if df.empty:
            raise SystemExit(f"Keine Stundenwerte bis zum Stichtag {stand}.")
    last = df["timestamp"].max()
    start = (last.normalize() - pd.Timedelta(days=days - 1))
    current = df[(df["timestamp"] >= start) & (df["timestamp"] <= last)].copy()
    current = current.sort_values("timestamp").reset_index(drop=True)
    current["x"] = range(len(current))

    key = ["month", "day", "hour"]
    for frame in (df, current):
        frame["month"] = frame["timestamp"].dt.month
        frame["day"] = frame["timestamp"].dt.day
        frame["hour"] = frame["timestamp"].dt.hour
    df["year"] = df["timestamp"].dt.year

    current_year = int(last.year)
    past = {}
    for offset in range(1, years + 1):
        year = current_year - offset
        sub = df[df["year"] == year]
        merged = current[key + ["x"]].merge(sub[key + ["temp_c"]], on=key, how="left")
        past[year] = merged.sort_values("x")

    return current, past, start, last


def day_axis(ax, current: pd.DataFrame) -> None:
    """Tagesgrenzen als Linien, Tagesnamen mittig darunter, 6-Stunden-Raster."""
    midnights = current.index[current["hour"] == 0].tolist()
    for x in midnights[1:]:
        ax.axvline(x - 0.5, color=wg.GRID, lw=0.9, zorder=1)
    for x in current.index[current["hour"].isin([6, 12, 18])]:
        ax.axvline(x, color=wg.GRID, lw=0.4, alpha=0.55, zorder=1)

    bounds = midnights + [len(current)]
    ticks, labels = [], []
    for a, b in zip(bounds, bounds[1:]):
        ts = current.loc[a, "timestamp"]
        ticks.append((a + b - 1) / 2)
        # Zwei Zeilen: Wochentag oben, Datum darunter – so bleibt Platz für
        # eine deutlich größere Schrift.
        labels.append(
            f"{wg.WEEKDAYS[ts.weekday()]}\n{ts.day}. {wg.MONTH_NAMES_LONG[ts.month - 1]}"
        )
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=19, linespacing=1.4)
    ax.tick_params(axis="x", length=0, pad=10)
    ax.set_xlim(-0.5, len(current) - 0.5)


def caption(current, past, station_name: str, args, last) -> str:
    """Alles, was früher im Bild stand: Titel, Einordnung, Kennzahlen, Quelle."""
    warmest = current.loc[current["temp_c"].idxmax()]
    coldest = current.loc[current["temp_c"].idxmin()]
    mean = current["temp_c"].mean()

    def stamp(row) -> str:
        ts = row["timestamp"]
        return f"{ts.day}. {wg.MONTH_NAMES_LONG[ts.month - 1]}, {ts:%H} Uhr"

    first_ts, last_ts = current["timestamp"].iloc[0], current["timestamp"].iloc[-1]
    zeitraum = (
        f"{wg.WEEKDAYS[first_ts.weekday()]}, {first_ts.day}. "
        f"{wg.MONTH_NAMES_LONG[first_ts.month - 1]} bis "
        f"{wg.WEEKDAYS[last_ts.weekday()]}, {last_ts.day}. "
        f"{wg.MONTH_NAMES_LONG[last_ts.month - 1]} {last_ts.year}"
    )

    # Einordnung: wie steht das Mittel der drei Tage zu dem der Vorjahre?
    past_means = {y: f["temp_c"].mean() for y, f in past.items() if f["temp_c"].notna().any()}
    missing = sorted(y for y in past if y not in past_means)
    ranking = ""
    if past_means:
        reference = sum(past_means.values()) / len(past_means)
        diff = mean - reference
        rank = sum(1 for m in past_means.values() if m > mean) + 1
        ranking = (
            f"\n\nIm Mittel {wg.de_num(abs(diff))} K "
            f"{'wärmer' if diff > 0 else 'kühler'} als dieselben drei Tage der "
            f"{len(past_means)} Vergleichsjahre — Platz {rank} von {len(past_means) + 1}."
        )
    if missing:
        # Messlücken offenlegen, statt sie in der Statistik verschwinden zu lassen.
        jahre = " und ".join(str(y) for y in missing)
        ranking += (
            f"\n\nFür {jahre} liegen an diesen Tagen keine Messwerte vor; "
            f"{'diese Jahre fehlen' if len(missing) > 1 else 'dieses Jahr fehlt'} "
            f"deshalb in Grafik und Vergleich."
        )

    return (
        f"Die letzten {args.days} Tage in "
        f"{wg.display_name(args.station, station_name)}\n\n"
        f"Stündliche Lufttemperatur in 2 m Höhe. Die kräftige blaue Linie ist "
        f"{last.year}, dahinter liegen dieselben Kalendertage der {args.years} "
        f"Vorjahre in Grau – je weiter zurück, desto heller."
        f"\n\n{zeitraum}"
        f"\n· Höchstwert {wg.de_num(warmest['temp_c'])} °C am {stamp(warmest)}"
        f"\n· Tiefstwert {wg.de_num(coldest['temp_c'])} °C am {stamp(coldest)}"
        f"\n· Mittel {wg.de_num(mean)} °C über {len(current)} Stunden"
        f"{ranking}"
        f"\n\n{wg.quelle(args.station, station_name, f'{last:%d.%m.%Y}, {last:%H} Uhr')}"
        f"\n\n{wg.HASHTAGS}"
    )


def main(argv=None) -> int:
    ap = wg.cli(__doc__)
    ap.set_defaults(format="jpg")  # Instagram nimmt nur JPEG entgegen
    ap.add_argument("--days", type=int, default=3, help="Anzahl der gezeigten Tage")
    ap.add_argument("--years", type=int, default=5, help="Anzahl der Vorjahre dahinter")
    ap.add_argument("--data-dir", type=Path, default=wg.ROOT / "data")
    ap.add_argument("--stand", metavar="JJJJ-MM-TT",
                    help="Bild so bauen, wie es an diesem Tag ausgesehen hätte")
    ap.add_argument("--posts", type=Path, default=wg.ROOT / "posts",
                    help="Verzeichnis, unter dem je Beitrag ein Ordner angelegt wird")
    ap.add_argument("--jpeg-quality", type=int, default=92)
    args = ap.parse_args(argv)

    plt.rcParams.update(
        {
            **wg.rc_font(),
            "figure.facecolor": wg.BACKGROUND,
            "savefig.facecolor": wg.BACKGROUND,
            "text.color": wg.TEXT,
        }
    )

    df = load_hourly(args.data_dir, args.station)
    current, past, start, last = build_window(df, args.days, args.years, args.stand)
    station_name = wg.station_name(args.station, args.data_dir)

    # Layout in Zoll bei 200 dpi festlegen, gespeichert wird mit --dpi:
    # bei 200 dpi kommen exakt die 1080 px heraus, die Instagram nutzt.
    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    # Kein Titel, keine Fußzeile: alles Textliche steht im Begleittext, damit
    # das Bild im Feed nur die Kurven zeigt.
    # Oben etwas Luft lassen: die Einheit steht über der Skala und würde am
    # Bildrand sonst angeschnitten.
    # Unten Platz für die zweizeiligen Tagesnamen, oben für die Einheit.
    ax = fig.add_axes((0.105, 0.205, 0.875, 0.735))

    # Vorjahre von alt nach jung, damit die dunkleren Kurven oben liegen.
    for offset in range(args.years, 0, -1):
        year = int(last.year) - offset
        sub = past[year]
        ax.plot(sub["x"], sub["temp_c"], color=grey(offset - 1), lw=1.5,
                solid_capstyle="round", zorder=2 + (args.years - offset))

    # Erst ein weißer Sockel, dann die blaue Linie darüber: so bleibt sie auch
    # dort ablesbar, wo sie durch das Bündel der Vorjahre läuft.
    ax.plot(current["x"], current["temp_c"], color=wg.BACKGROUND, lw=HALO_LW,
            solid_capstyle="round", zorder=9)
    ax.plot(current["x"], current["temp_c"], color=wg.CURRENT_BLUE, lw=CURRENT_LW,
            solid_capstyle="round", zorder=10)

    day_axis(ax, current)
    ax.grid(axis="y", color=wg.GRID, lw=0.5, alpha=0.8)
    ax.set_axisbelow(True)
    # Die Achse trägt nur noch die Einheit, waagerecht über der Skala.
    ax.set_ylabel("°C", rotation=0, loc="top", labelpad=-14,
                  fontsize=11, color=wg.TEXT_MUTED)
    ax.tick_params(axis="y", labelsize=11, colors=wg.TEXT_MUTED, length=0)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)

    # Jahre ohne Messwerte gar nicht erst in die Legende aufnehmen – sonst
    # sucht man im Bild nach einer Linie, die es nicht gibt.
    handles = [Line2D([], [], color=wg.CURRENT_BLUE, lw=CURRENT_LW, label=str(last.year))]
    handles += [
        Line2D([], [], color=grey(i), lw=2, label=str(int(last.year) - 1 - i))
        for i in range(args.years)
        if past[int(last.year) - 1 - i]["temp_c"].notna().any()
    ]
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.005, 0.995),
                    frameon=True, framealpha=0.93, edgecolor=wg.GRID,
                    facecolor=wg.BACKGROUND, fontsize=9, handlelength=1.6,
                    borderpad=0.7, labelspacing=0.42, ncols=2, columnspacing=1.2)
    leg.get_frame().set_linewidth(0.5)
    leg.set_zorder(11)

    # Ein Ordner je Beitrag: Bild und Begleittext liegen beieinander, damit ein
    # späteres Upload-Skript nur noch auf das Verzeichnis zeigen muss.
    slug = f"drei_tage_{args.station:05d}_{last:%Y-%m-%d}"
    post_dir: Path = args.posts / slug
    post_dir.mkdir(parents=True, exist_ok=True)

    image = post_dir / f"bild.{args.format}"
    save_kwargs = {"pil_kwargs": {"quality": args.jpeg_quality}} if args.format == "jpg" else {}
    fig.savefig(image, dpi=args.dpi, **save_kwargs)
    plt.close(fig)

    text = post_dir / "text.txt"
    text.write_text(caption(current, past, station_name, args, last), encoding="utf-8")

    print(f"geschrieben: {image}\ngeschrieben: {text}")
    # Letzte Zeile maschinenlesbar, damit post_daily.sh den Ordner findet,
    # ohne den Namen selbst zusammenbauen zu müssen.
    print(f"POST_DIR={post_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
