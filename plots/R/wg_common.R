# Gemeinsame Farben, Texte und Datenzugriffe für alle R-Grafiken.
#
# Die R-Skripte lesen dieselben CSVs aus data/derived/ wie die Python-Skripte,
# damit sich die Varianten nur in der Umsetzung unterscheiden, nicht in den Zahlen.

# ---------------------------------------------------------------------------
# Palette – identisch zu plots/python/wg_common.py
# ---------------------------------------------------------------------------

WG <- list(
  BACKGROUND  = "#ffffff",
  RECORD_BAND = "#e6e2d8",
  NORMAL_BAND = "#b7a583",
  BAR_NEUTRAL = "#4c4c4c",
  WARM        = "#c0392b",
  COLD        = "#2c6fa8",
  GRID        = "#d8d4cb",
  TEXT        = "#1a1a1a",
  TEXT_MUTED  = "#6b6b6b"
)

# Ältere Jahre blass, aktuelles Jahr kräftig.
YEAR_COLORS <- c("#cfc9bd", "#a9c0d4", "#7ea6c6", "#d98b6a", "#b32d22")

MONTH_NAMES <- c("Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dez")
MONTH_NAMES_LONG <- c("Januar", "Februar", "März", "April", "Mai", "Juni",
                      "Juli", "August", "September", "Oktober", "November", "Dezember")
# Erster Tag jedes Monats im 365-Tage-Schema (siehe climatology.py).
MONTH_STARTS <- c(1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335)
MONTH_END <- 366
MONTH_CENTERS <- (MONTH_STARTS + c(MONTH_STARTS[-1], MONTH_END)) / 2

SOURCE_NOTE <- "Datenquelle: Deutscher Wetterdienst, Climate Data Center (opendata.dwd.de)"

# ---------------------------------------------------------------------------
# Deutsche Formatierung, unabhängig vom Locale
# ---------------------------------------------------------------------------

de_num <- function(x, decimals = 1, sign = FALSE) {
  s <- formatC(x, format = "f", digits = decimals, flag = if (sign) "+" else "")
  gsub(".", ",", s, fixed = TRUE)
}

de_date <- function(d) {
  d <- as.Date(d)
  paste0(as.integer(format(d, "%d")), ". ", MONTH_NAMES_LONG[as.integer(format(d, "%m"))])
}

# ---------------------------------------------------------------------------
# Kommandozeile: --station 4931 --year 2026 --output ... --dpi ...
# ---------------------------------------------------------------------------

wg_args <- function(defaults = list()) {
  root <- normalizePath(file.path(dirname(wg_script_dir()), ".."), mustWork = FALSE)
  opts <- utils::modifyList(
    list(station = 4931L, year = as.integer(format(Sys.Date(), "%Y")),
         derived = file.path(root, "data", "derived"),
         output = file.path(root, "output"),
         dpi = 200L, width = 16, height = 9),
    defaults
  )
  raw <- commandArgs(trailingOnly = TRUE)
  i <- 1L
  while (i <= length(raw)) {
    key <- sub("^--", "", raw[i])
    if (!key %in% names(opts)) stop("unbekannte Option: ", raw[i], call. = FALSE)
    value <- raw[i + 1L]
    opts[[key]] <- if (is.numeric(opts[[key]])) as.numeric(value) else value
    i <- i + 2L
  }
  opts$station <- as.integer(opts$station)
  opts$year <- as.integer(opts$year)
  opts
}

wg_script_dir <- function() {
  # Rscript verrät den Pfad nur über --file=
  args <- commandArgs(trailingOnly = FALSE)
  hit <- grep("^--file=", args, value = TRUE)
  if (length(hit)) return(dirname(normalizePath(sub("^--file=", "", hit[1]))))
  getwd()
}

# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------

wg_load <- function(station, year, derived) {
  tag <- sprintf("%05d", station)
  paths <- c(
    clim    = file.path(derived, sprintf("climatology_%s.csv", tag)),
    year    = file.path(derived, sprintf("year_%s_%d.csv", tag, year)),
    recent  = file.path(derived, sprintf("recent_%s_%d.csv", tag, year)),
    summary = file.path(derived, sprintf("summary_%d.csv", year))
  )
  missing <- paths[!file.exists(paths)]
  if (length(missing)) {
    stop("Abgeleitete Daten fehlen:\n  ", paste(missing, collapse = "\n  "),
         "\nBitte 'python climatology.py --year ", year, "' laufen lassen.", call. = FALSE)
  }

  summary_all <- utils::read.csv(paths[["summary"]])
  list(
    clim    = utils::read.csv(paths[["clim"]]),
    year    = transform(utils::read.csv(paths[["year"]]), date = as.Date(date)),
    recent  = transform(utils::read.csv(paths[["recent"]]), date = as.Date(date)),
    summary = as.list(summary_all[summary_all$station_id == station, ][1, ])
  )
}

wg_subtitle <- function(s) {
  sprintf(paste0("Tägliche Höchst- und Tiefsttemperaturen %d im Vergleich zur ",
                 "Normalperiode %d–%d und zu den Rekorden seit %d"),
          s$year, s$reference_from, s$reference_to, s$record_from)
}

wg_stats_line <- function(s) {
  sprintf(paste0("Jahresmittel bisher %s °C (%s K zur Normalperiode)   ·   ",
                 "Höchstwert %s °C   ·   Tiefstwert %s °C   ·   ",
                 "%d Tage ≥ 30 °C   ·   %d Frosttage"),
          de_num(s$temp_mean), de_num(s$anomaly, sign = TRUE),
          de_num(s$temp_max), de_num(s$temp_min),
          s$days_above_30, s$frost_days)
}

wg_footer <- function(s, engine) {
  sprintf("%s  ·  Station %d  ·  Stand %s  ·  Grafik: %s",
          SOURCE_NOTE, s$station_id, s$last_date, engine)
}

wg_out <- function(name, station, year, output, ext = "png") {
  dir.create(output, showWarnings = FALSE, recursive = TRUE)
  file.path(output, sprintf("%s_%05d_%d.%s", name, station, year, ext))
}

# Einheitliches PNG-Gerät: ragg rendert Schrift deutlich sauberer als das
# eingebaute png()-Gerät, ist aber optional.
wg_png <- function(path, width, height, dpi) {
  if (requireNamespace("ragg", quietly = TRUE)) {
    ragg::agg_png(path, width = width, height = height, units = "in",
                  res = dpi, background = WG$BACKGROUND)
  } else {
    grDevices::png(path, width = width, height = height, units = "in",
                   res = dpi, bg = WG$BACKGROUND, type = "cairo")
  }
}
