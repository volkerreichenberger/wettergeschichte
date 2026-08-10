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

# GitHub Pages baut nach einem Push erst neu; bis dahin liefert die URL 404.
# Instagram würde in dieser Zeit mit ERROR abbrechen, deshalb wird gewartet.
WAIT_SECONDS=300
WAIT_INTERVAL=10

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

warte_auf_bild() {
  # Pollt die öffentliche URL, bis sie 200 liefert. Rückgabe 1 bei Zeitablauf.
  local url="$1" start=$SECONDS code=""
  echo "-- warte, bis das Bild ausgeliefert wird (bis zu ${WAIT_SECONDS}s)"
  while [ $(( SECONDS - start )) -lt "$WAIT_SECONDS" ]; do
    code="$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 20 "$url" || true)"
    if [ "$code" = "200" ]; then
      echo "   erreichbar nach $(( SECONDS - start ))s"
      return 0
    fi
    sleep "$WAIT_INTERVAL"
  done
  echo "   nach ${WAIT_SECONDS}s immer noch nicht da (zuletzt HTTP ${code:-?})" >&2
  return 1
}

case "$VARIANTE" in
  serie)       BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum serie) ;;
  nyt-jahr)    BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum jahr) ;;
  nyt-quartal) BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum quartal) ;;
  nyt-3monate) BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum monate --months 3) ;;
  drei-tage)   BUILD=(plots/python/drei_tage_matplotlib.py) ;;
  *) echo "unbekannte Variante: $VARIANTE" >&2
     echo "möglich: serie nyt-jahr nyt-quartal nyt-3monate drei-tage" >&2; exit 2 ;;
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
  # Auch das Vorjahr: die Quartalsserie reicht bis zu drei Quartale zurück und
  # greift damit im ersten Halbjahr auf das Vorjahr zu.
  "$PYTHON" climatology.py --stations "$STATION"
  "$PYTHON" climatology.py --stations "$STATION" --year "$(( $(date +%Y) - 1 ))"
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

CAPTION="$POST_DIR/text.txt"
[ -f "$CAPTION" ] || { echo "text.txt fehlt in $POST_DIR" >&2; exit 1; }

# Einzelbild heißt bild.jpg, eine Serie bild_1.jpg … bild_n.jpg. Die
# Sortierung bestimmt die Reihenfolge im Karussell.
IMAGES=()
if [ -f "$POST_DIR/bild.jpg" ]; then
  IMAGES=("$POST_DIR/bild.jpg")
else
  while IFS= read -r f; do IMAGES+=("$f"); done < <(ls -1 "$POST_DIR"/bild_*.jpg 2>/dev/null | sort -V)
fi
# Unter 'set -u' bricht bash 3.2 an einem leeren Array ab, deshalb ${...[*]:-}.
[ -n "${IMAGES[*]:-}" ] || { echo "kein Bild in $POST_DIR" >&2; exit 1; }
echo "   ${#IMAGES[@]} Bild(er)"

# ---------------------------------------------------------------------------
# 3. Bild öffentlich ablegen
# ---------------------------------------------------------------------------
# Die Instagram-API lädt keine Datei hoch, sie holt sie von einer URL.
# WG_UPLOAD_CMD und WG_PUBLIC_URL kommen aus post_daily.conf; {src} und {name}
# werden ersetzt.
URLS=()
if [ -n "${WG_UPLOAD_CMD:-}" ] && [ -n "${WG_PUBLIC_URL:-}" ]; then
  echo "-- Bilder hochladen"
  for IMAGE in "${IMAGES[@]}"; do
    REMOTE_NAME="$(basename "$POST_DIR")_$(basename "$IMAGE")"
    CMD="${WG_UPLOAD_CMD//\{src\}/$IMAGE}"
    CMD="${CMD//\{name\}/$REMOTE_NAME}"
    URL="${WG_PUBLIC_URL//\{name\}/$REMOTE_NAME}"
    URLS+=("$URL")
    if [ "$UPLOAD" -eq 1 ]; then
      eval "$CMD"
      echo "   $REMOTE_NAME"
    else
      echo "   $REMOTE_NAME (Trockenlauf – nicht ausgeführt)"
    fi
  done
  # Erst nach dem letzten Push warten: GitHub Pages baut ohnehin alles auf
  # einmal, und geprüft wird das zuletzt hinzugefügte Bild.
  # ${URLS[-1]} gibt es erst ab bash 4.3; macOS liefert 3.2.
  LETZTE="${URLS[$(( ${#URLS[@]} - 1 ))]}"
  if [ "$UPLOAD" -eq 1 ] && ! warte_auf_bild "$LETZTE"; then
    # Ohne abrufbares Bild scheitert die Instagram-API ohnehin – dann lieber
    # hier abbrechen, als einen kaputten Container anzulegen.
    [ "$PUBLISH" -eq 1 ] && { echo "   Abbruch vor dem Veröffentlichen." >&2; exit 1; }
  fi
else
  for IMAGE in "${IMAGES[@]}"; do
    URLS+=("https://BITTE-NOCH-EINTRAGEN.example/$(basename "$IMAGE")")
  done
  echo "-- Kein Upload konfiguriert (WG_UPLOAD_CMD / WG_PUBLIC_URL fehlen)."
  if [ "$PUBLISH" -eq 1 ]; then
    echo "   Ohne öffentlich erreichbare Bild-URL kann nicht veröffentlicht werden." >&2
    exit 1
  fi
fi

if [ "$PUBLISH" -eq 0 ] && [ "$UPLOAD" -eq 1 ]; then
  echo "== Bilder hochgeladen, nicht veröffentlicht (--upload-only)"
fi

# ---------------------------------------------------------------------------
# 4. Veröffentlichen
# ---------------------------------------------------------------------------
echo "-- Instagram"
ARGS=(instagram_post.py --caption-file "$CAPTION")
for URL in "${URLS[@]}"; do ARGS+=(--image-url "$URL"); done
[ "$PUBLISH" -eq 1 ] && ARGS+=(--publish)
"$PYTHON" "${ARGS[@]}"

echo "== fertig: $POST_DIR"
