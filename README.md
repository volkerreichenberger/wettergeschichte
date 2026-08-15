# Wettergeschichte

Grafische Auswertung von Wetterdaten des Deutschen Wetterdienstes für die
beiden Stuttgarter Stationen im Stil des klassischen
[New-York-Times-Wetterdiagramms](https://graphics8.nytimes.com/images/2016/02/19/multimedia/oakImage-1455906157517/oakImage-1455906157517-superJumbo.png).

| Station | Name | Höhe | Daten seit | wird verwendet für |
|---|---|---|---|---|
| 4931 | Stuttgart-Echterdingen | 371 m | 1953 | Temperaturbeiträge; auf Instagram als „Stuttgart (Süd)" |
| 4928 | Stuttgart (Schnarrenberg) | 314 m | 1958 | den Bewölkungsbeitrag, Strahlungsdaten, Vergleiche |

Beide Stationen erscheinen also auf Instagram. Der Grund für die Aufteilung ist
kein gestalterischer, sondern ein Loch in den Daten: An 4931 fehlt der
**Bedeckungsgrad von Juni 2022 bis August 2023** vollständig — 15 Monate am
Stück. An 4928 ist dieselbe Reihe praktisch lückenlos, deshalb kommt die
Bewölkung von dort. Der Begleittext des Beitrags sagt das und nennt den Grund.

---

# Der tägliche Ablauf

**Ein Befehl macht alles:**

```bash
cd ~/Programming/wettergeschichte
./post_daily.py --publish
```

Der Reihe nach: Token prüfen und bei Bedarf verlängern → Daten beim DWD
holen → Kennzahlen ableiten → alle Beiträge bauen → Bilder in die
Bildablage schieben → auf Instagram veröffentlichen.

**Nicht vor 10 Uhr laufen lassen.** Der DWD schiebt die Daten des Vortags
morgens gegen 8:40 bis 9:00 Uhr nach. Wer früher startet, baut den Beitrag mit
vorgestrigen Zahlen — das Skript merkt das nicht, weil es keine Lücke gibt,
sondern nur einen Tag weniger. Die Beispiele hier nehmen 11 Uhr; das lässt
Luft für einen verspäteten Nachschub.

### Wenn du es Schritt für Schritt willst

```bash
# 1. Daten holen (macht nichts, wenn der DWD nichts Neues hat)
python3 fetch_dwd.py --stations 4931 4928     # 4928 für die Bewölkung
python3 fetch_hourly.py --stations 4931       # Stundenwerte nur für 4931

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

Welche Beiträge entstehen, legt `VARIANTE` in `post_daily.conf` fest — mehrere
durch Leerzeichen getrennt. Vorgabe ist
`serie drei-tage bewoelkung regen-kumulativ`, also vier Beiträge je Lauf:

| Variante | Beitrag | wie oft |
|---|---|---|
| `serie` | Karussell aus sechs Bildern: das Kalenderjahr, die vier jüngsten Quartale, die Legende | täglich |
| `drei-tage` | die letzten drei Tage im Stundenverlauf, dahinter dieselben Tage der fünf Vorjahre | täglich |
| `bewoelkung` | Bewölkungskalender des **laufenden** Monats und der fünf Vorjahre, dazu ein Streifenbild über neun Jahre | täglich |
| `regen-kumulativ` | vier Jahre untereinander, jedes als Summenkurve gegen den Normalverlauf | täglich |

`bewoelkung` nimmt den laufenden Monat. Das erste Bild reicht bis zum letzten Tag
mit Daten, der Rest des Monats bleibt als gestrichelter Umriss leer; die Vorjahre
dahinter sind immer **ganze** Monate, damit man sieht, worauf der laufende Monat
zusteuert. Am Monatsanfang ist das ein einzelnes Kästchen — so gewollt, die
Reihe wächst dann Tag für Tag mit. Solange der Monat läuft, nennt der
Begleittext den Stand und verkneift sich einen Rang: ein angefangener Monat und
ein ganzer sind nicht dasselbe.

Weil täglich ein Feld dazukommt, wird der laufende Monat bei jedem Lauf neu
gezeichnet. Ein **abgeschlossener** Monat dagegen, den es schon als Ordner gibt,
wird übersprungen: Er ändert sich nicht mehr, und ein zweiter Lauf hieße ein
zweiter Beitrag. `--force` hebt genau diese Sperre auf.

```bash
./post_daily.py --variante bewoelkung                            # laufender Monat
./post_daily.py --variante bewoelkung --publish
./post_daily.py --variante bewoelkung --monat 2026-01 --force --publish
```

Liegt noch kein einziger Tag vor — genau am Ersten, solange der DWD den Vortag
nachschiebt — oder fehlen bei mehr als zwei gemeldeten Tagen die Messwerte
(`--max-fehlend`), endet das Bauskript mit Rückgabewert 3 — „nichts zu tun“,
kein Fehler.

Der Beitrag kommt von **Station 4928**, die übrigen von 4931 — `post_daily.py`
holt deshalb die Daten beider Stationen und gibt jeder Variante die passende mit.

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
0 11 * * *  cd ~/Programming/wettergeschichte && ./post_daily.py --publish >> log/post.log 2>&1
```

Auf einem Server mit virtueller Umgebung sieht die Zeile anders aus, und es
gibt ein paar Fallstricke — siehe [Täglich laufen lassen](#täglich-laufen-lassen).

---

## Was nie ins Repository darf

| | |
|---|---|
| `post_daily.conf` | Zugriffstoken, App-Geheimcode, Konto-ID |
| `post_daily.conf.*` | Sicherungskopien davon — dieselben Geheimnisse |
| Zugriffstoken im Klartext | `IGAA…`, `EAA…`, auch in Dokumentation oder Commit-Nachrichten |
| Instagram-App-Geheimcode | steht im Meta-Dashboard, gehört nur in die lokale Konfiguration |

Alles davon deckt `.gitignore` ab. Verlassen sollte man sich darauf nicht: Ein
`git add -A` nach einer längeren Sitzung nimmt leicht eine Datei mit, an die
niemand gedacht hat — genau so wäre einmal eine Sicherungskopie der
Konfiguration mitgegangen.

Deshalb liegt unter `hooks/pre-commit` eine zusätzliche Sperre. Sie prüft vor
jedem Commit, was im Index liegt, und blockiert verbotene Dateinamen ebenso wie
Inhalte, die die Länge echter Geheimnisse haben. Platzhalter wie `IGAA...` oder
`GEHEIM` lösen bewusst nicht aus.

**Einmalig je Arbeitskopie aktivieren** — `.git/hooks` wird nicht versioniert:

```bash
git config core.hooksPath hooks
git config core.hooksPath          # muss "hooks" ausgeben
```

Schlägt der Haken an, ist das ein Fund und kein Werkzeugfehler: die Datei
gehört mit `git reset <datei>` aus dem Index, nicht der Haken mit
`--no-verify` übergangen.

Und wenn doch einmal ein Token in die Historie gerät: Es ist damit verbrannt.
Dann im Meta-Dashboard ein neues erzeugen und das alte verfallen lassen — die
Historie umzuschreiben hilft nicht, weil das Token in der Zwischenzeit
öffentlich war.

---

## Auf einem neuen Rechner einrichten

Der Ablauf ist einmal auf einem Debian-Server durchgespielt worden; die
Stolpersteine unten sind die, die dabei wirklich aufgetreten sind.

```bash
git clone https://github.com/volkerreichenberger/wettergeschichte.git
git clone https://github.com/volkerreichenberger/wettergeschichtebilder.git
cd wettergeschichte
git config core.hooksPath hooks          # Sperre gegen Zugangsdaten im Repo

python3 -m venv .venv                    # siehe "Virtuelle Umgebung" unten
source .venv/bin/activate
pip install -r requirements.txt

cp /pfad/vom/alten/rechner/post_daily.conf .   # oder aus der Vorlage bauen
chmod 600 post_daily.conf
python3 check_setup.py
```

`check_setup.py` prüft, was der tägliche Ablauf braucht, und ändert nichts.
Es unterscheidet **FEHLT** (läuft so nicht) von **Hinweis** (läuft, betrifft
aber das Aussehen oder eine Nebenvariante). Mit `--alles` kommen die
Vergleichsvarianten dazu (plotnine, plotly, R), mit `--keine-netzpruefung`
bleibt es offline.

### Virtuelle Umgebung

Auf Debian 12 und Ubuntu ab 23.04 lehnt das System-Python `pip install` ab
(`externally-managed-environment`, PEP 668), und `pip` heißt dort `pip3` oder
gar nichts. Deshalb der Umweg über `python3 -m venv` — dafür braucht es
`sudo apt install python3-venv python3-pip`.

Zu beachten: `./post_daily.py` startet über die Shebang-Zeile das *System*-
Python, nicht das der Umgebung. Also entweder vorher `source .venv/bin/activate`
oder gleich den vollen Pfad nehmen. Die Unterprozesse erben die Umgebung, weil
`post_daily.py` sie mit `sys.executable` aufruft:

```bash
~/wettergeschichte/.venv/bin/python3 post_daily.py --skip-fetch
```

### Die Schrift

Die Beiträge sind schmal gesetzt: erste Wahl Myriad Pro, Ersatz **Fira Sans**.
Fehlt beides, nimmt matplotlib klaglos DejaVu Sans — die Bilder entstehen,
sehen aber anders aus als alles bisher Veröffentlichte, und das fällt erst auf
Instagram auf. Deshalb prüft `check_setup.py` das eigens.

Debian hat nur Fira *Code* (monospace) im Paketbestand, nicht Fira Sans, und
`fonts.google.com/download?family=…` liefert inzwischen eine HTML-Seite statt
eines ZIP-Archivs. Was bleibt, ist das Repository `google/fonts`:

```bash
mkdir -p ~/.local/share/fonts && cd ~/.local/share/fonts
BASE=https://raw.githubusercontent.com/google/fonts/main/ofl
for s in Regular Italic Medium SemiBold Bold; do
  curl -fLO "$BASE/firasanscondensed/FiraSansCondensed-$s.ttf"
  curl -fLO "$BASE/firasans/FiraSans-$s.ttf"
done
rm -rf ~/.cache/matplotlib      # sonst bleibt die alte Schriftliste stehen
python3 -c "import matplotlib.font_manager as fm; print(sorted({f.name for f in fm.fontManager.ttflist if 'Fira' in f.name}))"
```

`fc-cache` wird **nicht** gebraucht: matplotlib sucht selbst in
`~/.local/share/fonts` und überspringt die fontconfig-Abfrage stillschweigend,
wenn `fc-list` fehlt. Auf einem nackten Server ist fontconfig oft nicht dabei.

### `BILDER` in `post_daily.conf`

Der Pfad zur Bildablage steht dort absolut und zeigt nach dem Kopieren noch auf
den alten Rechner. `WG_UPLOAD_CMD` benutzt `$BILDER`, mehr ist nicht zu ändern.

### Push-Zugang zur Bildablage

`post_daily.py` committet und pusht in `wettergeschichtebilder`. Für einen
Rechner, der unbeaufsichtigt per cron läuft, ist ein **SSH-Deploy-Key** die
richtige Wahl: Er gilt nur für dieses eine Repository, läuft nicht ab, und ein
Token im Klartext erübrigt sich.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_wettergeschichtebilder -N "" -C "cron"
cat ~/.ssh/id_wettergeschichtebilder.pub
```

Den Text unter *Settings → Deploy keys → Add deploy key* des Repositories
eintragen, **"Allow write access" ankreuzen**. Dann:

```bash
cat >> ~/.ssh/config <<'ENDE'

Host github-bilder
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_wettergeschichtebilder
  IdentitiesOnly yes
ENDE
chmod 600 ~/.ssh/config

git -C ~/wettergeschichtebilder remote set-url origin git@github-bilder:volkerreichenberger/wettergeschichtebilder.git
ssh -T git@github-bilder          # Fingerabdruck einmal mit "yes" bestätigen
git -C ~/wettergeschichtebilder push
```

Das `ssh -T` ist kein Zierrat: Ohne den Eintrag in `~/.ssh/known_hosts` bleibt
der cron-Lauf später an der Fingerabdruck-Frage hängen, und niemand ist da, der
antwortet.

**Wenn Port 22 gesperrt ist** — in Server-Netzen die Regel, erkennbar an
`ssh: connect to host github.com port 22: Connection refused` — bietet GitHub
dieselbe Verbindung auf Port 443 an. Im Block oben dann zwei Zeilen ändern:

```
Host github-bilder
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_wettergeschichtebilder
  IdentitiesOnly yes
```

Nicht einen zweiten `Host github-bilder`-Block anhängen: SSH nimmt bei
doppelten Einträgen den **ersten** Wert je Schlüsselwort, der alte gewönne
also. Der Fingerabdruck landet danach als `[ssh.github.com]:443` in
`known_hosts` — ein eigener Eintrag, deshalb muss `ssh -T git@github-bilder`
auch nach der Umstellung noch einmal laufen.

### Täglich laufen lassen

`BENUTZER` unten durch den eigenen Kontonamen ersetzen — `pwd` im
Projektverzeichnis zeigt den vollen Pfad.

```bash
mkdir -p ~/wettergeschichte/log     # log/ ist nicht im Repository
crontab -e
```

```cron
0 11 * * *  cd /home/BENUTZER/wettergeschichte && .venv/bin/python3 post_daily.py --publish >> log/post.log 2>&1
```

Fünf Dinge, an denen cron-Einträge scheitern:

* **Absoluter Pfad.** cron führt die Zeile mit `/bin/sh` aus, und deren `PATH`
  ist kurz. `~` durch den vollen Pfad ersetzen, `python3` durch
  `.venv/bin/python3` — sonst nimmt er das System-Python ohne pandas.
* **Uhrzeit in der Zeitzone des Servers**, nicht in Deiner — `timedatectl`
  zeigt sie. Der DWD liefert die Vortagsdaten gegen 8:40–9:00 Uhr deutscher
  Zeit. Auf `Europe/Berlin` passt `0 11`, und die Umstellung zwischen Sommer-
  und Winterzeit erledigt cron mit. Auf UTC müsste die Zeile zweimal im Jahr
  gewechselt werden (`0 9` beziehungsweise `0 10`); einfacher ist
  `sudo timedatectl set-timezone Europe/Berlin`.
* **Geht die Uhr richtig?** `timedatectl` zeigt es als
  `System clock synchronized`. Steht dort `no`, läuft die Uhr womöglich weg,
  und der Auftrag startet irgendwann vor den DWD-Daten — das fällt nicht als
  Fehler auf, sondern nur als fehlender Tag im Bild. Abhilfe:
  `sudo timedatectl set-ntp true`. Bleibt es bei `no`, sperrt vermutlich die
  Firewall ausgehendes UDP auf Port 123.
* **Ausgabe umleiten.** Ohne `>> log/post.log 2>&1` verschickt cron sie per
  Mail, und ohne Mailsystem ist sie schlicht weg — auch die Fehlermeldungen.
* **Erst von Hand prüfen**, und zwar mit derselben leeren Umgebung, die cron
  benutzt:

  ```bash
  WG=/home/BENUTZER/wettergeschichte
  env -i HOME=$HOME sh -c "cd $WG && .venv/bin/python3 post_daily.py --skip-fetch"
  env -i HOME=$HOME sh -c "cd $WG && .venv/bin/python3 post_daily.py --upload-only"
  ```

  Der erste Aufruf prüft das Bauen, der zweite zusätzlich den Push in die
  Bildablage — den Teil, der ohne `known_hosts`-Eintrag hängen bleibt.
  `--upload-only` legt die Bilder ab und veröffentlicht nichts. Laufen beide
  durch, läuft auch cron.

Das Zugriffstoken verlängert `post_daily.py` selbsttätig, sobald weniger als
14 Tage Restlaufzeit bleiben — dafür ist kein eigener Eintrag nötig. Es
schreibt das neue Token in `post_daily.conf` zurück, die Datei muss für den
cron-Benutzer also schreibbar sein.

### Daten und Kennzahlen

Die Rohdaten liegen nicht im Repository. `post_daily.py` holt sie beim ersten
Lauf und leitet dabei auch die Kennzahlen ab — beides zusammen überspringt
`--skip-fetch` aber. Wer mit `--skip-fetch` anfängt, braucht sie einmal von Hand:

```bash
python3 fetch_dwd.py --stations 4931 4928
python3 fetch_hourly.py --stations 4931
python3 climatology.py --stations 4931 4928 --year 2025   # Vorjahr: Quartalsserie
python3 climatology.py --stations 4931 4928 --year 2026
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
check_setup.py      prüft, ob auf diesem Rechner alles da ist
post_daily.conf     Station, Varianten, Bildablage, Zugangsdaten (nicht im Repo)
fetch_dwd.py        holt die DWD-Tageswerte, inkrementell
fetch_hourly.py     holt die Stundenwerte (Temperatur, Niederschlag)
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

Alles davon sind echte Eigenheiten der Messreihen, keine Fehler der Skripte:

* **4931 hat beim Bedeckungsgrad ein Loch von Juni 2022 bis August 2023** —
  15 Monate am Stück, 493 fehlende Tage seit 2021. Bei 4928 fehlen im selben
  Zeitraum fünf Tage. Deshalb kommt der Bewölkungsbeitrag von 4928.
* **4931** hat die Sonnenscheindauer im Juli 2023 eingestellt; ab dann steht
  in `sunshine_h` nichts mehr. Für Sonnenschein ist 4928 die Station der Wahl.
* **4931** fehlen 78 Tage aus dem Jahr 2023 vollständig, **4928** acht Tage
  aus dem Jahr 2000 und die Julis **2000 bis 2008**.
* **Strahlungsdaten** (`solar`) gibt es nur für 4928, und sie hinken den
  übrigen Messwerten rund vier Wochen hinterher.

Die beiden Stationen taugen für Temperatur gut als Ersatz füreinander, für
Bewölkung und Sonnenschein nicht — dort entscheidet die Lücke, welche Station
brauchbar ist.

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

Geblieben ist davon nur die Hochkant-Karte `instagram_card.py --chart
fuenf_jahre`, die diese Fassung selbst zeichnet. Die eigenständigen Varianten –
matplotlib geglättet, matplotlib mit Min/Max-Strichen, ggplot2 mit patchwork –
sind entfallen; im Kanal steht dafür das NYT-Diagramm.

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

Diese Grafik liegt auf **Stundenwerten** (`fetch_hourly.py`) statt auf
Tageswerten – aus drei Tagen Tageswerten würden drei Punkte, keine Kurve.
Die Vorjahre werden über Monat, Tag und Stunde zugeordnet und liegen damit
kalendarisch exakt untereinander. Fällt ein 29. Februar ins Fenster, bleibt die
Kurve in Nicht-Schaltjahren dort lückenhaft.

### Niederschlag

`plots/python/regen_matplotlib.py` sammelt mehrere Sichten auf denselben
Datensatz, gewählt über `--art`:

| Art | zeigt |
|---|---|
| `kumulativ` | vier Jahre untereinander, jedes als Summenkurve gegen den Normalverlauf — die Instagram-Variante |
| `rueckstand` | dieselben Summenkurven, aber alle in einem Feld übereinander |
| `schnee` | Anteil der Winterniederschlagstage mit Schnee, über die ganze Reihe |

```bash
python plots/python/regen_matplotlib.py --art kumulativ --station 4931
```

`kumulativ` gibt allen vier Feldern dieselbe Skala und zählt die Tage im
365-Tage-Schema der Klimatologie – sonst läge die Kurve eines Schaltjahres ab
März um einen Tag neben dem Normalverlauf. Das laufende Jahr steht oben und
wird gegen den Normalwert bis zum selben Kalendertag verglichen, nicht gegen
das ganze Jahr.

Ein Wort zur Vorsicht: Beim Niederschlag ist **kein Trend messbar**. Die
Jahressummen streuen mit 117 mm, der Rückgang über 72 Jahre beträgt 58 mm — das
Rauschen ist doppelt so groß wie das Signal. Ein Streifenbild im Stil der
Warming Stripes wäre hier eine Aussage, die die Daten nicht hergeben.
Beim Schneeanteil ist es umgekehrt, dort liegt ein deutliches Signal.

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
