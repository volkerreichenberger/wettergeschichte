# Wettergeschichte

Grafische Auswertung von Wetterdaten des Deutschen Wetterdienstes für die
beiden Stuttgarter Stationen im Stil des klassischen
[New-York-Times-Wetterdiagramms](https://graphics8.nytimes.com/images/2016/02/19/multimedia/oakImage-1455906157517/oakImage-1455906157517-superJumbo.png).

| Station | Name | Höhe | Daten seit | |
|---|---|---|---|---|
| 4931 | Stuttgart-Echterdingen | 371 m | 1953 | **wird auf Instagram gezeigt**, dort als „Stuttgart (Süd)" |
| 4928 | Stuttgart (Schnarrenberg) | 314 m | 1958 | nur für Vergleiche, hat als einzige Strahlungsdaten |

---

# Der tägliche Ablauf

**Ein Befehl macht alles:**

```bash
cd ~/Programming/wettergeschichte
./post_daily.py --publish
```

Der Reihe nach: Token prüfen und bei Bedarf verlängern → Daten beim DWD
holen → Kennzahlen ableiten → beide Beiträge bauen → Bilder in die
Bildablage schieben → auf Instagram veröffentlichen.

**Nicht vor 9:15 Uhr laufen lassen.** Der DWD schiebt die Daten des Vortags
morgens gegen 8:40 bis 9:00 Uhr nach. Wer früher startet, baut den Beitrag mit
vorgestrigen Zahlen — das Skript merkt das nicht, weil es keine Lücke gibt,
sondern nur einen Tag weniger.

### Wenn du es Schritt für Schritt willst

```bash
# 1. Daten holen (macht nichts, wenn der DWD nichts Neues hat)
python3 fetch_dwd.py --stations 4931
python3 fetch_hourly.py --stations 4931

# 2. Ist gestern schon dabei? Letzte Spalte lesen.
python3 fetch_dwd.py --status
python3 fetch_hourly.py --status

# 3. Trockenlauf: baut die Bilder, zeigt den Bildtext, sendet nichts
./post_daily.py --skip-fetch

# 4. Wenn es passt, wirklich veröffentlichen
./post_daily.py --skip-fetch --publish
```

`--status` geht nicht ins Netz, es liest nur den lokalen Bestand. Steht dort
noch das vorgestrige Datum, hat der DWD schlicht noch nicht aktualisiert —
dann eine halbe Stunde warten und Schritt 1 wiederholen.

### Was dabei entsteht

Zwei Beiträge, festgelegt über `VARIANTE` in `post_daily.conf`:

| Variante | Beitrag | wie oft |
|---|---|---|
| `serie` | Karussell aus sechs Bildern: das Kalenderjahr, die vier jüngsten Quartale, die Legende | täglich |
| `drei-tage` | die letzten drei Tage im Stundenverlauf, dahinter dieselben Tage der fünf Vorjahre | täglich |
| `bewoelkung` | Bewölkungskalender des Vormonats und der fünf Vorjahre, dazu ein Streifenbild über neun Jahre | einmal im Monat |

`bewoelkung` läuft täglich mit, tut aber fast immer nichts: Der Beitrag entsteht
erst, wenn der Vormonat vollständig vorliegt, und wird übersprungen, sobald es
ihn gibt. Er kommt außerdem von **Station 4928 Schnarrenberg** — an 4931 fehlt
der Bedeckungsgrad von Juni 2022 bis August 2023. `post_daily.py` holt deshalb
die Daten beider Stationen.

Jeder Beitrag landet als eigener Ordner unter `posts/` mit `bild.jpg`
(beziehungsweise `bild_1.jpg` … `bild_6.jpg`) und `text.txt`.

**Achtung bei Handänderungen am Bildtext:** Jeder Lauf von `post_daily.py`
baut Bild *und* `text.txt` neu und überschreibt sie. Wer den Text vor dem
Veröffentlichen anpassen will, geht deshalb am Skript vorbei — die Bilder
liegen nach Schritt 3 ja schon hochgeladen bereit:

```bash
POST=posts/drei_tage_04931_2026-08-10
$EDITOR $POST/text.txt
set -a; . ./post_daily.conf; set +a
python3 instagram_post.py --caption-file $POST/text.txt \
    --image-url https://volkerreichenberger.github.io/wettergeschichtebilder/$(basename $POST)_bild.jpg \
    --publish
```

### Wenn etwas schiefgeht

| Meldung | Bedeutung |
|---|---|
| `unverändert` beim Holen | Der DWD hat nichts Neues. Kein Fehler. |
| `nach 300s nicht in der erwarteten Fassung da` | GitHub Pages liefert das Bild noch nicht aus. Später erneut versuchen; veröffentlicht wird in dem Fall nichts. |
| `Token wird verlängert` | Normalbetrieb, passiert unter 14 Resttagen automatisch. |
| `Session key invalid` beim Token | Das Token ist abgelaufen. Neu erzeugen im Meta-Dashboard, siehe [INSTAGRAM.md](INSTAGRAM.md). |

Automatisch täglich:

```cron
15 9 * * *  cd ~/Programming/wettergeschichte && ./post_daily.py --publish >> log/post.log 2>&1
```

---

## Alles neu zeichnen, zum Vergleichen

Neben den Instagram-Beiträgen gibt es die Werkstatt: `run_all.py` baut jede
Variante in jeder Bibliothek, für beide Stationen, nach `output/`.

```bash
python3 run_all.py                                  # alles
python3 run_all.py --skip-fetch --only matplotlib   # nur neu zeichnen
python3 climatology.py --year 2026                  # nur Kennzahlen ableiten
```

Gebraucht werden Python (pandas, numpy, matplotlib; für einzelne Varianten
zusätzlich plotnine, plotly + kaleido) und R (ggplot2, patchwork, lattice,
ragg). Fehlt ein Paket, schlägt nur die betreffende Variante fehl, der Rest
läuft weiter.

## Aufbau

```
post_daily.py       der tägliche Ablauf, siehe oben
post_daily.conf     Station, Varianten, Bildablage, Zugangsdaten (nicht im Repo)
fetch_dwd.py        holt die DWD-Tageswerte, inkrementell
fetch_hourly.py     holt die stündlichen Lufttemperaturen
dwd_datasets.py     Katalog der Datensätze und Spaltennamen
climatology.py      leitet Normalen, Rekorde und Jahreswerte ab
instagram_post.py   veröffentlicht Bild und Text über die Instagram-API
run_all.py          baut alle Varianten zum Vergleichen
plots/python/       matplotlib, plotnine, plotly
plots/R/            ggplot2, lattice, base graphics
data/               Rohdaten, aufbereitete CSVs, abgeleitete Kennzahlen
posts/              je Beitrag ein Ordner mit Bild und Begleittext
output/             die Vergleichsbilder aus run_all.py
```

## Die Daten

`fetch_dwd.py` lädt alle Tagesdatensätze, die der DWD für die beiden Stationen
anbietet und die mindestens zehn Jahre abdecken:

| Datensatz | Inhalt | 4928 | 4931 |
|---|---|---|---|
| `kl` | Temperatur, Niederschlag, Wind, Sonne, Druck, Feuchte, Bedeckung, Schnee | 1958– | 1953– |
| `more_precip` | Niederschlag und Neuschnee des Niederschlagsmessnetzes | 1958– | 1953– |
| `soil_temperature` | Erdbodentemperatur in 2 bis 50 cm Tiefe | 1977– | 1995– |
| `solar` | Global-, Diffus- und Gegenstrahlung | 1979– | — |
| `weather_phenomena` | Nebel, Gewitter, Sturm, Tau, Reif, Graupel, Hagel | 1958–2000 | 1953–2022 |
| `more_weather_phenomena` | dieselben Erscheinungen im Niederschlagsmessnetz | 1960–2000 | 1960–2022 |
| `water_equiv` | Schneehöhe und Wasseräquivalent der Schneedecke | 1985–1999 | 1953–2015 |

Insgesamt 42 Messgrößen; `data/data_dictionary.csv` erklärt jede Spalte mit
Einheit. Die drei letzten Datensätze führt der DWD an diesen Stationen nicht
mehr fort – sie sind trotzdem dabei, weil sie lange Reihen liefern.

**Inkrementell** heißt hier: vor jedem Download wird das Verzeichnislisting
gelesen und Dateiname, Größe und `Last-Modified` gegen
`data/raw/manifest.json` geprüft. Unveränderte Dateien werden übersprungen.
Ein Lauf ohne Neuerungen dauert rund sechs Sekunden und überträgt nur die
Listings. Kommen neue Tage dazu, werden sie in die bestehenden CSVs
eingemischt; für Tage, die in `historical` **und** `recent` vorkommen, gewinnt
`historical` – das sind die endgültig geprüften Werte.

Ergebnis je Station:

```
data/stations/04931/kl.csv          eine CSV je Datensatz
data/stations/04931/daily.csv       alle Datensätze auf das Datum gejoint
```

### Was in den Daten auffällt

Beides sind echte Eigenheiten der Messreihen, keine Fehler der Skripte:

* **4931** hat die Sonnenscheindauer im Juli 2023 eingestellt; ab dann steht
  in `sunshine_h` nichts mehr. Für Sonnenschein ist 4928 die Station der Wahl.
* **4931** fehlen 78 Tage aus dem Jahr 2023 vollständig, **4928** acht Tage
  aus dem Jahr 2000.
* **Strahlungsdaten** (`solar`) gibt es nur für 4928, und sie hinken den
  übrigen Messwerten rund vier Wochen hinterher.

## Die Grafiken

Alle Varianten lesen dieselben abgeleiteten CSVs aus `data/derived/` und
benutzen dieselbe Palette – die Bilder unterscheiden sich also nur in der
Umsetzung, nicht in den Zahlen.

### Das NYT-Diagramm

Pro Kalendertag vier Größen übereinander:

* hellgraue Fläche – Spanne zwischen Rekordtief und Rekordhoch seit Messbeginn
* beigefarbene Fläche – Normalspanne, also mittleres Tagesminimum und
  -maximum der Normalperiode 1991–2020
* dunkler Balken – die Tagesspanne des dargestellten Jahres
* rote und blaue Spitzen – der Teil des Balkens, der die Normalspanne verlässt
* Punkte – an diesem Kalendertag wurde ein neuer Rekord aufgestellt

| Variante | Datei | Anmerkung |
|---|---|---|
| **matplotlib** | `plots/python/nyt_matplotlib.py` | die vollständigste: Legende, beschriftete Extremwerte, feinste Kontrolle |
| **plotnine** | `plots/python/nyt_plotnine.py` | ggplot-Grammatik in Python, Legende entsteht aus den Daten |
| **plotly** | `plots/python/nyt_plotly.py` | Standbild über kaleido; mit `--html` zusätzlich interaktiv |
| **R / ggplot2** | `plots/R/nyt_ggplot2.R` | das Gegenstück in R, gleiche Ebenenlogik |
| **R / lattice** | `plots/R/nyt_lattice.R` | alles in einer Panel-Funktion, Legende von Hand |
| **R / base** | `plots/R/nyt_base.R` | ohne jedes Zusatzpaket, mit Abstand am schnellsten |

### Nur die letzten Monate

`--months 3` beschränkt das NYT-Diagramm auf das letzte Quartal. Die Balken
werden dabei automatisch breiter (die Stärke ergibt sich aus der tatsächlichen
Achsenbreite, damit sie sich in keinem Format berühren), die Monatsnamen
werden ausgeschrieben, und Untertitel wie Kennzahlen beziehen sich dann auf
den Ausschnitt statt auf das ganze Jahr.

```bash
python plots/python/nyt_matplotlib.py --station 4931 --months 3
python plots/python/instagram_card.py --station 4931 --months 3   # 1080 × 1350
```

Fürs Instagram-Format ist das die brauchbarere Fassung: über zwölf Monate sind
die Tagesbalken im Hochformat nur noch Striche.

### Die Fünf-Jahres-Variante

Beantwortet die Frage „ist es dieses Jahr wirklich viel heißer als letztes?“.
An rohen Tageswerten lässt sie sich nicht beantworten, dafür schwanken sie zu
stark. Deshalb: 31-Tage-Mittel der Tagesmitteltemperatur, ein Verlauf je Jahr,
darunter der aufsummierte Niederschlag. Die Kennzahlen rechts sind auf den
Stichtag des laufenden Jahres gekürzt – sonst vergleicht man ein Rumpfjahr mit
vollen Jahren.

* `plots/python/fuenf_jahre_matplotlib.py`
* `plots/R/fuenf_jahre_ggplot2.R` (mit patchwork)

### Die Fünf-Jahres-Variante mit Min/Max-Strichen

Ein anderer Zugang zur selben Frage: die Tagesbalken des laufenden Jahres wie
im NYT-Diagramm, und dahinter für jeden Kalendertag die Tagesminima und
-maxima der fünf Vorjahre als schmale waagerechte Striche, die mit zunehmendem
Alter heller werden.

Der Unterschied zur geglätteten Fassung: dort sieht man den Verlauf, hier den
einzelnen Tag. Ob ein heißer Tag im Rahmen der letzten Jahre liegt oder aus
ihnen herausragt, lässt sich nur so ablesen. Über ein ganzes Jahr wird es
allerdings dicht – im Quartalsausschnitt kommt die Idee besser zur Geltung.

```bash
python plots/python/fuenf_jahre_striche_matplotlib.py --station 4931
python plots/python/fuenf_jahre_striche_matplotlib.py --station 4931 --months 3
```

### Beiträge für Instagram: quadratisch und ohne Text im Bild

Die Grafiken unter `posts/` sind fürs Veröffentlichen gedacht: 1080 × 1080,
kein Titel, keine Fußzeile, nur Diagramm und Legende. Die Achse links trägt nur
die Einheit `°C`. Alles Textliche – Überschrift, Erklärung der Flächen,
Kennzahlen, Quellenangabe, Hashtags – steht daneben in einer `text.txt`.

Je Beitrag entsteht ein eigener Ordner, damit ein Upload-Skript später nur auf
das Verzeichnis zeigen muss:

```
posts/nyt_serie_04931_2026-08-10/bild_1.jpg … bild_6.jpg
posts/nyt_serie_04931_2026-08-10/text.txt
posts/drei_tage_04931_2026-08-10/bild.jpg
posts/drei_tage_04931_2026-08-10/text.txt
```

Das NYT-Diagramm gibt es in vier Zuschnitten:

```bash
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum serie
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum jahr
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum quartal --zurueck 2
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum monate --months 3
```

`serie` ist der Regelfall: sechs Bilder in einem Ordner für einen
Karussell-Beitrag – das Kalenderjahr, die vier jüngsten Quartale mit dem
laufenden zuletzt, und die Legende als Schlussbild. Die Quartale sind starr am
Kalender ausgerichtet und reichen im ersten Halbjahr ins Vorjahr zurück, für
das dann ebenfalls Kennzahlen abgeleitet sein müssen.

Alle Bilder einer Serie teilen sich **eine** Temperaturskala – mit je eigener
Skala sähe ein kühles Quartal beim Wischen aus wie ein heißes. Und keines der
Diagramme trägt einen Legendenkasten: er würde je nach Jahreszeit genau die
Tage verdecken, um die es geht.

Das ganze Jahr im Quadrat funktioniert, wird aber dicht: 365 Tagesbalken auf
1080 px lassen je Tag knapp drei Pixel. Ein Quartal ist der bessere
Kompromiss, wenn die Balken einzeln erkennbar bleiben sollen.

Die ältere Fassung `instagram_card.py` schreibt Titel und Kennzahlen ins Bild
(1080 × 1350) – nützlich, wenn die Grafik auch ohne Bildtext lesbar sein soll.

### Die letzten drei Tage

Quadratisch (1080 × 1080), die aktuelle Kurve in Blau
(RGB 35 · 102 · 202), dahinter dieselben Kalendertage der fünf Vorjahre in
Grau, das mit dem Alter heller wird (Grauwerte 160, 180, 200, 220, 240).

```bash
python plots/python/drei_tage_matplotlib.py --station 4931
python plots/python/drei_tage_matplotlib.py --station 4928 --days 5 --years 3
```

Diese Grafik liegt als einzige auf **Stundenwerten** (`fetch_hourly.py`) statt
auf Tageswerten – aus drei Tagen Tageswerten würden drei Punkte, keine Kurve.
Die Vorjahre werden über Monat, Tag und Stunde zugeordnet und liegen damit
kalendarisch exakt untereinander. Fällt ein 29. Februar ins Fenster, bleibt die
Kurve in Nicht-Schaltjahren dort lückenhaft.

### Optionen

Alle Skripte verstehen dieselben Optionen:

```bash
python plots/python/nyt_matplotlib.py --station 4928 --year 2025 --dpi 300 --format pdf
Rscript  plots/R/nyt_ggplot2.R        --station 4928 --year 2025 --dpi 300
```

Die Normalperiode lässt sich beim Ableiten umstellen:

```bash
python climatology.py --reference 1961 1990
```

## Instagram

Der Kanal heißt **wettergeschichte**. Der tägliche Ablauf steht oben; alles
Weitere – Einrichtung der Meta-App, Zugriffstoken, Bildablage, Karussell,
Stolpersteine – in [INSTAGRAM.md](INSTAGRAM.md).

Drei Dinge, die man wissen sollte:

* **Die API lädt keine Datei hoch.** Sie holt sich das Bild von einer
  öffentlich erreichbaren URL. Deshalb wandern die JPGs zuerst in das
  Repository [wettergeschichtebilder](https://github.com/volkerreichenberger/wettergeschichtebilder)
  und werden über GitHub Pages ausgeliefert.
* **Nur JPEG**, höchstens 10 Bilder je Karussell, Bildtext bis 2200 Zeichen,
  100 API-Beiträge je Konto und 24 Stunden.
* **Das Zugriffstoken gilt 60 Tage.** `post_daily.py` verlängert es
  selbsttätig, sobald weniger als 14 Tage bleiben. Läuft es doch einmal ab,
  hilft nur der Weg über das Meta-Dashboard.

## Datenquelle

Deutscher Wetterdienst, Climate Data Center,
[opendata.dwd.de](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/).
Die Daten stehen unter der [GeoNutzV](https://www.dwd.de/DE/service/copyright/copyright_node.html)
zur freien Nutzung; als Quellenangabe genügt „Deutscher Wetterdienst“, bei
Veränderung mit dem Zusatz „verändert“.
