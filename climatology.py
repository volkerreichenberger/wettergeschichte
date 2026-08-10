#!/usr/bin/env python3
"""Leitet aus den DWD-Tagesdaten die Kennzahlen für das NYT-Diagramm ab.

Das klassische New-York-Times-Klimadiagramm braucht pro Kalendertag vier Größen:

* **Rekordspanne**  – tiefstes je gemessenes Minimum, höchstes je gemessenes Maximum
* **Normalspanne**  – mittleres Tagesminimum und -maximum der Referenzperiode
* **Tageswerte**    – Minimum und Maximum des dargestellten Jahres
* **Abweichung**    – liegt der Tag über oder unter der Normalspanne?

Damit R und Python garantiert dieselben Zahlen zeichnen, werden alle Kennzahlen
hier einmal berechnet und als CSV nach ``data/derived/`` geschrieben.

    python climatology.py                     # beide Stationen, aktuelles Jahr
    python climatology.py --year 2025
    python climatology.py --reference 1961 1990
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from dwd_datasets import STATIONS

#: WMO-Normalperiode; bewusst konfigurierbar (--reference).
REFERENCE_PERIOD = (1991, 2020)

#: Fenster in Tagen, über das die Normalen geglättet werden (zentriert).
SMOOTHING_WINDOW = 15


def load_daily(data_dir: Path, station_id: int) -> pd.DataFrame:
    path = data_dir / "stations" / f"{station_id:05d}" / "daily.csv"
    if not path.exists():
        raise SystemExit(f"{path} fehlt – bitte zuerst 'python fetch_dwd.py' laufen lassen")
    df = pd.read_csv(path, parse_dates=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    # Der 29. Februar bekommt keinen eigenen Platz auf der x-Achse: wir zählen
    # den Tag im Jahr so, als hätte jedes Jahr 365 Tage. Dadurch liegen alle
    # Jahre deckungsgleich übereinander.
    df["doy"] = doy_no_leap(df["date"])
    return df


def doy_no_leap(dates: pd.Series) -> pd.Series:
    """Tag im Jahr, wobei der 29.02. auf denselben Index wie der 28.02. fällt."""
    doy = dates.dt.dayofyear
    leap = dates.dt.is_leap_year & (doy > 59)
    return doy.where(~leap, doy - 1)


def circular_rolling_mean(values: pd.Series, window: int) -> pd.Series:
    """Zentrierter gleitender Mittelwert, der über den Jahreswechsel hinweg schließt."""
    padded = pd.concat([values.iloc[-window:], values, values.iloc[:window]], ignore_index=True)
    smoothed = padded.rolling(window, center=True, min_periods=1).mean()
    return smoothed.iloc[window : window + len(values)].reset_index(drop=True)


def build_climatology(
    df: pd.DataFrame, reference: tuple[int, int], window: int = SMOOTHING_WINDOW
) -> pd.DataFrame:
    """Pro Kalendertag: Rekorde über die ganze Reihe, Normalen über die Referenzperiode."""
    obs = df.dropna(subset=["temp_max_c", "temp_min_c"])

    records = (
        obs.groupby("doy")
        .agg(
            record_high=("temp_max_c", "max"),
            record_low=("temp_min_c", "min"),
            n_years=("year", "nunique"),
        )
        .reset_index()
    )

    # Jahr des Rekords mitführen – das sind die Beschriftungen im NYT-Original.
    hi = obs.loc[obs.groupby("doy")["temp_max_c"].idxmax(), ["doy", "year"]]
    lo = obs.loc[obs.groupby("doy")["temp_min_c"].idxmin(), ["doy", "year"]]
    records = records.merge(hi.rename(columns={"year": "record_high_year"}), on="doy")
    records = records.merge(lo.rename(columns={"year": "record_low_year"}), on="doy")

    ref = obs[obs["year"].between(*reference)]
    if ref.empty:
        raise SystemExit(f"keine Daten in der Referenzperiode {reference[0]}–{reference[1]}")
    normals = (
        ref.groupby("doy")
        .agg(
            normal_high=("temp_max_c", "mean"),
            normal_low=("temp_min_c", "mean"),
            normal_mean=("temp_mean_c", "mean"),
            normal_precip=("precip_mm", "mean"),
        )
        .reset_index()
    )
    for col in ("normal_high", "normal_low", "normal_mean", "normal_precip"):
        normals[col] = circular_rolling_mean(normals[col], window)

    clim = records.merge(normals, on="doy").sort_values("doy").reset_index(drop=True)
    clim["reference_from"], clim["reference_to"] = reference
    clim["record_from"] = int(obs["year"].min())
    clim["record_to"] = int(obs["year"].max())
    # Label für die x-Achse: ein fiktives Nicht-Schaltjahr.
    clim["label_date"] = pd.to_datetime("2001-01-01") + pd.to_timedelta(clim["doy"] - 1, unit="D")
    clim["month"] = clim["label_date"].dt.month
    return clim


def build_year(df: pd.DataFrame, clim: pd.DataFrame, year: int) -> pd.DataFrame:
    """Tageswerte eines Jahres, angereichert um die Lage zur Normalspanne."""
    cols = [
        "date", "doy", "temp_min_c", "temp_max_c", "temp_mean_c",
        "precip_mm", "sunshine_h", "snow_depth_cm",
    ]
    year_df = df.loc[df["year"] == year, [c for c in cols if c in df.columns]].copy()
    if year_df.empty:
        raise SystemExit(f"keine Daten für {year}")

    year_df = year_df.merge(
        clim[["doy", "normal_high", "normal_low", "record_high", "record_low"]], on="doy", how="left"
    )
    year_df["above_normal"] = year_df["temp_max_c"] - year_df["normal_high"]
    year_df["below_normal"] = year_df["normal_low"] - year_df["temp_min_c"]
    year_df["anomaly"] = year_df["temp_mean_c"] - (year_df["normal_high"] + year_df["normal_low"]) / 2

    # Der Balken des Tages wird in drei Teile zerlegt: der Teil innerhalb der
    # Normalspanne, der Überschuss nach oben und der nach unten. Genau so
    # entstehen im Original die roten und blauen Spitzen.
    year_df["bar_low"] = year_df["temp_min_c"]
    year_df["bar_high"] = year_df["temp_max_c"]
    year_df["warm_from"] = np.maximum(year_df["temp_min_c"], year_df["normal_high"])
    year_df["warm_to"] = year_df["temp_max_c"]
    year_df["cold_from"] = year_df["temp_min_c"]
    year_df["cold_to"] = np.minimum(year_df["temp_max_c"], year_df["normal_low"])
    year_df.loc[year_df["warm_to"] <= year_df["warm_from"], ["warm_from", "warm_to"]] = np.nan
    year_df.loc[year_df["cold_to"] <= year_df["cold_from"], ["cold_from", "cold_to"]] = np.nan

    year_df["is_record_high"] = year_df["temp_max_c"] >= year_df["record_high"]
    year_df["is_record_low"] = year_df["temp_min_c"] <= year_df["record_low"]
    year_df["precip_cum"] = year_df["precip_mm"].fillna(0).cumsum()
    return year_df


def build_recent_years(df: pd.DataFrame, clim: pd.DataFrame, year: int, n: int = 5) -> pd.DataFrame:
    """Das laufende Jahr plus die n Vorjahre – Rohwerte und geglättete Verläufe.

    Ein Jahr mehr als die Vergleichsgrafik braucht: die Strich-Variante stellt
    das laufende Jahr als Balken dar und die n Vorjahre als Min/Max-Striche.
    Grafiken, die nur fünf Verläufe zeigen wollen, schneiden selbst zu.
    """
    years = list(range(year - n, year + 1))
    sub = df[df["year"].isin(years)].copy()
    sub = sub.merge(clim[["doy", "normal_mean", "normal_precip"]], on="doy", how="left")
    sub = sub.sort_values(["year", "doy"])

    # 31-Tage-Mittel: ohne Glättung ist der Vergleich mehrerer Jahre nur Rauschen.
    sub["temp_smooth"] = sub.groupby("year")["temp_mean_c"].transform(
        lambda s: s.rolling(31, center=True, min_periods=10).mean()
    )
    sub["precip_cum"] = sub.groupby("year")["precip_mm"].transform(lambda s: s.fillna(0).cumsum())
    sub["anomaly"] = sub["temp_mean_c"] - sub["normal_mean"]
    sub["anomaly_smooth"] = sub.groupby("year")["anomaly"].transform(
        lambda s: s.rolling(31, center=True, min_periods=10).mean()
    )
    keep = [
        "date", "year", "doy", "temp_mean_c", "temp_min_c", "temp_max_c", "temp_smooth",
        "precip_mm", "precip_cum", "normal_mean", "normal_precip", "anomaly", "anomaly_smooth",
    ]
    return sub[[c for c in keep if c in sub.columns]].reset_index(drop=True)


def summarise(year_df: pd.DataFrame, clim: pd.DataFrame, station_id: int, year: int) -> dict:
    """Die Zahlen, die als Text ins Diagramm wandern."""
    valid = year_df.dropna(subset=["temp_mean_c"])
    normal_mean = clim.loc[clim["doy"].isin(valid["doy"]), "normal_mean"].mean()
    return {
        "station_id": station_id,
        "station_name": STATIONS.get(station_id, str(station_id)),
        "year": year,
        "days_with_data": int(len(valid)),
        "last_date": valid["date"].max().date().isoformat() if len(valid) else None,
        "temp_mean": round(float(valid["temp_mean_c"].mean()), 2) if len(valid) else None,
        "normal_mean": round(float(normal_mean), 2) if pd.notna(normal_mean) else None,
        "anomaly": round(float(valid["temp_mean_c"].mean() - normal_mean), 2) if len(valid) else None,
        "temp_max": round(float(year_df["temp_max_c"].max()), 1),
        "temp_max_date": year_df.loc[year_df["temp_max_c"].idxmax(), "date"].date().isoformat(),
        "temp_min": round(float(year_df["temp_min_c"].min()), 1),
        "temp_min_date": year_df.loc[year_df["temp_min_c"].idxmin(), "date"].date().isoformat(),
        "record_highs": int(year_df["is_record_high"].sum()),
        "record_lows": int(year_df["is_record_low"].sum()),
        "days_above_30": int((year_df["temp_max_c"] >= 30).sum()),
        "days_above_25": int((year_df["temp_max_c"] >= 25).sum()),
        "frost_days": int((year_df["temp_min_c"] < 0).sum()),
        "precip_sum": round(float(year_df["precip_mm"].sum()), 1),
        "precip_normal_sum": round(float(clim.loc[clim["doy"].isin(valid["doy"]), "normal_precip"].sum()), 1),
        "reference_from": int(clim["reference_from"].iloc[0]),
        "reference_to": int(clim["reference_to"].iloc[0]),
        "record_from": int(clim["record_from"].iloc[0]),
        "record_to": int(clim["record_to"].iloc[0]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--stations", type=int, nargs="+", default=list(STATIONS))
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--reference", type=int, nargs=2, default=list(REFERENCE_PERIOD),
                    metavar=("VON", "BIS"))
    ap.add_argument("--recent-years", type=int, default=5)
    args = ap.parse_args(argv)

    out_dir: Path = args.data_dir / "derived"
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for station_id in args.stations:
        df = load_daily(args.data_dir, station_id)
        clim = build_climatology(df, tuple(args.reference))
        year_df = build_year(df, clim, args.year)
        recent = build_recent_years(df, clim, args.year, args.recent_years)
        summary = summarise(year_df, clim, station_id, args.year)
        summaries.append(summary)

        tag = f"{station_id:05d}"
        clim.to_csv(out_dir / f"climatology_{tag}.csv", index=False, date_format="%Y-%m-%d")
        year_df.to_csv(out_dir / f"year_{tag}_{args.year}.csv", index=False, date_format="%Y-%m-%d")
        recent.to_csv(out_dir / f"recent_{tag}_{args.year}.csv", index=False, date_format="%Y-%m-%d")

        print(
            f"{station_id} {summary['station_name']}: {args.year} bisher "
            f"{summary['temp_mean']} °C, Normal {summary['normal_mean']} °C "
            f"({summary['anomaly']:+.2f} K), {summary['days_above_30']} heiße Tage, "
            f"{summary['record_highs']} Tagesrekorde"
        )

    pd.DataFrame(summaries).to_csv(out_dir / f"summary_{args.year}.csv", index=False)
    print(f"\ngeschrieben nach {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
