#!/usr/bin/env python3
"""Veröffentlicht ein fertiges Bild samt Bildtext auf Instagram (Graph API).

Ablauf der Instagram Content Publishing API – immer zweistufig:

1. ``POST /{ig-user-id}/media``          Container anlegen (Bild-URL + Caption)
2. ``GET  /{container-id}?fields=status_code``  warten, bis ``FINISHED``
3. ``POST /{ig-user-id}/media_publish``  Container veröffentlichen

Der Haken: **die API lädt keine Datei hoch.** Sie holt sich das Bild von einer
öffentlich erreichbaren URL. Die JPGs aus ``output/`` müssen also vorher
irgendwo liegen, wo Meta sie abrufen kann (GitHub Pages, S3, eigener Webspace).
Siehe INSTAGRAM.md.

Voraussetzungen:

    export IG_USER_ID=17841400000000000
    export IG_ACCESS_TOKEN=EAAG...          # langlebiges Token

Aufruf:

    # zeigt nur, was passieren würde (Standard)
    python instagram_post.py --image-url https://example.org/wetter.jpg \\
        --caption-file output/instagram_nyt_04931_2026.txt

    # tatsächlich veröffentlichen
    python instagram_post.py --image-url https://example.org/wetter.jpg \\
        --caption-file output/instagram_nyt_04931_2026.txt --publish
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

#: Aktuelle Graph-API-Version (Stand Februar 2026). Ältere Versionen laufen aus,
#: deshalb bewusst als Option und nicht fest verdrahtet.
DEFAULT_API_VERSION = "v25.0"
GRAPH = "https://graph.facebook.com"

#: Instagram erlaubt 100 API-Posts je Konto in 24 Stunden.
DAILY_LIMIT = 100


class GraphError(RuntimeError):
    pass


def _call(method: str, url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}", method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body)["error"]["message"]
        except Exception:
            message = body
        raise GraphError(f"{exc.code} {exc.reason}: {message}") from None


def create_container(base: str, ig_user: str, token: str, image_url: str, caption: str) -> str:
    res = _call("POST", f"{base}/{ig_user}/media",
                {"image_url": image_url, "caption": caption, "access_token": token})
    if "id" not in res:
        raise GraphError(f"unerwartete Antwort beim Anlegen des Containers: {res}")
    return res["id"]


def wait_ready(base: str, container: str, token: str, timeout: int = 180) -> None:
    """Der Container wird asynchron verarbeitet; erst FINISHED darf publiziert werden."""
    deadline = time.monotonic() + timeout
    while True:
        res = _call("GET", f"{base}/{container}",
                    {"fields": "status_code,status", "access_token": token})
        status = res.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise GraphError(f"Instagram konnte das Bild nicht verarbeiten: {res.get('status')}")
        if time.monotonic() > deadline:
            raise GraphError(f"Zeitüberschreitung, Status blieb bei {status!r}")
        time.sleep(3)


def publish(base: str, ig_user: str, token: str, container: str) -> str:
    res = _call("POST", f"{base}/{ig_user}/media_publish",
                {"creation_id": container, "access_token": token})
    if "id" not in res:
        raise GraphError(f"unerwartete Antwort beim Veröffentlichen: {res}")
    return res["id"]


def quota_used(base: str, ig_user: str, token: str) -> tuple[int, int] | None:
    """Wie viele der erlaubten Posts sind in den letzten 24 h schon verbraucht?"""
    try:
        res = _call("GET", f"{base}/{ig_user}/content_publishing_limit",
                    {"fields": "config,quota_usage", "access_token": token})
    except GraphError:
        return None
    entry = (res.get("data") or [{}])[0]
    limit = (entry.get("config") or {}).get("quota_total", DAILY_LIMIT)
    return int(entry.get("quota_usage", 0)), int(limit)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image-url", required=True,
                    help="öffentlich erreichbare URL des JPEGs (kein lokaler Pfad!)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--caption", help="Bildtext direkt")
    group.add_argument("--caption-file", type=Path, help="Bildtext aus Datei")
    ap.add_argument("--publish", action="store_true",
                    help="wirklich veröffentlichen (ohne dieses Flag nur Vorschau)")
    ap.add_argument("--api-version", default=DEFAULT_API_VERSION)
    ap.add_argument("--ig-user-id", default=os.environ.get("IG_USER_ID"))
    ap.add_argument("--access-token", default=os.environ.get("IG_ACCESS_TOKEN"))
    args = ap.parse_args(argv)

    caption = args.caption if args.caption else args.caption_file.read_text(encoding="utf-8")
    caption = caption.strip()
    if len(caption) > 2200:
        print(f"Warnung: Bildtext ist {len(caption)} Zeichen lang, Instagram kürzt bei 2200.")

    base = f"{GRAPH}/{args.api_version}"

    if not args.publish:
        print("Vorschau (nichts gesendet – zum Veröffentlichen --publish angeben)\n")
        print(f"  Endpunkt   {base}/{args.ig_user_id or '<IG_USER_ID>'}/media")
        print(f"  Bild-URL   {args.image_url}")
        print(f"  Zeichen    {len(caption)}")
        print("\n--- Bildtext ---")
        print(caption)
        return 0

    if not args.ig_user_id or not args.access_token:
        print("IG_USER_ID und IG_ACCESS_TOKEN fehlen (Umgebungsvariablen oder Optionen).",
              file=sys.stderr)
        return 2

    try:
        used = quota_used(base, args.ig_user_id, args.access_token)
        if used:
            print(f"Kontingent: {used[0]} von {used[1]} Posts in den letzten 24 h verbraucht")

        print("Container anlegen …")
        container = create_container(base, args.ig_user_id, args.access_token,
                                     args.image_url, caption)
        print(f"  Container {container}")

        print("auf Verarbeitung warten …")
        wait_ready(base, container, args.access_token)

        print("veröffentlichen …")
        media_id = publish(base, args.ig_user_id, args.access_token, container)
        print(f"fertig – Media-ID {media_id}")
    except GraphError as exc:
        print(f"Instagram-API meldet: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
