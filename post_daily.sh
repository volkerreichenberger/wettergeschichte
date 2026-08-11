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
STAND=""     # Stichtag: Beitrag so bauen, wie er an dem Tag ausgesehen haette

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
    --stand)      STAND="$2"; shift ;;
    --variante)   VARIANTE="$2"; shift ;;
    -h|--help)    sed -n '2,15p' "$0"; exit 0 ;;
    *)            echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

warte_auf_bild() {
  # Pollt die öffentliche URL, bis sie 200 liefert *und* die ausgelieferte
  # Datei so groß ist wie die lokale. Der Größenvergleich ist nötig, weil ein
  # ersetztes Bild unter gleichem Namen sofort 200 liefert – aber noch mit dem
  # alten Inhalt, den Instagram dann holen würde.
  local url="$1" datei="$2" start=$SECONDS code="" ferne="" lokal=""
  lokal="$(wc -c < "$datei" | tr -d ' ')"
  echo "-- warte, bis das Bild ausgeliefert wird (bis zu ${WAIT_SECONDS}s)"
  while [ $(( SECONDS - start )) -lt "$WAIT_SECONDS" ]; do
    read -r code ferne <<<"$(curl -s -o /dev/null -w '%{http_code} %{size_download}' \
                             -L --max-time 30 "$url" || echo "000 0")"
    if [ "$code" = "200" ] && [ "$ferne" = "$lokal" ]; then
      echo "   erreichbar nach $(( SECONDS - start ))s"
      return 0
    fi
    sleep "$WAIT_INTERVAL"
  done
  echo "   nach ${WAIT_SECONDS}s nicht in der erwarteten Fassung da " \
       "(HTTP ${code:-?}, ${ferne:-?} statt ${lokal} Bytes)" >&2
  return 1
}

# VARIANTE darf mehrere Werte enthalten, durch Leerzeichen getrennt – dann
# entsteht je Variante ein eigener Beitrag. Erst alle prüfen, damit ein Tippfehler
# nicht auffällt, nachdem der erste Beitrag schon veröffentlicht ist.
setze_build() {
  case "$1" in
    serie)       BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum serie) ;;
    nyt-jahr)    BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum jahr) ;;
    nyt-quartal) BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum quartal) ;;
    nyt-3monate) BUILD=(plots/python/nyt_post_matplotlib.py --zeitraum monate --months 3) ;;
    drei-tage)   BUILD=(plots/python/drei_tage_matplotlib.py) ;;
    *) echo "unbekannte Variante: $1" >&2
       echo "möglich: serie nyt-jahr nyt-quartal nyt-3monate drei-tage" >&2; return 2 ;;
  esac
}
for VAR in $VARIANTE; do setze_build "$VAR" || exit 2; done

echo "== Wettergeschichte, Station $STATION${STAND:+, Stand $STAND}"
echo "   Varianten: $VARIANTE"

# ---------------------------------------------------------------------------
# 0. Token prüfen und bei Bedarf verlängern
# ---------------------------------------------------------------------------
# Das Instagram-Token gilt 60 Tage. Läuft es ab, steht der Cronjob still, und
# neu erzeugen ginge nur von Hand im Dashboard. Deshalb rechtzeitig erneuern –
# Instagram lässt das erst ab 24 Stunden Alter zu, nach Ablauf gar nicht mehr.
if [ -n "${IG_ACCESS_TOKEN:-}" ]; then
  echo "-- Zugriffstoken"
  TOKEN_OUT="$("$PYTHON" instagram_post.py --ensure-token --conf post_daily.conf \
               --min-days "${TOKEN_MIN_DAYS:-14}" || true)"
  echo "$TOKEN_OUT" | grep -v '^IG_ACCESS_TOKEN=' | sed 's/^/   /'
  NEW_TOKEN="$(printf '%s\n' "$TOKEN_OUT" | sed -n 's/^IG_ACCESS_TOKEN=//p' | tail -1)"
  if [ -n "$NEW_TOKEN" ]; then
    export IG_ACCESS_TOKEN="$NEW_TOKEN"
  elif [ "$PUBLISH" -eq 1 ]; then
    echo "   Token konnte nicht geprüft werden – Abbruch." >&2
    exit 1
  fi
fi

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

FEHLER=0
for VAR in $VARIANTE; do
setze_build "$VAR"

# ---------------------------------------------------------------------------
# 2. Beitrag bauen
# ---------------------------------------------------------------------------
printf '\n-- Beitrag bauen: %s\n' "$VAR"
BUILD_ARGS=(--station "$STATION")
[ -n "$STAND" ] && BUILD_ARGS+=(--stand "$STAND")
BUILD_OUT="$("$PYTHON" "${BUILD[@]}" "${BUILD_ARGS[@]}")"
echo "$BUILD_OUT"

POST_DIR="$(printf '%s\n' "$BUILD_OUT" | sed -n 's/^POST_DIR=//p' | tail -1)"
if [ -z "$POST_DIR" ] || [ ! -d "$POST_DIR" ]; then
  echo "   Beitragsordner nicht gefunden – $VAR übersprungen." >&2
  FEHLER=1; continue
fi

CAPTION="$POST_DIR/text.txt"
[ -f "$CAPTION" ] || { echo "   text.txt fehlt in $POST_DIR" >&2; FEHLER=1; continue; }

# Einzelbild heißt bild.jpg, eine Serie bild_1.jpg … bild_n.jpg. Die
# Sortierung bestimmt die Reihenfolge im Karussell.
IMAGES=()
if [ -f "$POST_DIR/bild.jpg" ]; then
  IMAGES=("$POST_DIR/bild.jpg")
else
  while IFS= read -r f; do IMAGES+=("$f"); done < <(ls -1 "$POST_DIR"/bild_*.jpg 2>/dev/null | sort -V)
fi
# Unter 'set -u' bricht bash 3.2 an einem leeren Array ab, deshalb ${...[*]:-}.
[ -n "${IMAGES[*]:-}" ] || { echo "   kein Bild in $POST_DIR" >&2; FEHLER=1; continue; }
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
  LETZTE_DATEI="${IMAGES[$(( ${#IMAGES[@]} - 1 ))]}"
  if [ "$UPLOAD" -eq 1 ] && ! warte_auf_bild "$LETZTE" "$LETZTE_DATEI"; then
    # Ohne abrufbares Bild scheitert die Instagram-API ohnehin – dann lieber
    # hier abbrechen, als einen kaputten Container anzulegen.
    if [ "$PUBLISH" -eq 1 ]; then
      echo "   $VAR nicht veröffentlicht – Bild nicht abrufbar." >&2
      FEHLER=1; continue
    fi
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
done

exit "$FEHLER"
