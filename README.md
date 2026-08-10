# Wettergeschichte

Grafische Auswertung von Wetterdaten des Deutschen Wetterdienstes für die
beiden Stuttgarter Stationen im Stil des klassischen
[New-York-Times-Wetterdiagramms](https://graphics8.nytimes.com/images/2016/02/19/multimedia/oakImage-1455906157517/oakImage-1455906157517-superJumbo.png).

| Station | Name | Höhe | Daten seit |
|---|---|---|---|
| 4928 | Stuttgart (Schnarrenberg) | 314 m | 1958 |
| 4931 | Stuttgart-Echterdingen | 371 m | 1953 |

## Schnellstart

```bash
python run_all.py                 # Daten holen, Kennzahlen ableiten, alle Grafiken bauen
open output/                      # Varianten vergleichen
```

Einzelne Schritte:

```bash
python fetch_dwd.py               # nur Daten aktualisieren (inkrementell)
python fetch_dwd.py --status      # zeigen, was lokal liegt
python climatology.py --year 2026 # Normalen, Rekorde und Jahreswerte ableiten
python run_all.py --skip-fetch --only matplotlib   # nur neu zeichnen
```

Gebraucht werden Python (pandas, numpy, matplotlib; für einzelne Varianten
zusätzlich plotnine, plotly + kaleido) und R (ggplot2, patchwork, lattice,
ragg). Fehlt ein Paket, schlägt nur die betreffende Variante fehl, der Rest
läuft weiter.

## Aufbau

```
fetch_dwd.py        holt die DWD-Rohdaten, inkrementell
dwd_datasets.py     Katalog der Datensätze und Spaltennamen
climatology.py      leitet Normalen, Rekorde und Jahreswerte ab
run_all.py          baut alles der Reihe nach
instagram_post.py   veröffentlicht ein Bild über die Instagram-API
plots/python/       matplotlib, plotnine, plotly, Instagram-Karte
plots/R/            ggplot2, lattice, base graphics
data/               Rohdaten, aufbereitete CSVs, abgeleitete Kennzahlen
output/             die fertigen Bilder
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
posts/nyt_h1_04931_2026-08-09/bild.jpg
posts/nyt_h1_04931_2026-08-09/text.txt
```

Das NYT-Diagramm gibt es in vier Zuschnitten:

```bash
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum jahr
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum h1     # Jan–Jun
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum h2     # Jul–Dez
python plots/python/nyt_post_matplotlib.py --station 4931 --zeitraum monate --months 3
```

Das ganze Jahr im Quadrat funktioniert, wird aber dicht: 365 Tagesbalken auf
1080 px lassen je Tag knapp drei Pixel. Die beiden Halbjahre sind der bessere
Kompromiss, wenn die Balken einzeln erkennbar bleiben sollen.

Die ältere Fassung `instagram_card.py` schreibt Titel und Kennzahlen ins Bild
(1080 × 1350) – nützlich, wenn die Grafik auch ohne Bildtext lesbar sein soll.

### Die letzten drei Tage

Quadratisch (1080 × 1080), die aktuelle Kurve in Pantone Classic Blue
(RGB 50 · 81 · 133), dahinter dieselben Kalendertage der fünf Vorjahre in
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

Ja, das Veröffentlichen geht über eine API – Details, Einrichtung und
Stolpersteine stehen in [INSTAGRAM.md](INSTAGRAM.md). Kurz:

```bash
python plots/python/instagram_card.py --station 4931 --year 2026
```

erzeugt eine Fassung im Hochformat 1080 × 1350 als JPEG plus einen fertigen
Bildtext daneben. `instagram_post.py` schickt beides über die Content
Publishing API los. Der wichtigste Haken: die API lädt keine Datei hoch,
sondern holt sich das Bild von einer öffentlich erreichbaren URL.

## Datenquelle

Deutscher Wetterdienst, Climate Data Center,
[opendata.dwd.de](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/).
Die Daten stehen unter der [GeoNutzV](https://www.dwd.de/DE/service/copyright/copyright_node.html)
zur freien Nutzung; als Quellenangabe genügt „Deutscher Wetterdienst“, bei
Veränderung mit dem Zusatz „verändert“.
