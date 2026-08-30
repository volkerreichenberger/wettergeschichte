# Auf Instagram veröffentlichen

Der Kanal heißt **wettergeschichte** und ist noch in Einrichtung (Stand
10. August 2026). Die Schritte dafür stehen unten in der Tabelle.

Kurze Antwort auf die Frage aus dem README: **Ja, das geht über eine API.**
Die einzige echte Unbequemlichkeit: die API **lädt keine Datei hoch**, sondern
holt sich das Bild von einer öffentlich erreichbaren URL. Man braucht also
zusätzlich einen Ort, an dem die JPGs liegen (siehe unten).

## Zwei Wege – dieses Projekt nimmt den Instagram-Login

Meta bietet die Veröffentlichungs-API in zwei Ausführungen an. Welche gilt,
entscheidet sich daran, welches Produkt in der Meta-App eingerichtet ist:

| | **Instagram-Login** (hier verwendet) | Facebook-Login |
|---|---|---|
| Server | `graph.instagram.com` | `graph.facebook.com` |
| Facebook-Seite | **nicht nötig** | nötig |
| Berechtigungen | `instagram_business_basic`, `instagram_business_content_publish` | `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` |
| Token | Instagram-Nutzer-Token | Seiten- oder Nutzer-Token |
| Schalter im Skript | `--api instagram` (Vorgabe) | `--api facebook` |

Der Instagram-Login ist für einen einzelnen eigenen Kanal der schlankere Weg.
Wer im Graph API Explorer ein *Seiten-Zugriffstoken* anfordert und
**„Invalid platform app“** zu sehen bekommt, ist genau in diesem Punkt falsch
abgebogen: Seiten-Token gibt es nur beim Facebook-Login.

## Was einmalig einzurichten ist

| Schritt | Was zu tun ist |
|---|---|
| 1 | Instagram-Konto auf **Profi-Konto** umstellen: *Einstellungen und Privatsphäre → Kontoart und Tools → Zu professionellem Konto wechseln*. Kostet nichts und verlangt keine Werbung. |
| 2 | Auf [developers.facebook.com](https://developers.facebook.com) eine **App** anlegen und das Produkt *Instagram* mit **Instagram-Login** hinzufügen. |
| 3 | Berechtigungen anfordern: `instagram_business_basic` und `instagram_business_content_publish`. |
| 4 | Im Graph API Explorer den blauen Knopf **„Generate Instagram Access Token“** drücken – *nicht* „Seiten-Zugriffstoken anfordern“. |
| 5 | Konto-ID auslesen und Token verlängern (beides kann `instagram_post.py`, siehe unten). |
| 6 | **App Review** nur nötig, um fremde Konten zu bedienen. Für den eigenen Kanal reicht der Entwicklungsmodus, solange das Konto eine Rolle in der App hat. |

### Konto-ID und langlebiges Token

```bash
export IG_ACCESS_TOKEN=IGAA...          # Token aus dem Dashboard

python instagram_post.py --whoami
# -> IG_USER_ID=17841439243436075   (Konto @wettergeschichte)
```

Zwei Fallstricke:

* Die gesuchte Zahl steht in **`user_id`**, nicht in `id`. Letzteres ist eine
  app-bezogene Kennung und funktioniert nicht als `IG_USER_ID`.
* **Das im Dashboard erzeugte Token ist bereits langlebig** (60 Tage). Ein
  Tausch über `--exchange-token` scheitert deshalb mit „Session key invalid" –
  es gibt nichts zu tauschen. Verlängert wird mit `--refresh-token`.

### Das Token läuft nicht ab

`post_daily.py` prüft bei jedem Lauf, wie lange das Token noch gilt, und
verlängert es, sobald weniger als 14 Tage bleiben (`TOKEN_MIN_DAYS`). Das neue
Token und sein Ablaufdatum schreibt es selbst in `post_daily.conf`.

Das muss automatisch geschehen: Instagram verlängert nur Token, die mindestens
24 Stunden alt sind und **noch nicht abgelaufen** sind. Ist die Frist einmal
verstrichen, hilft nur der Weg über das Dashboard von Hand.

## Was die API vom Bild verlangt

* **Nur JPEG.** Deshalb schreibt `plots/python/instagram_card.py` `.jpg` und
  nicht `.png`.
* **Öffentlich erreichbare URL**, kein Datei-Upload und kein `localhost`.
* **Bildtext maximal 2200 Zeichen**, höchstens 30 Hashtags.
* **100 API-Posts je Konto in 24 Stunden.** Für eine Grafik am Tag reichlich.

Für das Format: das breite 16:9-Diagramm wird im Feed winzig dargestellt.
`instagram_card.py` erzeugt deshalb eine eigene Fassung im Hochformat
1080 × 1350 (4:5) – das ist das größte Format, das Instagram im Feed zulässt.

## Wo die Bilder liegen

In diesem Projekt: im eigenen Repository
[wettergeschichtebilder](https://github.com/volkerreichenberger/wettergeschichtebilder),
ausgeliefert über GitHub Pages. `post_daily.py` kopiert das fertige JPEG dorthin,
committet, pusht – und übergibt Instagram die URL

```
https://volkerreichenberger.github.io/wettergeschichtebilder/2026/06/14/<name>.jpg
```

Die Bilder liegen nach Tagen sortiert, `JJJJ/MM/TT`, nach dem Tag des Laufs.
Ohne diese Aufteilung stünden nach einem Jahr rund 1500 Dateien nebeneinander
in einem Verzeichnis. Das Tagesverzeichnis legt `post_daily.py` vor dem
Kopieren selbst an, weil `cp` das nicht tut; in `WG_PUBLIC_URL` steckt es
bereits in `{name}`, dort ist deshalb nichts zu ändern.

Das kostet nichts und braucht keinen Server. Der Pfad steht in
`post_daily.conf` (`BILDER=…`); liegt das Repository woanders, nur dort ändern.

Andere Wege wären ein S3-kompatibler Speicher (Cloudflare R2, Backblaze B2)
oder eigener Webspace per `scp` – Vorlagen dafür stehen in
`post_daily.conf.example`.

Die URL muss zum Zeitpunkt des Postens erreichbar sein. Danach kann das Bild
wieder verschwinden; Instagram hat es dann bereits kopiert. **Achtung:** Nach
dem Push braucht GitHub Pages typischerweise ein bis zwei Minuten, bis die
Datei ausgeliefert wird – `post_daily.py` sollte also nicht unmittelbar nach
dem Upload veröffentlichen. Falls Instagram `ERROR` meldet, ist das die erste
Ursache, die zu prüfen ist.

## Der eigentliche Post

Die Beitragsskripte legen je Beitrag einen Ordner unter `posts/` an, der Bild
und Begleittext enthält:

```
posts/nyt_h1_04931_2026-08-09/bild.jpg
posts/nyt_h1_04931_2026-08-09/text.txt
```

```bash
# 1. Beitrag erzeugen
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum h1
POST=posts/nyt_h1_04931_2026-08-09

# 2. bild.jpg irgendwo öffentlich ablegen (hier beispielhaft per scp)
scp $POST/bild.jpg web:/var/www/wetter/nyt_h1_04931.jpg

# 3. Vorschau – zeigt nur, was gesendet würde
python instagram_post.py \
    --image-url https://example.org/wetter/nyt_h1_04931.jpg \
    --caption-file $POST/text.txt

# 4. wirklich veröffentlichen
export IG_USER_ID=17841400000000000
export IG_ACCESS_TOKEN=EAAG...
python instagram_post.py \
    --image-url https://example.org/wetter/nyt_h1_04931.jpg \
    --caption-file $POST/text.txt \
    --publish
```

`instagram_post.py` macht dabei genau die drei Aufrufe der Content Publishing
API: Container anlegen, auf `status_code = FINISHED` warten, veröffentlichen.
Ohne `--publish` passiert nichts – es wird nur angezeigt, was gesendet würde.

## Täglich automatisch

`post_daily.py` macht die vier Schritte am Stück: Daten holen, Beitrag bauen,
Bild hochladen, veröffentlichen.

```bash
cp post_daily.conf.example post_daily.conf   # einmalig, dann ausfüllen
./post_daily.py                              # Trockenlauf: baut alles, sendet nichts
./post_daily.py --publish                    # wirklich veröffentlichen
./post_daily.py --variante drei-tage --station 4928 --publish
```

Ohne `post_daily.conf` läuft nur der Trockenlauf – so lässt sich der ganze Weg
prüfen, bevor Zugangsdaten im Spiel sind. Der Trockenlauf zeigt am Ende den
fertigen Bildtext und die URL, unter der das Bild liegen müsste.

`VARIANTE` in `post_daily.conf` darf **mehrere** Werte enthalten, durch
Leerzeichen getrennt – dann entsteht je Variante ein eigener Beitrag:

```bash
VARIANTE="serie drei-tage"
```

Auf der Kommandozeile geht dasselbe: `--variante "serie drei-tage"`. Daten und
Token werden dabei nur einmal geholt, gebaut und veröffentlicht wird je
Variante. Scheitert eine, laufen die übrigen trotzdem durch; das Skript endet
dann mit Rückgabewert 1.

Zur Wahl stehen:

| Variante | Beitrag |
|---|---|
| `serie` | Karussell: Ganzjahresbild, die vier jüngsten Quartale, Legende |
| `bewoelkung` | einmal im Monat: Bewölkungskalender des Vormonats und der fünf Vorjahre, dazu ein Streifenbild über neun Jahre |
| `drei-tage` | die letzten drei Tage im Stundenverlauf |
| `nyt-quartal` | nur das laufende Quartal |
| `nyt-3monate` | die letzten drei Monate, gleitend |
| `nyt-jahr` | das ganze Kalenderjahr |

### Die Bewölkung – einmal im Monat

`bewoelkung` läuft täglich mit, tut aber fast immer nichts: Das Skript baut den
Beitrag erst, wenn der Vormonat vollständig vorliegt, und überspringt ihn, wenn
der Ordner schon existiert. In beiden Fällen endet es mit Rückgabewert 3, den
`post_daily.py` als „nichts zu tun“ und nicht als Fehler wertet.

Zwei Besonderheiten:

* **Andere Station.** Der Bedeckungsgrad kommt von **4928 Schnarrenberg**,
  nicht von 4931 – dort fehlt er von Juni 2022 bis August 2023 vollständig.
  `post_daily.py` holt deshalb die Daten beider Stationen und gibt jeder
  Variante die passende mit (`BEWOELKUNG_STATION`).
* **Nachträglich.** `--monat 2026-01` baut einen beliebigen Monat, `--force`
  auch dann, wenn es den Ordner schon gibt.
* **Toleranz.** Bis zu zwei fehlende Tage im Monat sind erlaubt; sie bleiben im
  Bild leer und werden im Begleittext benannt. Ohne diese Toleranz würde ein
  einzelner Messausfall den Monatsbeitrag für immer blockieren.

### Die Serie

`serie` erzeugt sechs Bilder in einem Ordner und veröffentlicht sie als
**Karussell-Beitrag**:

1. das laufende Kalenderjahr
2.–5. die vier jüngsten Quartale, das laufende zuletzt
6. die Legende

Die Quartale sind starr am Kalender ausgerichtet (Jan–Mär, Apr–Jun, Jul–Sep,
Okt–Dez). Am 1. April springt die Scheibe um und zeigt zunächst nur einen Tag –
dafür sind die Bilder untereinander vergleichbar. Die drei Vorgänger reichen im
ersten Halbjahr ins Vorjahr zurück; `post_daily.py` leitet die Kennzahlen
deshalb für das laufende **und** das vorige Jahr ab.

Zwei Dinge, die die Serie erst ehrlich machen:

* **Alle sechs Bilder teilen sich eine Temperaturskala.** Mit je eigener Skala
  sähe ein kühles Quartal beim Wischen aus wie ein heißes.
* **Kein Legendenkasten in den Diagrammen.** Er würde je nach Jahreszeit genau
  die Tage verdecken, um die es geht; stattdessen steht die Legende als eigenes
  Schlussbild und zusätzlich ausformuliert im Bildtext.

Nach dem Push wartet das Skript, bis GitHub Pages die Datei wirklich
ausliefert (bis zu fünf Minuten, einstellbar über `WAIT_SECONDS`). Kommt sie
nicht, bricht es vor dem Veröffentlichen ab, statt bei Instagram einen
fehlerhaften Container anzulegen.

```cron
# jeden Morgen um 11 Uhr – der DWD liefert die Vortagsdaten gegen 9 Uhr
0 11 * * *  cd ~/Programming/wettergeschichte && ./post_daily.py --publish >> log/post.log 2>&1
```

Zwei Dinge dabei beachten:

* Das Zugriffstoken läuft nach 60 Tagen ab. `post_daily.py` verlängert es
  selbsttätig, sobald weniger als 14 Tage Restlaufzeit bleiben, und schreibt
  das neue in `post_daily.conf` zurück — die Datei muss für den cron-Benutzer
  also schreibbar sein.
* Der DWD aktualisiert die `recent`-Dateien morgens; `fetch_dwd.py` erkennt am
  `Last-Modified`, ob sich überhaupt etwas geändert hat.

## Quellen

* [Content Publishing – Instagram Platform (Meta)](https://developers.facebook.com/docs/instagram-platform/content-publishing)
* [Graph API Changelog / Versionen](https://developers.facebook.com/docs/graph-api/changelog)
* [Instagram Graph API in 2026: Versions, Rate Limits & Content Publishing](https://www.netrows.com/blog/instagram-graph-api-guide-2026)
* [Post to Instagram via API: Guide (2026)](https://postproxy.dev/blog/post-to-instagram-via-api/)
