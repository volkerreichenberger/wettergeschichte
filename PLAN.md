# Plan: Bewölkung im Drei-Tage-Beitrag

Stand 22. September 2026. Ziel: Unter dem Temperaturverlauf der Variante
`drei-tage` (`plots/python/drei_tage_matplotlib.py`) erscheint ein Streifen,
der die Bewölkung Stunde für Stunde zeigt, und der Streifen macht nebenbei
sichtbar, wann Nacht war.

## 1. Was die Daten hergeben (geprüft am 22.09.2026)

Der DWD bietet unter `observations_germany/climate/hourly/cloudiness/` einen
Stundendatensatz für **beide** Stationen an, tagesaktuell wie die
Stundentemperatur:

| Station | Datei | seit | Stand |
|---|---|---|---|
| 4931 Echterdingen | `stundenwerte_N_04931_akt.zip` / `…_19490101_20251231_hist.zip` | 1949 | 21.09.2026, 23 Uhr |
| 4928 Schnarrenberg | `stundenwerte_N_04928_akt.zip` / `…_19840807_20251231_hist.zip` | 1984 | 21.09.2026, 23 Uhr |

Spalten der `produkt_n_stunde_…txt`: `STATIONS_ID; MESS_DATUM (JJJJMMTTHH); QN_8;
V_N_I; V_N`.

* `V_N` ist der Bedeckungsgrad in Achteln, 0 bis 8. Zusätzlich kommt **−1**
  vor („nicht bestimmbar", z. B. Nebel): an 4931 in 82 von rund 13 000
  Stunden des `recent`-Jahres. `−1` wird beim Einlesen zu NaN, sonst färbt es
  sich als „klarer als wolkenlos" ein.
* `V_N_I` sagt, wer gemessen hat: `I` Instrument (Ceilometer, über 99 %),
  `P` Person. An 4928 gibt es eine Zeile mit `-999`. Die Spalte wird
  mitgenommen (`cloud_source`), aber nicht gezeichnet; der Begleittext
  darf sagen, dass ein Gerät misst.
* 24 Werte je Tag, keine Lücke in den letzten fünf Tagen. Die bekannte Lücke an
  4931 (Juni 2022 bis August 2023) betrifft nur Vorjahre; der Streifen zeigt
  aber nur die aktuellen drei Tage. **Der Streifen kann also von 4931 kommen**,
  derselben Station wie die Temperatur. Fallback auf `BEWOELKUNG_STATION`
  (4928) nur, wenn im Fenster mehr als ein paar Stunden fehlen.
* Sonnenscheindauer (`hourly/sun`, `SD_SO` in Minuten) gibt es aktuell nur für
  4928; 4931 endet am 03.07.2023. Für diesen Plan nicht nötig, siehe 6.

**Zeitbasis:** `MESS_DATUM` der Stundendaten ist **UTC**. Das gilt auch für
die Temperatur, die das Skript heute schon nimmt, ohne umzurechnen: die
Tagesgrenzen im Bild liegen deshalb bei 0 Uhr UTC, also 1 bzw. 2 Uhr
Ortszeit. Sonnenauf- und -untergang müssen in derselben Basis berechnet
werden, sonst rutscht die Nacht um ein bis zwei Stunden. Ob das Bild
irgendwann auf Ortszeit umgestellt wird, ist eine eigene Entscheidung und
nicht Teil dieses Plans; der Streifen darf sie nicht vorwegnehmen.

Stationskoordinaten aus `N_Stundenwerte_Beschreibung_Stationen.txt`:

| Station | Breite | Länge | Höhe |
|---|---|---|---|
| 4931 | 48,6883° N | 9,2235° O | 371 m |
| 4928 | 48,8281° N | 9,2000° O | 314 m |

## 2. Wie der Streifen aussieht

Unter dem Temperaturfeld liegt ein schmaler Streifen über die volle Breite, ein
Feld je Stunde (72 Felder, bei 1080 px rund 13 px breit), ohne Zwischenräume,
ohne Rahmen. Die Tagesnamen und die Mitternachtslinien wandern unter den
Streifen, damit Kurve und Streifen dieselben Grenzen teilen.

**Der Streifen ist der Himmel.** Die Farbe eines Feldes ist die, die der Himmel
in dieser Stunde hatte:

* **Tag:** die Skala `blau` aus `bewoelkung_matplotlib.py`, fest an 0 bis 8
  Achtel gebunden: `#1f7ae0` wolkenlos → `#7ea6cf` → `#adb5bd` → `#8d9296`
  bedeckt. Dieselbe Skala wie im Bewölkungskalender, damit beide Beiträge
  dieselbe Sprache sprechen.
* **Nacht:** dieselben Achtel, aber der Himmel ist dunkel. Klare Nacht ist
  tiefes Nachtblau, bedeckte Nacht ist dunkles Grau:
  `#0d1b3d` wolkenlos → `#2b3a55` → `#3a4048` → `#33373b` bedeckt.
  Die Nachtskala liegt deutlich unter dem dunkelsten Tagesgrau, so bleibt der
  Wechsel auch bei durchgehend bedecktem Himmel sichtbar.
* **Dämmerung:** kein harter Schnitt, sondern eine Mischung der beiden Skalen
  über den Sonnenstand. Für jede Stunde wird die Sonnenhöhe berechnet; der
  Tagesanteil ist `clip((Höhe + 6°) / 12°, 0, 1)`, also 0 ab −6° (bürgerliche
  Dämmerung), 1 ab +6°. Ein Feld in der Dämmerung mischt Tages- und
  Nachtfarbe linear in diesem Verhältnis. Im September fällt der Übergang in
  ein bis zwei Felder, das reicht als weicher Rand.
* **Fehlt der Wert** (NaN, −1): Feld bleibt weiß, wie die Kurve bei
  Messlücken eine Lücke hat. Kein Grau, das wäre „bedeckt".

**Sonnenauf- und -untergang** stehen als Marken **unter** dem Streifen: ein
kleiner Strich an der Stelle, dazu die Uhrzeit in `TEXT_MUTED`, Größe 9,
je Tag zweimal (`↑ 5:12`, `↓ 17:26`; wenn wir bei UTC bleiben, steht das im
Begleittext). Damit trägt der Streifen eine echte Information mehr: Wie schnell
im Herbst die Tage kürzer werden, sieht man an drei Tagen nicht, aber die
Zeiten stehen da und wiederholen sich nicht mit dem Vortag.

Links vom Streifen ein kleines Wort in `TEXT_MUTED`, so wie das `°C` über der
Skala: `Himmel`. Keine Legende im Bild; die Skala erklärt der Begleittext, und
die Farben tragen sich selbst: Blau heißt klar, Grau heißt bedeckt, dunkel
heißt Nacht.

Warum so und nicht anders:

* **Kein graues Nachtband über dem ganzen Diagramm** (`axvspan`): Es liegt
  hinter den grauen Vorjahreskurven und macht sie schwerer lesbar; die
  Hauptaussage des Beitrags ist der Temperaturvergleich, der bleibt unangetastet.
* **Keine Sonnen- und Mondsymbole**: Zwölf Symbole auf 1080 px sind Unruhe;
  Uhrzeiten sagen mehr.
* **Kein eigener Nachtstreifen** unter dem Wolkenstreifen: Zwei Streifen, die
  man gegeneinander lesen muss. Die Nacht *im* Himmel ist das, was man ohnehin
  erwartet, deshalb braucht es keine Erklärung.

## 3. Umsetzung, Schritt für Schritt

### 3.1 `fetch_hourly.py`: Datensatz `cloudiness`

```python
"cloudiness": Hourly(
    key="cloudiness",
    path="cloudiness",
    label="Bedeckungsgrad, stündlich",
    pattern=r"stundenwerte_N_{sid}_.*\.zip",
    columns={"V_N": "cloud_okta", "V_N_I": "cloud_source"},
    qn="QN_8",
),
```

* In `parse_product` gibt es `pd.to_numeric` für alle Spalten; `cloud_source`
  ist Text (`I`/`P`) und muss davon ausgenommen bleiben, sonst wird sie NaN.
  Einfachste Lösung: ein Feld `text_columns` im `Hourly`-Dataclass, Vorgabe
  leer.
* `cloud_okta == -1` → NaN, mit Kommentar („nicht bestimmbar, meist Nebel").
* Ziel: `data/stations/04931/hourly_cloudiness.csv`. `--status` zeigt die neue
  Datei automatisch mit, wenn er über `HOURLY_DATASETS` iteriert; prüfen.
* `post_daily.py` ruft `fetch_hourly.py --stations <STATION>` ohne
  `--datasets`, holt also alle Stundendatensätze; nichts zu ändern.
  Falls der Fallback auf 4928 gewünscht ist, muss `daten_holen` die zweite
  Station mit übergeben, so wie es für `bewoelkung` schon die Tageswerte tut.

### 3.2 `wg_common.py`: Sonnenstand ohne neue Abhängigkeit

* `STATION_KOORDINATEN = {4931: (48.6883, 9.2235), 4928: (48.8281, 9.2000)}`.
* `sonnenhoehe(zeitpunkt_utc, breite, laenge) -> float` in Grad, nach den
  NOAA-Formeln (Deklination, Zeitgleichung, Stundenwinkel; rund 30 Zeilen).
  Genauigkeit einige Minuten, für Felder von einer Stunde Breite mehr als genug.
* `sonnenauf_untergang(datum, breite, laenge) -> (auf_utc, unter_utc)` aus
  derselben Rechnung mit Sonnenhöhe −0,833° (Refraktion und Sonnenradius).
* `SKALEN` aus `bewoelkung_matplotlib.py` nach `wg_common.py` ziehen, damit
  Kalender und Streifen dieselbe Quelle haben; dazu `NACHTSKALA` neu.
* Plausibilitätsprobe im Docstring festhalten: Stuttgart, 21.09.2026,
  Aufgang etwa 5:12 UTC (7:12 MESZ), Untergang etwa 17:26 UTC (19:26 MESZ).
  Das `astral`-Paket wäre die Alternative; es lohnt für zwei Zahlen am Tag
  nicht, `requirements.txt` bleibt wie sie ist.

### 3.3 `drei_tage_matplotlib.py`: Streifen zeichnen

* `load_hourly` bekommt einen zweiten Leser für `hourly_cloudiness.csv`;
  die Achtel werden über `timestamp` an `current` gehängt (`merge`, `how="left"`,
  Vorjahre brauchen keine Bewölkung).
* Layout: das Temperaturfeld von `(0.105, 0.205, 0.875, 0.735)` auf
  `(0.105, 0.275, 0.875, 0.665)`; darunter der Streifen als eigene Achse
  `(0.105, 0.218, 0.875, 0.040)`, gleiche `xlim`. Die Tagesbeschriftung
  (`day_axis`) wandert an die Streifenachse; die Mitternachtslinien werden in
  beiden Achsen gezeichnet, im Streifen als schmale weiße Fuge (`lw` 1,5 in
  `BACKGROUND`), damit die Tage auch dort getrennt bleiben.
* Farbe je Stunde: `tag = clip((hoehe + 6) / 12, 0, 1)`;
  `farbe = tag * skala_tag(okta / 8) + (1 - tag) * skala_nacht(okta / 8)`
  (RGB-Mischung, `to_rgb`). Zeichnen mit einem `imshow` über ein
  `(1, 72, 3)`-Array, `aspect="auto"`, `interpolation="nearest"`, oder mit
  `ax.bar(x, 1, width=1, color=…, linewidth=0)`; `imshow` ist bei 72 Feldern
  die saubere Wahl und vermeidet Haarlinien zwischen den Balken im JPEG.
  NaN-Felder auf `BACKGROUND` setzen.
* Marken für Auf- und Untergang: `ax_himmel.plot([x], [-0.15], marker="|")` in
  `TEXT_MUTED` unter dem Streifen und `ax_himmel.text(x, -0.55, "↑ 5:12", …)`,
  `fontsize=9`, `ha="center"`; `clip_on=False`, damit der Text unter die Achse
  darf. Position `x` aus der Uhrzeit: Stundenindex plus Minutenanteil.
* Beschriftung `Himmel` links als `set_ylabel("Himmel", rotation=0, …)` analog
  zu `°C`; y-Ticks aus, alle Spines aus.
* Die Achsen `x` der Marken und die Feldmitten müssen exakt zur Temperaturkurve
  passen: Kurve bei ganzen Stunden `x = 0 … 71`, Feld `i` von `i − 0,5` bis
  `i + 0,5`. Die Mitternachtslinie liegt heute bei `x − 0,5`, das passt.

### 3.4 Begleittext (`caption`)

Nach dem Absatz zur blauen Linie ein Absatz:

> Der Streifen darunter ist der Himmel, Stunde für Stunde: Blau heißt klar,
> Grau heißt bedeckt, gemessen in Achteln des Himmels, die Wolken verdecken.
> Nachts dunkelt der Streifen ab, ein klarer Nachthimmel ist tief dunkelblau,
> ein bedeckter dunkelgrau. Die Marken darunter sind Sonnenauf- und
> -untergang.

Kennzahlen ergänzen: `· Bewölkung im Mittel x Achtel, y klare und z bedeckte
Stunden` (klar: höchstens 2 Achtel, bedeckt: mindestens 7, wie beim
Kalender; dort sind es 2 und 6 für Tage, hier lieber 7 für Stunden, weil 8
Achtel die häufigste Stunde ist). Wenn Stunden fehlen, wie bei den Vorjahren
den Grund nennen. Falls die Bewölkung von 4928 kommt, steht das im Text, mit
Grund, wie beim Bewölkungsbeitrag.

### 3.5 Doku

* `README.md`: Zeile `drei-tage` in der Variantentabelle um den Streifen
  ergänzen; im Abschnitt „Die Daten" den Stundendatensatz `cloudiness` (beide
  Stationen, Zeitbasis UTC, `−1` und `V_N_I`) aufnehmen; unter „Was in den
  Daten auffällt" den Hinweis, dass die Stundenreihe an 4931 anders als die
  Tagesreihe keine 15-Monats-Lücke hat, falls die Prüfung in 4 das bestätigt.
* Docstring von `drei_tage_matplotlib.py` um den Streifen ergänzen.

## 4. Abnahme

1. `python3 fetch_hourly.py --stations 4931 4928 --datasets cloudiness`, dann
   `--status`: beide Stationen bis gestern.
2. Prüfen, ob die Stundenreihe von 4931 im Zeitraum Juni 2022 bis August 2023
   Werte hat (die Tagesreihe hat dort keine). Ergebnis in die README.
3. `./post_daily.py --variante drei-tage --skip-fetch` (kein `--publish`),
   Bild öffnen und ansehen:
   * Streifenfelder bündig zu den Mitternachtslinien und zu den Stunden der
     Kurve (eine Stunde mit auffälligem Wert, etwa 8 Achtel, gegen die CSV
     prüfen).
   * Nachtfelder dort, wo die Kurve ihr Minimum kurz vor dem Aufgang hat.
   * Auf- und Untergangszeiten gegen eine Referenz (timeanddate, Stuttgart)
     innerhalb von fünf Minuten, in der richtigen Zeitbasis.
   * JPEG bei 1080 px: keine Haarlinien zwischen den Feldern, kein Moiré.
4. Mit `--stand` drei Sondertage bauen: einen klaren Sommertag, einen
   durchgehend bedeckten Wintertag (Nacht muss sich vom Tag trotzdem abheben),
   einen Nebeltag mit `−1`-Stunden (weiße Lücken, kein Absturz).
5. Begleittext lesen: Kennzahlen stimmen mit der CSV überein, Wortlaut passt
   zum Rest.
6. Erst danach Commit anbieten (Regel aus `CLAUDE.md`: nicht ungefragt) und
   `--publish` nur auf Ansage.

## Nachtrag 22.09.2026: umgesetzt

Alles aus Abschnitt 3 ist gebaut (`fetch_hourly.py`, `wg_common.py`,
`drei_tage_matplotlib.py`, README). Abweichung vom Plan auf Wunsch: der
Streifen zeigt keine 72 harten Felder mehr, sondern interpoliert zwischen den
Stundenwerten linear auf einem 6-Minuten-Raster (`FEIN`); die Dämmerung wird
je Rasterpunkt gemischt. Fehlende Stunden bleiben weiß, samt der halben Stunde
davor und danach, damit die Interpolation eine Lücke nicht überbrückt.
Sonnenzeiten geprüft: innerhalb von drei Minuten an den Kalenderwerten.
Committet als `9de58aa`.

**Entscheidung Zeitbasis (22.09.2026): immer Ortszeit.** Die Stundenwerte
werden beim Laden von UTC nach Europe/Berlin umgerechnet (zonenbewusst, damit
die Zeitumstellung keine Lücke vortäuscht und die doppelte Stunde im Herbst
erhalten bleibt). Tagesgrenzen, Uhrzeiten im Begleittext und Sonnenmarken sind
seitdem Ortszeit; die erste offene Entscheidung unten ist damit erledigt.

## 5. Offene Entscheidungen

* **Zeitbasis:** UTC beibehalten (Bild wie bisher, Auf- und Untergang in UTC
  beschriften) oder das ganze Drei-Tage-Bild auf Ortszeit umstellen. Der
  Streifen macht die Frage sichtbar, weil Sonnenaufgang „um 5 Uhr" auffällt.
  Vorschlag: Ortszeit für das ganze Bild, als eigener Schritt vor diesem Plan.
* **Station für den Streifen:** 4931 (dieselbe wie die Temperatur, Vorschlag)
  oder immer 4928 wie beim Kalender. Für den Vergleich mit dem Kalender spräche
  4928, für die Konsistenz im Bild 4931.
* **Nachtskala:** die vier Farbwerte oben sind ein Vorschlag und werden am
  fertigen Bild nachjustiert; fest ist nur die Regel, dass die Nacht unter dem
  dunkelsten Tagesgrau bleibt.

## 6. Später, nicht jetzt

* **Sonnenscheindauer** (`hourly/sun`, nur 4928) als zweite Information:
  Minuten Sonne je Stunde als kleiner gelber Punkt im Feld, wie die
  Sonnenscheibe im Kalender-Stil `sonne`. Erst, wenn der Streifen steht.
* **Vorjahre im Streifen:** die Bewölkung derselben drei Tage aus dem Vorjahr
  als zweiter, schmalerer Streifen. Wahrscheinlich zu viel für ein Bild; eher
  ein eigener Beitrag.
