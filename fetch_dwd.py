#!/usr/bin/env python3
"""Holt DWD-Tagesdaten für die Stationen 4928 und 4931 und pflegt sie inkrementell fort.

Der Ablauf pro Station und Datensatz:

1. Verzeichnislisting auf opendata.dwd.de lesen und die zur Station gehörende
   ZIP-Datei bestimmen (der Dateiname der ``historical``-Datei enthält das
   Enddatum und ändert sich daher jährlich).
2. Name, Größe und ``Last-Modified`` gegen ``data/raw/manifest.json`` prüfen.
   Unveränderte Dateien werden gar nicht erst heruntergeladen.
3. Neu geladene Dateien parsen und in die bestehende CSV einmischen.
   Für Tage, die sowohl in ``historical`` als auch in ``recent`` vorkommen,
   gewinnt ``historical`` – das sind die endgültig geprüften Werte.

Ergebnis:

    data/stations.csv                      Stationsstammdaten
    data/data_dictionary.csv               Spaltenbeschreibungen
    data/raw/…                             Original-ZIPs (Cache)
    data/stations/04931/kl.csv             je Datensatz eine CSV
    data/stations/04931/daily.csv          alle Datensätze auf Datum gejoint

Aufruf:

    python fetch_dwd.py                    # alles aktualisieren
    python fetch_dwd.py --status           # nur zeigen, was lokal liegt
    python fetch_dwd.py --force            # Cache ignorieren, alles neu laden
    python fetch_dwd.py --datasets kl solar
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from dwd_datasets import (
    BASE_URL,
    COLUMN_DESCRIPTIONS,
    DATASETS,
    MERGED_COLUMN_ORDER,
    MISSING,
    STATIONS,
    Dataset,
)

USER_AGENT = "wettergeschichte/1.0 (DWD open data client)"
TIMEOUT = 120

#: ``historical`` schlägt ``recent``, weil dort die endgültig geprüften Werte stehen.
SOURCE_PRIORITY = {"recent": 0, "row": 1, "historical": 2}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def _open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def list_directory(url: str) -> dict[str, dict]:
    """Liest ein Apache-Verzeichnislisting und liefert ``{dateiname: {size, last_modified}}``."""
    with _open(url) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    entries: dict[str, dict] = {}
    # Zeilenformat: <a href="datei.zip">datei.zip</a>   17-Jun-2026 10:15:05   624178
    row = re.compile(
        r'<a href="(?P<name>[^"?/][^"]*\.zip)">.*?</a>\s*'
        r"(?P<date>\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2})\s+(?P<size>\d+)"
    )
    for m in row.finditer(html):
        entries[m.group("name")] = {
            "size": int(m.group("size")),
            "last_modified": m.group("date"),
        }
    return entries


def download(url: str) -> bytes:
    with _open(url) as resp:
        return resp.read()


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #


class Manifest:
    """Merkt sich, welche Remote-Datei zuletzt in welchem Stand verarbeitet wurde."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def key(station_id: int, dataset: str, subdir: str) -> str:
        return f"{station_id:05d}/{dataset}/{subdir or 'row'}"

    def is_current(self, key: str, entry: dict) -> bool:
        old = self.data.get(key)
        return bool(
            old
            and old.get("filename") == entry["filename"]
            and old.get("size") == entry["size"]
            and old.get("last_modified") == entry["last_modified"]
        )

    def update(self, key: str, entry: dict, rows: int) -> None:
        self.data[key] = {
            **entry,
            "rows": rows,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(dict(sorted(self.data.items())), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# --------------------------------------------------------------------------- #
# Parsen
# --------------------------------------------------------------------------- #


def parse_product(blob: bytes, ds: Dataset, source: str) -> pd.DataFrame:
    """Zieht die ``produkt_*.txt`` aus dem ZIP und macht daraus einen sauberen DataFrame."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n.startswith("produkt_") and n.endswith(".txt")]
        if not names:
            raise ValueError(f"keine produkt_*.txt im Archiv ({ds.key}/{source})")
        raw = zf.read(names[0])

    df = pd.read_csv(
        io.BytesIO(raw),
        sep=";",
        encoding="latin-1",
        na_values=[str(MISSING), f"{MISSING}.0", f"{MISSING}.000"],
        skipinitialspace=True,
    )
    df.columns = [c.strip() for c in df.columns]
    df = df.drop(columns=[c for c in ("eor", "eor ") if c in df.columns], errors="ignore")

    df["date"] = pd.to_datetime(df["MESS_DATUM"].astype(str).str[:8], format="%Y%m%d")
    df["station_id"] = df["STATIONS_ID"].astype(int)

    # Qualitätsniveaus zusammenfassen: das niedrigste der Datei ist die
    # konservative Aussage über den Tag.
    qn_cols = [c for c in ds.qn if c in df.columns]
    if qn_cols:
        df["quality_level"] = df[qn_cols].min(axis=1, skipna=True)

    keep = {src: dst for src, dst in ds.columns.items() if src in df.columns}
    missing = set(ds.columns) - set(keep)
    if missing:
        print(f"    Hinweis: Spalten fehlen in {ds.key}/{source}: {sorted(missing)}")

    out = df[["station_id", "date", *keep.keys()] + (["quality_level"] if qn_cols else [])]
    out = out.rename(columns=keep)
    for col in keep.values():
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.copy()
    out["source"] = source
    return out


def merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Führt alte und neue Daten zusammen; pro Tag gewinnt die vertrauenswürdigste Quelle."""
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df["_prio"] = df["source"].map(SOURCE_PRIORITY).fillna(0)
    df = df.sort_values(["date", "_prio"]).drop_duplicates(subset=["date"], keep="last")
    return df.drop(columns="_prio").sort_values("date").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Ablauf
# --------------------------------------------------------------------------- #


def dataset_csv(data_dir: Path, station_id: int, key: str) -> Path:
    return data_dir / "stations" / f"{station_id:05d}" / f"{key}.csv"


def update_dataset(
    station_id: int,
    ds: Dataset,
    data_dir: Path,
    manifest: Manifest,
    force: bool,
) -> str:
    """Aktualisiert einen Datensatz einer Station. Gibt eine kurze Statuszeile zurück."""
    pattern = re.compile(ds.filename_regex(station_id))
    new_frames: list[pd.DataFrame] = []
    touched: list[str] = []
    available = False

    # Fehlt die Ziel-CSV, hilft das Manifest nicht weiter – dann muss alles neu
    # geladen werden, auch wenn sich am Server nichts geändert hat.
    target = dataset_csv(data_dir, station_id, ds.key)
    force = force or not target.exists()

    for subdir in ds.subdirs:
        url_dir = ds.url(subdir)
        try:
            listing = list_directory(url_dir)
        except urllib.error.URLError as exc:
            print(f"    {ds.key}/{subdir or 'row'}: Verzeichnis nicht lesbar ({exc})")
            continue

        matches = sorted(n for n in listing if pattern.fullmatch(n))
        if not matches:
            continue
        available = True
        filename = matches[-1]
        entry = {"filename": filename, "url": url_dir + filename, **listing[filename]}
        key = manifest.key(station_id, ds.key, subdir)

        if not force and manifest.is_current(key, entry):
            continue

        blob = download(entry["url"])
        cache = data_dir / "raw" / ds.key
        cache.mkdir(parents=True, exist_ok=True)
        (cache / filename).write_bytes(blob)

        frame = parse_product(blob, ds, subdir or "row")
        new_frames.append(frame)
        manifest.update(key, entry, len(frame))
        touched.append(f"{subdir or 'row'} (+{len(frame)} Zeilen, Stand {entry['last_modified']})")

    if not available:
        return f"{ds.key}: für Station {station_id} nicht vorhanden"

    if not new_frames:
        n = sum(1 for _ in target.open(encoding="utf-8")) - 1
        return f"{ds.key}: unverändert ({n} Tage)"

    frames = list(new_frames)
    if target.exists():
        frames.insert(0, pd.read_csv(target, parse_dates=["date"]))

    merged = merge_frames(frames)
    target.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(target, index=False, date_format="%Y-%m-%d")

    span = f"{merged['date'].min():%Y-%m-%d} … {merged['date'].max():%Y-%m-%d}"
    return f"{ds.key}: {', '.join(touched)} -> {len(merged)} Tage, {span}"


def build_daily(station_id: int, data_dir: Path) -> Path | None:
    """Joint alle Datensätze einer Station auf das Datum zu einer breiten Tages-CSV."""
    merged: pd.DataFrame | None = None
    for key, ds in DATASETS.items():
        path = dataset_csv(data_dir, station_id, key)
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["date"])
        cols = ["date", *[c for c in ds.columns.values() if c in df.columns]]
        df = df[cols]
        merged = df if merged is None else merged.merge(df, on="date", how="outer")

    if merged is None:
        return None

    merged.insert(0, "station_id", station_id)
    ordered = [c for c in MERGED_COLUMN_ORDER if c in merged.columns]
    merged = merged[ordered + [c for c in merged.columns if c not in ordered]]
    merged = merged.sort_values("date").reset_index(drop=True)

    out = data_dir / "stations" / f"{station_id:05d}" / "daily.csv"
    merged.to_csv(out, index=False, date_format="%Y-%m-%d")
    return out


def write_station_metadata(data_dir: Path) -> None:
    url = f"{BASE_URL}/kl/recent/KL_Tageswerte_Beschreibung_Stationen.txt"
    try:
        text = download(url).decode("latin-1")
    except urllib.error.URLError as exc:
        print(f"  Stationsliste nicht abrufbar ({exc}) – überspringe")
        return

    rows = []
    for line in text.splitlines()[2:]:
        if not line.strip():
            continue
        sid = line[:5].strip()
        if not sid.isdigit() or int(sid) not in STATIONS:
            continue
        rows.append(
            {
                "station_id": int(sid),
                "name": line[61:102].strip(),
                "state": line[102:143].strip(),
                "from_date": line[6:14],
                "to_date": line[15:23],
                "altitude_m": int(line[24:38].strip()),
                "latitude": float(line[38:50].strip()),
                "longitude": float(line[50:60].strip()),
            }
        )
    if rows:
        pd.DataFrame(rows).to_csv(data_dir / "stations.csv", index=False)


def write_data_dictionary(data_dir: Path) -> None:
    rows = []
    for ds in DATASETS.values():
        for src, dst in ds.columns.items():
            unit, desc = COLUMN_DESCRIPTIONS.get(dst, ("", ""))
            rows.append(
                {
                    "column": dst,
                    "dwd_column": src,
                    "dataset": ds.key,
                    "unit": unit,
                    "description": desc,
                }
            )
    pd.DataFrame(rows).to_csv(data_dir / "data_dictionary.csv", index=False)


def print_status(data_dir: Path) -> None:
    for station_id, name in STATIONS.items():
        print(f"\nStation {station_id} – {name}")
        base = data_dir / "stations" / f"{station_id:05d}"
        if not base.exists():
            print("  (keine Daten – bitte 'python fetch_dwd.py' laufen lassen)")
            continue
        for path in sorted(base.glob("*.csv")):
            df = pd.read_csv(path, usecols=["date"], parse_dates=["date"])
            print(
                f"  {path.stem:<24} {len(df):>7} Tage  "
                f"{df['date'].min():%Y-%m-%d} … {df['date'].max():%Y-%m-%d}"
            )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--stations", type=int, nargs="+", default=list(STATIONS))
    ap.add_argument("--datasets", nargs="+", choices=list(DATASETS), default=list(DATASETS))
    ap.add_argument("--force", action="store_true", help="Cache ignorieren und alles neu laden")
    ap.add_argument("--status", action="store_true", help="nur den lokalen Bestand zeigen")
    args = ap.parse_args(argv)

    data_dir: Path = args.data_dir
    if args.status:
        print_status(data_dir)
        return 0

    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(data_dir / "raw" / "manifest.json")

    write_station_metadata(data_dir)
    write_data_dictionary(data_dir)

    for station_id in args.stations:
        print(f"\nStation {station_id} – {STATIONS.get(station_id, '?')}")
        for key in args.datasets:
            try:
                print("  " + update_dataset(station_id, DATASETS[key], data_dir, manifest, args.force))
            except (urllib.error.URLError, ValueError, zipfile.BadZipFile) as exc:
                print(f"  {key}: Fehler – {exc}")
        manifest.save()
        daily = build_daily(station_id, data_dir)
        if daily:
            df = pd.read_csv(daily, usecols=["date"], parse_dates=["date"])
            print(f"  -> {daily.relative_to(data_dir.parent)}: {len(df)} Tage")

    manifest.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
