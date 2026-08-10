#!/usr/bin/env python3
"""Holt die stündlichen Lufttemperaturen des DWD – inkrementell wie fetch_dwd.py.

Für Auswertungen über wenige Tage reichen Tageswerte nicht: drei Tage sind
drei Punkte, keine Kurve. Dieser Fetcher lädt deshalb zusätzlich den
Stundendatensatz ``hourly/air_temperature`` (Kürzel TU).

Die Logik ist dieselbe wie bei den Tageswerten: Verzeichnislisting lesen,
Dateiname/Größe/Last-Modified gegen das Manifest prüfen, nur Geändertes laden,
und beim Zusammenführen gewinnt ``historical`` gegen ``recent``.

    python fetch_hourly.py
    python fetch_hourly.py --status
    python fetch_hourly.py --force
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.error
import zipfile
from pathlib import Path

import pandas as pd

from dwd_datasets import MISSING, STATIONS
from fetch_dwd import SOURCE_PRIORITY, Manifest, download, list_directory

BASE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/"
    "observations_germany/climate/hourly/air_temperature"
)

DATASET = "hourly_air_temperature"
PATTERN = r"stundenwerte_TU_{sid}_.*\.zip"
COLUMNS = {"TT_TU": "temp_c", "RF_TU": "humidity_pct"}
QN = "QN_9"


def target_csv(data_dir: Path, station_id: int) -> Path:
    return data_dir / "stations" / f"{station_id:05d}" / f"{DATASET}.csv"


def parse_product(blob: bytes, source: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n.startswith("produkt_") and n.endswith(".txt")]
        if not names:
            raise ValueError(f"keine produkt_*.txt im Archiv ({source})")
        raw = zf.read(names[0])

    df = pd.read_csv(
        io.BytesIO(raw), sep=";", encoding="latin-1",
        na_values=[str(MISSING), f"{MISSING}.0"], skipinitialspace=True,
    )
    df.columns = [c.strip() for c in df.columns]

    # MESS_DATUM ist hier YYYYMMDDHH statt YYYYMMDD wie bei den Tageswerten.
    df["timestamp"] = pd.to_datetime(df["MESS_DATUM"].astype(str), format="%Y%m%d%H")
    df["station_id"] = df["STATIONS_ID"].astype(int)
    if QN in df.columns:
        df["quality_level"] = df[QN]

    keep = {src: dst for src, dst in COLUMNS.items() if src in df.columns}
    cols = ["station_id", "timestamp", *keep] + (["quality_level"] if QN in df.columns else [])
    out = df[cols].rename(columns=keep).copy()
    for col in keep.values():
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["source"] = source
    return out


def update_station(station_id: int, data_dir: Path, manifest: Manifest, force: bool) -> str:
    pattern = re.compile(PATTERN.format(sid=f"{station_id:05d}"))
    target = target_csv(data_dir, station_id)
    force = force or not target.exists()

    new_frames: list[pd.DataFrame] = []
    touched: list[str] = []

    for subdir in ("historical", "recent"):
        url_dir = f"{BASE_URL}/{subdir}/"
        try:
            listing = list_directory(url_dir)
        except urllib.error.URLError as exc:
            print(f"    {subdir}: Verzeichnis nicht lesbar ({exc})")
            continue

        matches = sorted(n for n in listing if pattern.fullmatch(n))
        if not matches:
            continue
        filename = matches[-1]
        entry = {"filename": filename, "url": url_dir + filename, **listing[filename]}
        key = manifest.key(station_id, DATASET, subdir)
        if not force and manifest.is_current(key, entry):
            continue

        blob = download(entry["url"])
        cache = data_dir / "raw" / DATASET
        cache.mkdir(parents=True, exist_ok=True)
        (cache / filename).write_bytes(blob)

        frame = parse_product(blob, subdir)
        new_frames.append(frame)
        manifest.update(key, entry, len(frame))
        touched.append(f"{subdir} (+{len(frame)} Stunden, Stand {entry['last_modified']})")

    if not new_frames:
        n = sum(1 for _ in target.open(encoding="utf-8")) - 1
        return f"unverändert ({n} Stunden)"

    frames = list(new_frames)
    if target.exists():
        frames.insert(0, pd.read_csv(target, parse_dates=["timestamp"]))

    df = pd.concat(frames, ignore_index=True)
    df["_prio"] = df["source"].map(SOURCE_PRIORITY).fillna(0)
    df = (
        df.sort_values(["timestamp", "_prio"])
        .drop_duplicates(subset=["timestamp"], keep="last")
        .drop(columns="_prio")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)
    span = f"{df['timestamp'].min():%Y-%m-%d %H} … {df['timestamp'].max():%Y-%m-%d %H} Uhr"
    return f"{', '.join(touched)} -> {len(df)} Stunden, {span}"


def print_status(data_dir: Path) -> None:
    for station_id, name in STATIONS.items():
        path = target_csv(data_dir, station_id)
        if not path.exists():
            print(f"{station_id} {name}: keine Stundendaten – 'python fetch_hourly.py' laufen lassen")
            continue
        df = pd.read_csv(path, usecols=["timestamp"], parse_dates=["timestamp"])
        print(f"{station_id} {name}: {len(df)} Stunden, "
              f"{df['timestamp'].min():%Y-%m-%d} … {df['timestamp'].max():%Y-%m-%d %H} Uhr")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--stations", type=int, nargs="+", default=list(STATIONS))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    if args.status:
        print_status(args.data_dir)
        return 0

    manifest = Manifest(args.data_dir / "raw" / "manifest.json")
    for station_id in args.stations:
        print(f"Station {station_id} – {STATIONS.get(station_id, '?')}")
        try:
            print("  " + update_station(station_id, args.data_dir, manifest, args.force))
        except (urllib.error.URLError, ValueError, zipfile.BadZipFile) as exc:
            print(f"  Fehler – {exc}")
        manifest.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
