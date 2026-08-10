#!/usr/bin/env python3
"""Veröffentlicht ein fertiges Bild samt Bildtext auf Instagram.

Meta bietet zwei getrennte Wege an; welcher gilt, hängt davon ab, welches
Produkt in der Meta-App eingerichtet ist:

* ``--api instagram``  Instagram-Login, Aufrufe gegen ``graph.instagram.com``.
  Braucht keine Facebook-Seite. Berechtigungen ``instagram_business_basic``
  und ``instagram_business_content_publish``. Das ist die Vorgabe.
* ``--api facebook``   Facebook-Login, Aufrufe gegen ``graph.facebook.com``.
  Braucht eine verknüpfte Facebook-Seite und ein Seiten- oder Nutzer-Token.

Der Veröffentlichungsablauf ist in beiden Fällen derselbe – immer dreistufig:

1. ``POST /{ig-user-id}/media``                 Container anlegen (Bild-URL + Text)
2. ``GET  /{container-id}?fields=status_code``  warten, bis ``FINISHED``
3. ``POST /{ig-user-id}/media_publish``         Container veröffentlichen

Der Haken: **die API lädt keine Datei hoch.** Sie holt sich das Bild von einer
öffentlich erreichbaren URL. Siehe INSTAGRAM.md.

Hilfsaufrufe, die kein Bild brauchen:

    python instagram_post.py --whoami                    # ID und Kontoname zeigen
    python instagram_post.py --exchange-token KURZ_TOKEN --app-secret GEHEIM
    python instagram_post.py --refresh-token             # verlängert um 60 Tage

Veröffentlichen:

    export IG_USER_ID=17841400000000000
    export IG_ACCESS_TOKEN=IGAA...

    # zeigt nur, was passieren würde (Standard)
    python instagram_post.py --image-url https://example.org/wetter.jpg \\
        --caption-file posts/drei_tage_04931_2026-08-09/text.txt

    # tatsächlich veröffentlichen
    python instagram_post.py --image-url https://example.org/wetter.jpg \\
        --caption-file posts/drei_tage_04931_2026-08-09/text.txt --publish
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
from datetime import date, timedelta
from pathlib import Path

#: Aktuelle Graph-API-Version (Stand Februar 2026). Ältere laufen aus,
#: deshalb als Option und nicht fest verdrahtet.
DEFAULT_API_VERSION = "v25.0"

HOSTS = {
    "instagram": "https://graph.instagram.com",
    "facebook": "https://graph.facebook.com",
}

#: Instagram erlaubt 100 API-Posts je Konto in 24 Stunden.
DAILY_LIMIT = 100

MAX_CAPTION = 2200


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


# --------------------------------------------------------------------------- #
# Veröffentlichen
# --------------------------------------------------------------------------- #


#: Instagram nimmt höchstens zehn Bilder in einen Karussell-Beitrag.
MAX_CAROUSEL = 10


def create_container(base: str, ig_user: str, token: str, image_url: str, caption: str) -> str:
    res = _call("POST", f"{base}/{ig_user}/media",
                {"image_url": image_url, "caption": caption, "access_token": token})
    if "id" not in res:
        raise GraphError(f"unerwartete Antwort beim Anlegen des Containers: {res}")
    return res["id"]


def create_child(base: str, ig_user: str, token: str, image_url: str) -> str:
    """Einzelbild eines Karussells – trägt keinen eigenen Bildtext."""
    res = _call("POST", f"{base}/{ig_user}/media",
                {"image_url": image_url, "is_carousel_item": "true", "access_token": token})
    if "id" not in res:
        raise GraphError(f"unerwartete Antwort beim Anlegen eines Karussell-Bildes: {res}")
    return res["id"]


def create_carousel(base: str, ig_user: str, token: str, children: list[str], caption: str) -> str:
    res = _call("POST", f"{base}/{ig_user}/media",
                {"media_type": "CAROUSEL", "children": ",".join(children),
                 "caption": caption, "access_token": token})
    if "id" not in res:
        raise GraphError(f"unerwartete Antwort beim Anlegen des Karussells: {res}")
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
            raise GraphError(
                f"Instagram konnte das Bild nicht verarbeiten: {res.get('status')}. "
                "Häufigste Ursache: die Bild-URL ist von außen nicht erreichbar."
            )
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


# --------------------------------------------------------------------------- #
# Hilfsaufrufe rund um Konto und Token
# --------------------------------------------------------------------------- #


def whoami(api: str, base: str, token: str) -> dict:
    """Liefert die numerische Konto-ID und den Kontonamen.

    Beim Instagram-Login steht die gesuchte ID in ``user_id``; ``id`` ist eine
    andere, app-bezogene Kennung und taugt nicht als IG_USER_ID.
    """
    if api == "instagram":
        return _call("GET", f"{base}/me",
                     {"fields": "user_id,username", "access_token": token})
    # Beim Facebook-Login führt der Weg über die Seite.
    pages = _call("GET", f"{base}/me/accounts",
                  {"fields": "id,name", "access_token": token})
    out: dict = {"pages": pages.get("data", [])}
    for page in out["pages"]:
        linked = _call("GET", f"{base}/{page['id']}",
                       {"fields": "instagram_business_account{id,username}",
                        "access_token": token})
        page["instagram_business_account"] = linked.get("instagram_business_account")
    return out


def exchange_token(api: str, short_token: str, app_secret: str) -> dict:
    """Kurzlebiges Token (etwa eine Stunde) gegen ein langlebiges (60 Tage) tauschen."""
    if api == "instagram":
        return _call("GET", f"{HOSTS['instagram']}/access_token",
                     {"grant_type": "ig_exchange_token",
                      "client_secret": app_secret, "access_token": short_token})
    raise GraphError(
        "Beim Facebook-Login braucht der Tausch zusätzlich die App-ID:\n"
        "  curl 'https://graph.facebook.com/" + DEFAULT_API_VERSION + "/oauth/access_token"
        "?grant_type=fb_exchange_token&client_id=<APP_ID>"
        "&client_secret=<APP_SECRET>&fb_exchange_token=<KURZ_TOKEN>'"
    )


def days_left(expires: str | None) -> int | None:
    """Verbleibende Gültigkeit in Tagen, oder None wenn unbekannt."""
    if not expires:
        return None
    try:
        return (date.fromisoformat(expires.strip()) - date.today()).days
    except ValueError:
        return None


def write_conf(path: Path, token: str, expires: str) -> None:
    """Token und Ablaufdatum in post_daily.conf ersetzen oder anhängen."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, seen = [], set()
    for line in lines:
        for key, value in (("IG_ACCESS_TOKEN", token), ("IG_TOKEN_EXPIRES", expires)):
            if line.startswith(f"export {key}="):
                out.append(f"export {key}={value}")
                seen.add(key)
                break
        else:
            out.append(line)
    for key, value in (("IG_ACCESS_TOKEN", token), ("IG_TOKEN_EXPIRES", expires)):
        if key not in seen:
            out.append(f"export {key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def ensure_token(api: str, token: str, expires: str | None, min_days: int,
                 conf: Path | None) -> str:
    """Verlängert das Token, wenn es bald abläuft. Gibt das gültige Token zurück.

    Instagram lässt eine Verlängerung erst zu, wenn das Token 24 Stunden alt
    ist, und nach Ablauf gar nicht mehr. Deshalb wird früh genug erneuert und
    nicht erst am letzten Tag.
    """
    left = days_left(expires)
    if left is not None and left > min_days:
        print(f"Token gültig, noch {left} Tage – keine Verlängerung nötig.")
        return token

    grund = "Ablaufdatum unbekannt" if left is None else f"nur noch {left} Tage"
    print(f"Token wird verlängert ({grund}).")
    res = refresh_token(api, token)
    new_token = res.get("access_token")
    if not new_token:
        raise GraphError(f"unerwartete Antwort beim Verlängern: {res}")
    neu = date.today() + timedelta(seconds=int(res.get("expires_in", 0)))
    print(f"Neues Token gültig bis {neu.isoformat()}.")
    if conf:
        write_conf(conf, new_token, neu.isoformat())
        print(f"In {conf} eingetragen.")
    return new_token


def refresh_token(api: str, token: str) -> dict:
    """Langlebiges Token um weitere 60 Tage verlängern.

    Geht erst, wenn das Token mindestens 24 Stunden alt ist. Nach 60 Tagen
    ohne Verlängerung ist es endgültig hinüber.
    """
    if api == "instagram":
        return _call("GET", f"{HOSTS['instagram']}/refresh_access_token",
                     {"grant_type": "ig_refresh_token", "access_token": token})
    raise GraphError(
        "Beim Facebook-Login laufen Seiten-Token, die aus einem langlebigen "
        "Nutzer-Token stammen, nicht ab – eine Verlängerung entfällt."
    )


# --------------------------------------------------------------------------- #
# Kommandozeile
# --------------------------------------------------------------------------- #


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", choices=list(HOSTS), default=os.environ.get("IG_API", "instagram"),
                    help="welcher Produktweg der Meta-App (Vorgabe: instagram)")
    ap.add_argument("--api-version", default=DEFAULT_API_VERSION)
    ap.add_argument("--ig-user-id", default=os.environ.get("IG_USER_ID"))
    ap.add_argument("--access-token", default=os.environ.get("IG_ACCESS_TOKEN"))

    ap.add_argument("--image-url", action="append", metavar="URL",
                    help="öffentlich erreichbare URL des JPEGs (kein lokaler Pfad!). "
                         "Mehrfach angeben ergibt einen Karussell-Beitrag; "
                         "die Reihenfolge ist die Reihenfolge im Beitrag.")
    caption = ap.add_mutually_exclusive_group()
    caption.add_argument("--caption", help="Bildtext direkt")
    caption.add_argument("--caption-file", type=Path, help="Bildtext aus Datei")
    ap.add_argument("--publish", action="store_true",
                    help="wirklich veröffentlichen (ohne dieses Flag nur Vorschau)")

    tools = ap.add_argument_group("Hilfsaufrufe (brauchen kein Bild)")
    tools.add_argument("--whoami", action="store_true", help="Konto-ID und Kontonamen zeigen")
    tools.add_argument("--exchange-token", metavar="KURZ_TOKEN",
                       help="kurzlebiges Token gegen ein 60-Tage-Token tauschen")
    tools.add_argument("--app-secret", default=os.environ.get("IG_APP_SECRET"),
                       help="App-Geheimnis, nur für --exchange-token")
    tools.add_argument("--refresh-token", action="store_true",
                       help="langlebiges Token um 60 Tage verlängern")
    tools.add_argument("--ensure-token", action="store_true",
                       help="Token nur verlängern, wenn es bald abläuft")
    tools.add_argument("--min-days", type=int, default=14,
                       help="ab wie wenigen Resttagen --ensure-token verlängert")
    tools.add_argument("--conf", type=Path,
                       help="Datei, in die das erneuerte Token geschrieben wird")
    tools.add_argument("--token-expires", default=os.environ.get("IG_TOKEN_EXPIRES"),
                       help="bekanntes Ablaufdatum, ISO-Format")
    args = ap.parse_args(argv)

    base = f"{HOSTS[args.api]}/{args.api_version}"

    # ---- Hilfsaufrufe --------------------------------------------------- #
    if args.ensure_token:
        if not args.access_token:
            print("IG_ACCESS_TOKEN fehlt (oder --access-token angeben).", file=sys.stderr)
            return 2
        try:
            token = ensure_token(args.api, args.access_token, args.token_expires,
                                 args.min_days, args.conf)
        except GraphError as exc:
            print(f"Instagram-API meldet: {exc}", file=sys.stderr)
            return 1
        # Letzte Zeile maschinenlesbar, damit post_daily.sh das Token
        # uebernehmen kann, ohne die ganze Konfiguration neu einzulesen.
        print(f"IG_ACCESS_TOKEN={token}")
        return 0

    if args.whoami or args.refresh_token or args.exchange_token:
        try:
            if args.exchange_token:
                if not args.app_secret:
                    print("--app-secret fehlt (oder IG_APP_SECRET setzen).", file=sys.stderr)
                    return 2
                res = exchange_token(args.api, args.exchange_token, args.app_secret)
                print(json.dumps(res, indent=2))
                print("\nDieses Token als IG_ACCESS_TOKEN in post_daily.conf eintragen.")
                return 0
            if not args.access_token:
                print("IG_ACCESS_TOKEN fehlt (oder --access-token angeben).", file=sys.stderr)
                return 2
            if args.refresh_token:
                print(json.dumps(refresh_token(args.api, args.access_token), indent=2))
                return 0
            res = whoami(args.api, base, args.access_token)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            if args.api == "instagram" and "user_id" in res:
                print(f"\nIG_USER_ID={res['user_id']}   (Konto @{res.get('username', '?')})")
            return 0
        except GraphError as exc:
            print(f"Instagram-API meldet: {exc}", file=sys.stderr)
            return 1

    # ---- Veröffentlichen ------------------------------------------------ #
    if not args.image_url or not (args.caption or args.caption_file):
        ap.error("--image-url und --caption/--caption-file werden zum Veröffentlichen gebraucht")

    text = args.caption if args.caption else args.caption_file.read_text(encoding="utf-8")
    text = text.strip()
    if len(text) > MAX_CAPTION:
        print(f"Warnung: Bildtext ist {len(text)} Zeichen lang, Instagram kürzt bei {MAX_CAPTION}.")

    urls: list[str] = args.image_url
    if len(urls) > MAX_CAROUSEL:
        print(f"Instagram nimmt höchstens {MAX_CAROUSEL} Bilder je Beitrag, "
              f"angegeben sind {len(urls)}.", file=sys.stderr)
        return 2

    if not args.publish:
        print("Vorschau (nichts gesendet – zum Veröffentlichen --publish angeben)\n")
        print(f"  Produktweg {args.api}")
        print(f"  Endpunkt   {base}/{args.ig_user_id or '<IG_USER_ID>'}/media")
        print(f"  Art        {'Karussell mit %d Bildern' % len(urls) if len(urls) > 1 else 'Einzelbild'}")
        for i, url in enumerate(urls, start=1):
            print(f"  Bild {i}     {url}")
        print(f"  Zeichen    {len(text)}")
        print("\n--- Bildtext ---")
        print(text)
        return 0

    if not args.ig_user_id or not args.access_token:
        print("IG_USER_ID und IG_ACCESS_TOKEN fehlen (Umgebungsvariablen oder Optionen).",
              file=sys.stderr)
        return 2

    try:
        used = quota_used(base, args.ig_user_id, args.access_token)
        if used:
            print(f"Kontingent: {used[0]} von {used[1]} Posts in den letzten 24 h verbraucht")

        if len(urls) == 1:
            print("Container anlegen …")
            container = create_container(base, args.ig_user_id, args.access_token,
                                         urls[0], text)
        else:
            children = []
            for i, url in enumerate(urls, start=1):
                child = create_child(base, args.ig_user_id, args.access_token, url)
                print(f"  Bild {i}/{len(urls)}: Container {child}")
                # Jedes Einzelbild muss fertig verarbeitet sein, bevor das
                # Karussell darauf verweisen darf.
                wait_ready(base, child, args.access_token)
                children.append(child)
            print("Karussell anlegen …")
            container = create_carousel(base, args.ig_user_id, args.access_token,
                                        children, text)
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
