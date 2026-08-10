# Auf Instagram veröffentlichen

Der Kanal heißt **wettergeschichte** und ist noch in Einrichtung (Stand
10. August 2026). Die Schritte dafür stehen unten in der Tabelle.

Kurze Antwort auf die Frage aus dem README: **Ja, das geht über eine API** –
aber nicht so bequem, wie man hoffen würde. Zwei Dinge machen Arbeit:

1. Der Kanal muss ein **Profi-Konto** (Business oder Creator) sein und über
   eine Facebook-Seite mit einer Meta-App verbunden werden.
2. Die API **lädt keine Datei hoch**. Sie holt sich das Bild von einer
   öffentlich erreichbaren URL. Man braucht also zusätzlich einen Ort, an dem
   die JPGs liegen.

Wenn beides einmal steht, ist das Posten selbst ein Dreizeiler und läuft
zuverlässig automatisiert – zum Beispiel jeden Morgen per `cron`.

## Was einmalig einzurichten ist

| Schritt | Was zu tun ist |
|---|---|
| 1 | Neues Instagram-Konto anlegen und in den Einstellungen auf **Profi-Konto** umstellen (Business oder Creator). |
| 2 | Eine **Facebook-Seite** anlegen und mit dem Instagram-Konto verknüpfen. Ohne Seite kein API-Zugang. |
| 3 | Auf [developers.facebook.com](https://developers.facebook.com) eine **App** anlegen (Typ „Business“) und das Produkt *Instagram* hinzufügen. |
| 4 | Berechtigungen anfordern: `instagram_business_basic` und `instagram_business_content_publish` (bei Anmeldung über Facebook: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`). |
| 5 | **Langlebiges Zugriffstoken** erzeugen (60 Tage gültig, davor verlängerbar) und die **Instagram-User-ID** notieren. |
| 6 | **App Review** bei Meta einreichen. Solange die App im Entwicklungsmodus ist, kann sie nur Konten bedienen, die eine Rolle in der App haben. Für den eigenen Kanal reicht das oft schon – ohne Review geht es nur nicht öffentlich für fremde Konten. Die Prüfung dauert erfahrungsgemäß zwei bis vier Wochen. |

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
ausgeliefert über GitHub Pages. `post_daily.sh` kopiert das fertige JPEG dorthin,
committet, pusht – und übergibt Instagram die URL

```
https://volkerreichenberger.github.io/wettergeschichtebilder/<name>.jpg
```

Das kostet nichts und braucht keinen Server. Der Pfad steht in
`post_daily.conf` (`BILDER=…`); liegt das Repository woanders, nur dort ändern.

Andere Wege wären ein S3-kompatibler Speicher (Cloudflare R2, Backblaze B2)
oder eigener Webspace per `scp` – Vorlagen dafür stehen in
`post_daily.conf.example`.

Die URL muss zum Zeitpunkt des Postens erreichbar sein. Danach kann das Bild
wieder verschwinden; Instagram hat es dann bereits kopiert. **Achtung:** Nach
dem Push braucht GitHub Pages typischerweise ein bis zwei Minuten, bis die
Datei ausgeliefert wird – `post_daily.sh` sollte also nicht unmittelbar nach
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

`post_daily.sh` macht die vier Schritte am Stück: Daten holen, Beitrag bauen,
Bild hochladen, veröffentlichen.

```bash
cp post_daily.conf.example post_daily.conf   # einmalig, dann ausfüllen
./post_daily.sh                              # Trockenlauf: baut alles, sendet nichts
./post_daily.sh --publish                    # wirklich veröffentlichen
./post_daily.sh --variante drei-tage --station 4928 --publish
```

Ohne `post_daily.conf` läuft nur der Trockenlauf – so lässt sich der ganze Weg
prüfen, bevor Zugangsdaten im Spiel sind. Der Trockenlauf zeigt am Ende den
fertigen Bildtext und die URL, unter der das Bild liegen müsste.

Als `--variante` stehen zur Wahl:

| Variante | Bild |
|---|---|
| `drei-tage` | die letzten drei Tage im Stundenverlauf |
| `nyt-3monate` | das letzte Quartal |
| `nyt-halbjahr` | bis Ende Juni das erste, danach das zweite Halbjahr |
| `nyt-h1` / `nyt-h2` | ein festes Halbjahr |
| `nyt-jahr` | das ganze Kalenderjahr |

`nyt-halbjahr` ist die Variante für den Automatikbetrieb: das noch nicht
begonnene Halbjahr wäre ein leeres Bild.

Nach dem Push wartet das Skript, bis GitHub Pages die Datei wirklich
ausliefert (bis zu fünf Minuten, einstellbar über `WAIT_SECONDS`). Kommt sie
nicht, bricht es vor dem Veröffentlichen ab, statt bei Instagram einen
fehlerhaften Container anzulegen.

```cron
# jeden Morgen um 8:15
15 8 * * *  cd ~/Programming/wettergeschichte && ./post_daily.sh --publish >> log/post.log 2>&1
```

Zwei Dinge dabei beachten:

* Das Zugriffstoken läuft nach 60 Tagen ab. Entweder rechtzeitig verlängern
  (`GET /refresh_access_token`) oder in den Kalender schreiben.
* Der DWD aktualisiert die `recent`-Dateien morgens; `fetch_dwd.py` erkennt am
  `Last-Modified`, ob sich überhaupt etwas geändert hat.

## Quellen

* [Content Publishing – Instagram Platform (Meta)](https://developers.facebook.com/docs/instagram-platform/content-publishing)
* [Graph API Changelog / Versionen](https://developers.facebook.com/docs/graph-api/changelog)
* [Instagram Graph API in 2026: Versions, Rate Limits & Content Publishing](https://www.netrows.com/blog/instagram-graph-api-guide-2026)
* [Post to Instagram via API: Guide (2026)](https://postproxy.dev/blog/post-to-instagram-via-api/)
