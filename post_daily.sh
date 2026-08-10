#!/usr/bin/env bash
#
# Täglicher Ablauf: Daten holen, Beitrag bauen, Bild hochladen, veröffentlichen.
#
#   ./post_daily.sh                          Trockenlauf (baut alles, sendet nichts)
#   ./post_daily.sh --publish                wirklich veröffentlichen
#   ./post_daily.sh --variante nyt-h1        andere Grafik
#   ./post_daily.sh --station 4928 --publish
#
# Einstellungen kommen aus post_daily.conf (siehe post_daily.conf.example).
# Ohne diese Datei läuft nur der Trockenlauf – das ist Absicht: so lässt sich
# der ganze Weg testen, bevor Zugangsdaten im Spiel sind.

set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
STATION=4931
VARIANTE="nyt-h1"
UPLOAD=0     # Bild wirklich hochladen
PUBLISH=0    # Beitrag wirklich veröffentlichen
SKIP_FETCH=0

# ---------------------------------------------------------------------------
# Einstellungen
# ---------------------------------------------------------------------------
# shellcheck source=/dev/null
[ -f post_daily.conf ] && . ./post_daily.conf

while [ $# -gt 0 ]; do
  case "$1" in
    --publish)     UPLOAD=1; PUBLISH=1 ;;
    --upload-only) UPLOAD=1 ;;   # Bildablage testen, ohne zu veröffentlichen
    --skip-fetch)  SKIP_FETCH=1 ;;
    --station)    STATION="$2"; shift ;;
    --variante)   VARIANTE="$2"; shift ;;
    -h|--help)    sed -n '2,15p' "$0"; exit 0 ;;
    *)            echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

case "$VARIANTE" in
  nyt-jahr)    BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum jahr) ;;
  nyt-h1)      BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum h1) ;;
  nyt-h2)      BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum h2) ;;
  nyt-3monate) BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum monate --months 3) ;;
  drei-tage)   BUILD=(plots/python/drei_tage_matplotlib.py) ;;
  *) echo "unbekannte Variante: $VARIANTE" >&2
     echo "möglich: nyt-jahr nyt-h1 nyt-h2 nyt-3monate drei-tage" >&2; exit 2 ;;
esac

echo "== Wettergeschichte, Variante $VARIANTE, Station $STATION"

# ---------------------------------------------------------------------------
# 1. Daten aktualisieren
# ---------------------------------------------------------------------------
if [ "$SKIP_FETCH" -eq 0 ]; then
  echo "-- Daten holen"
  "$PYTHON" fetch_dwd.py --stations "$STATION"
  "$PYTHON" fetch_hourly.py --stations "$STATION"
  echo "-- Kennzahlen ableiten"
  "$PYTHON" climatology.py --stations "$STATION"
else
  echo "-- Daten übersprungen (--skip-fetch)"
fi

# ---------------------------------------------------------------------------
# 2. Beitrag bauen
# ---------------------------------------------------------------------------
echo "-- Beitrag bauen"
BUILD_OUT="$("$PYTHON" "${BUILD[@]}" --station "$STATION")"
echo "$BUILD_OUT"

POST_DIR="$(printf '%s\n' "$BUILD_OUT" | sed -n 's/^POST_DIR=//p' | tail -1)"
if [ -z "$POST_DIR" ] || [ ! -d "$POST_DIR" ]; then
  echo "Beitragsordner nicht gefunden – Abbruch." >&2
  exit 1
fi

IMAGE="$POST_DIR/bild.jpg"
CAPTION="$POST_DIR/text.txt"
REMOTE_NAME="$(basename "$POST_DIR").jpg"
[ -f "$IMAGE" ] && [ -f "$CAPTION" ] || { echo "Bild oder Text fehlt in $POST_DIR" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 3. Bild öffentlich ablegen
# ---------------------------------------------------------------------------
# Die Instagram-API lädt keine Datei hoch, sie holt sie von einer URL.
# WG_UPLOAD_CMD und WG_PUBLIC_URL kommen aus post_daily.conf; {src} und {name}
# werden ersetzt.
if [ -n "${WG_UPLOAD_CMD:-}" ] && [ -n "${WG_PUBLIC_URL:-}" ]; then
  CMD="${WG_UPLOAD_CMD//\{src\}/$IMAGE}"
  CMD="${CMD//\{name\}/$REMOTE_NAME}"
  URL="${WG_PUBLIC_URL//\{name\}/$REMOTE_NAME}"
  echo "-- Bild hochladen: $CMD"
  if [ "$UPLOAD" -eq 1 ]; then
    eval "$CMD"
    echo "   liegt unter $URL"
  else
    echo "   (Trockenlauf – nicht ausgeführt)"
  fi
else
  URL="https://BITTE-NOCH-EINTRAGEN.example/$REMOTE_NAME"
  echo "-- Kein Upload konfiguriert (WG_UPLOAD_CMD / WG_PUBLIC_URL fehlen)."
  if [ "$PUBLISH" -eq 1 ]; then
    echo "   Ohne öffentlich erreichbare Bild-URL kann nicht veröffentlicht werden." >&2
    exit 1
  fi
fi

if [ "$PUBLISH" -eq 0 ] && [ "$UPLOAD" -eq 1 ]; then
  echo "== Bild hochgeladen, nicht veröffentlicht (--upload-only)"
fi

# ---------------------------------------------------------------------------
# 4. Veröffentlichen
# ---------------------------------------------------------------------------
echo "-- Instagram"
ARGS=(instagram_post.py --image-url "$URL" --caption-file "$CAPTION")
[ "$PUBLISH" -eq 1 ] && ARGS+=(--publish)
"$PYTHON" "${ARGS[@]}"

echo "== fertig: $POST_DIR"
