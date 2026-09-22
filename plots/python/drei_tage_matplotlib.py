#!/usr/bin/env python3
"""Die letzten drei Tage im Stundenverlauf, dahinter dieselben Tage der Vorjahre.

Die aktuelle Kurve steht in Blau (RGB 35, 102, 202), die fünf
Vorjahre dahinter in Grau, das mit dem Alter heller wird (Grauwerte 80, 120,
160, 200, 240).

Unter der Kurve liegt der Himmel: ein Streifen, der den Bedeckungsgrad in
Achteln zeigt, zwischen den Stundenwerten glatt interpoliert – dieselbe Skala
wie im Bewölkungskalender, Blau heißt klar, Grau heißt bedeckt. Nachts dunkelt der Streifen ab: eine klare
Nacht ist tiefes Nachtblau, eine bedeckte dunkelgrau; die Dämmerung mischt
beide Skalen über die Sonnenhöhe. Sonnenauf- und -untergang stehen als Marken
unter dem Streifen. So trägt der Streifen die Nacht mit, ohne dass ein Band
hinter die Vorjahreskurven müsste.

Grundlage sind Stundenwerte (``fetch_hourly.py``), nicht die Tageswerte: drei
Tage wären sonst drei Punkte. Die Vorjahre werden über Monat, Tag und Stunde
zugeordnet, liegen also kalendarisch exakt untereinander. Alle Zeiten sind
UTC, wie der DWD sie liefert – auch die Tagesgrenzen und die Sonnenmarken.

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
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
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

#: Sonnenhöhe, unter der der Himmel ganz Nacht ist (bürgerliche Dämmerung),
#: und ab der er ganz Tag ist. Dazwischen mischen sich beide Skalen linear.
NACHT_BIS = -6.0
TAG_AB = 6.0

#: Stunden mit höchstens so vielen Achteln zählen als klar, mit mindestens
#: so vielen als bedeckt. Bei Stunden liegt „bedeckt" höher als beim
#: Kalender (6 bei Tagesmitteln): acht Achtel sind die häufigste Einzelstunde.
KLAR_BIS = 2
BEDECKT_AB = 7

#: Raster des Himmelsstreifens in Minuten. Zwischen den Stundenwerten wird
#: linear interpoliert; sechs Minuten sind bei 1080 px gut ein Pixel je Schritt.
FEIN = 6


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


def load_cloud(data_dir: Path, station_id: int) -> pd.DataFrame:
    """Stündlicher Bedeckungsgrad; NaN steht für „nicht bestimmbar" (Nebel)."""
    path = data_dir / "stations" / f"{station_id:05d}" / "hourly_cloudiness.csv"
    if not path.exists():
        raise SystemExit(
            f"{path} fehlt – bitte zuerst 'python fetch_hourly.py --datasets cloudiness' "
            f"laufen lassen."
        )
    return pd.read_csv(path, parse_dates=["timestamp"], usecols=["timestamp", "cloud_okta"])


def build_window(df: pd.DataFrame, days: int, years: int, stand: str | None = None,
                 cloud: pd.DataFrame | None = None):
    """Aktuelles Fenster plus die deckungsgleichen Fenster der Vorjahre.

    Zugeordnet wird über (Monat, Tag, Stunde). Fällt ein 29. Februar ins
    Fenster, fehlt er in Nicht-Schaltjahren schlicht – die Kurve hat dort
    eine Lücke, was ehrlicher ist als ein verschobener Wert.

    ``stand`` beschneidet die Reihe auf einen Stichtag; damit lässt sich das
    Bild so bauen, wie es an einem früheren Tag ausgesehen hätte.

    ``cloud`` hängt den Bedeckungsgrad an das aktuelle Fenster (Spalte
    ``cloud_okta``); die Vorjahre brauchen ihn nicht.
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
    if cloud is not None:
        current = current.merge(cloud, on="timestamp", how="left")
    else:
        current["cloud_okta"] = float("nan")

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


def day_lines(ax, current: pd.DataFrame) -> None:
    """Tagesgrenzen als Linien und 6-Stunden-Raster – im Temperaturfeld."""
    midnights = current.index[current["hour"] == 0].tolist()
    for x in midnights[1:]:
        ax.axvline(x - 0.5, color=wg.GRID, lw=0.9, zorder=1)
    for x in current.index[current["hour"].isin([6, 12, 18])]:
        ax.axvline(x, color=wg.GRID, lw=0.4, alpha=0.55, zorder=1)
    ax.set_xlim(-0.5, len(current) - 0.5)
    ax.set_xticks([])


def day_labels(ax, current: pd.DataFrame, pad: float) -> None:
    """Tagesnamen mittig unter der Achse, zweizeilig."""
    midnights = current.index[current["hour"] == 0].tolist()
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
    ax.tick_params(axis="x", length=0, pad=pad)
    ax.set_xlim(-0.5, len(current) - 0.5)


def tagesanteil(hoehe: float) -> float:
    """0 = Nacht, 1 = Tag, dazwischen Dämmerung – aus der Sonnenhöhe in Grad."""
    return float(min(1.0, max(0.0, (hoehe - NACHT_BIS) / (TAG_AB - NACHT_BIS))))


def sky_colors(current: pd.DataFrame, station_id: int) -> np.ndarray:
    """Der Himmel als Verlauf: Bedeckungsgrad auf der Tages- oder Nachtskala.

    Die Stundenwerte sind Momentwerte zur vollen Stunde; dazwischen wird linear
    interpoliert, im Raster von ``FEIN`` Minuten, damit der Streifen keine
    harten Stundenkanten hat. Die Skalen sind fest an 0 bis 8 Achtel gebunden;
    der Tagesanteil aus der Sonnenhöhe mischt beide Farben je Rasterpunkt, so
    dass auch die Dämmerung weich verläuft. Stunden ohne Wert bleiben weiß, wie
    die Kurve bei Messlücken eine Lücke lässt – Grau hieße „bedeckt".
    """
    tag = LinearSegmentedColormap.from_list("himmel_tag", wg.SKALEN["blau"])
    nacht = LinearSegmentedColormap.from_list("himmel_nacht", wg.NACHTSKALA)
    breite, laenge = wg.STATION_KOORDINATEN[station_id]

    stunden = pd.Series(current["cloud_okta"].to_numpy(), index=current["timestamp"])
    t0, t1 = stunden.index[0], stunden.index[-1]
    halb = pd.Timedelta(minutes=30)
    # Das Raster reicht wie die Felder bisher eine halbe Stunde über die
    # erste und letzte Messung hinaus; dort wird der Randwert gehalten.
    raster = pd.date_range(t0 - halb, t1 + halb, freq=f"{FEIN}min")
    fein = (stunden.reindex(stunden.index.union(raster))
                   .interpolate(method="time", limit_area="inside")
                   .reindex(raster).ffill().bfill())
    # Zu einer fehlenden Stunde gehört die halbe Stunde davor und danach:
    # sonst würde die Interpolation die Lücke einfach überbrücken.
    ohne_wert = set(stunden.index[stunden.isna()])
    farben = np.ones((1, len(raster), 3))
    for i, (ts, okta) in enumerate(zip(raster, fein.to_numpy())):
        if pd.isna(okta) or ts.round("h") in ohne_wert:
            continue
        anteil = tagesanteil(wg.sonnenhoehe(ts, breite, laenge))
        wert = min(1.0, max(0.0, okta / wg.OKTA_MAX))
        farben[0, i] = anteil * np.array(tag(wert)[:3]) + (1 - anteil) * np.array(nacht(wert)[:3])
    return farben


def sun_marks(ax, current: pd.DataFrame, station_id: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Sonnenauf- und -untergang je Tag als Marke mit Uhrzeit unter dem Streifen.

    Liefert die Zeiten für den Begleittext gleich mit.
    """
    breite, laenge = wg.STATION_KOORDINATEN[station_id]
    t0 = current["timestamp"].iloc[0]
    zeiten = []
    for tag in sorted({ts.normalize() for ts in current["timestamp"]}):
        auf, unter = wg.sonnenauf_untergang(tag, breite, laenge)
        zeiten.append((f"{tag.day}. {wg.MONTH_NAMES_LONG[tag.month - 1]}", auf, unter))
        for ts, marker in ((auf, 6), (unter, 7)):   # 6 = Caret nach oben, 7 = nach unten
            if ts is None:
                continue
            # Feld i deckt Stunde i ab und reicht von i − 0,5 bis i + 0,5.
            x = (ts - t0) / pd.Timedelta(hours=1) - 0.5
            if x < -0.5 or x > len(current) - 0.5:
                continue
            ax.plot([x], [-0.42], marker=marker, markersize=5, color=wg.TEXT_MUTED,
                    clip_on=False, lw=0, zorder=5)
            ax.text(x, -0.95, f"{ts:%H:%M}", ha="center", va="top", fontsize=8.5,
                    color=wg.TEXT_MUTED, clip_on=False)
    return zeiten


def sky_strip(ax, current: pd.DataFrame, station_id: int):
    """Der Himmel als Streifen, glatt interpoliert, Mitternacht als weiße Fuge."""
    ax.imshow(sky_colors(current, station_id), aspect="auto", interpolation="bilinear",
              extent=(-0.5, len(current) - 0.5, 0, 1), zorder=2)
    for x in current.index[current["hour"] == 0].tolist()[1:]:
        ax.axvline(x - 0.5, color=wg.BACKGROUND, lw=1.6, zorder=3)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_ylabel("Himmel", rotation=0, ha="right", va="center", labelpad=8,
                  fontsize=10, color=wg.TEXT_MUTED)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    return sun_marks(ax, current, station_id)


def himmel_absatz(current: pd.DataFrame, sonnenzeiten) -> str:
    """Erklärt den Streifen, nennt Kennzahlen und die Sonnenzeiten (UTC)."""
    okta = current["cloud_okta"]
    fehlend = int(okta.isna().sum())
    zeilen = [
        "Der Streifen darunter ist der Himmel im Verlauf der Stunden: Blau heißt klar, "
        "Grau heißt bedeckt, gemessen in Achteln des Himmels, die Wolken verdecken. "
        "Nachts dunkelt der Streifen ab – ein klarer Nachthimmel ist tief dunkelblau, "
        "ein bedeckter dunkelgrau. Die Marken darunter sind Sonnenauf- und -untergang."
    ]
    if okta.notna().any():
        zeilen.append(
            f"· Bewölkung im Mittel {wg.de_num(okta.mean())} Achtel, "
            f"{int((okta <= KLAR_BIS).sum())} klare und "
            f"{int((okta >= BEDECKT_AB).sum())} bedeckte Stunden"
        )
    if fehlend:
        zeilen.append(
            f"· {fehlend} Stunde{'n' if fehlend > 1 else ''} ohne bestimmbaren "
            f"Bedeckungsgrad (meist Nebel) bleiben im Streifen weiß"
        )
    sonne = [
        f"{tag} ↑ {auf:%H:%M} ↓ {unter:%H:%M}"
        for tag, auf, unter in sonnenzeiten if auf is not None and unter is not None
    ]
    if sonne:
        zeilen.append("· Sonne: " + ", ".join(sonne) + " (alle Zeiten UTC, wie die Messwerte)")
    return "\n".join(zeilen)


def caption(current, past, station_name: str, args, last, sonnenzeiten) -> str:
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
        f"\n\n{himmel_absatz(current, sonnenzeiten)}"
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
    cloud = load_cloud(args.data_dir, args.station)
    current, past, start, last = build_window(df, args.days, args.years, args.stand, cloud)
    station_name = wg.station_name(args.station, args.data_dir)

    # Layout in Zoll bei 200 dpi festlegen, gespeichert wird mit --dpi:
    # bei 200 dpi kommen exakt die 1080 px heraus, die Instagram nutzt.
    fig = plt.figure(figsize=(SIZE_PX / 200, SIZE_PX / 200), dpi=200)
    # Kein Titel, keine Fußzeile: alles Textliche steht im Begleittext, damit
    # das Bild im Feed nur die Kurven zeigt.
    # Oben etwas Luft lassen: die Einheit steht über der Skala und würde am
    # Bildrand sonst angeschnitten. Unten liegt der Himmelsstreifen mit den
    # Sonnenmarken, darunter die zweizeiligen Tagesnamen.
    ax = fig.add_axes((0.105, 0.305, 0.875, 0.635))
    # Bewusst kein sharex: geteilte Achsen zeichnen die Tagesnamen an beiden
    # Achsen; beide bekommen dieselben Grenzen stattdessen explizit gesetzt.
    ax_sky = fig.add_axes((0.105, 0.245, 0.875, 0.038))

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

    day_lines(ax, current)
    sonnenzeiten = sky_strip(ax_sky, current, args.station)
    # Die Tagesnamen sitzen unter den Sonnenmarken, deshalb der große Abstand
    # (in Punkt: 30 pt sind bei 200 dpi rund 85 px).
    day_labels(ax_sky, current, pad=30)
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
    text.write_text(caption(current, past, station_name, args, last, sonnenzeiten),
                    encoding="utf-8")

    print(f"geschrieben: {image}\ngeschrieben: {text}")
    # Letzte Zeile maschinenlesbar, damit post_daily.sh den Ordner findet,
    # ohne den Namen selbst zusammenbauen zu müssen.
    print(f"POST_DIR={post_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
