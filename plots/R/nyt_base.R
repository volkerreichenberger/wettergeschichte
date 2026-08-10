#!/usr/bin/env Rscript
# NYT-Klimadiagramm mit R-Bordmitteln (base graphics).
#
# Ohne jedes Zusatzpaket: polygon(), segments(), points(), axis(). Das ist die
# schnellste Variante und läuft auf jeder R-Installation, dafür muss man jede
# Achse und jede Beschriftung selbst setzen.
#
#   Rscript plots/R/nyt_base.R --station 4931 --year 2026

source(file.path(dirname(sub("^--file=", "",
  grep("^--file=", commandArgs(FALSE), value = TRUE)[1])), "wg_common.R"))

opts <- wg_args()
d <- wg_load(opts$station, opts$year, opts$derived)
clim <- d$clim; yr <- d$year; s <- d$summary

ymin <- min(clim$record_low, yr$temp_min_c, na.rm = TRUE) - 2
ymax <- max(clim$record_high, yr$temp_max_c, na.rm = TRUE) + 11
ybreaks <- seq(floor(ymin / 5) * 5, ceiling(ymax / 5) * 5, by = 5)

hi_mask <- as.logical(yr$is_record_high)
lo_mask <- as.logical(yr$is_record_low)

path <- wg_out("nyt_base", opts$station, opts$year, opts$output)
wg_png(path, opts$width, opts$height, opts$dpi)

# mar in Zeilenhöhen: unten Monatsnamen, links Skala, oben der Titelblock.
par(mar = c(3.2, 4.0, 7.6, 1.4), mgp = c(2, 0.7, 0), family = "sans",
    xaxs = "i", bg = WG$BACKGROUND, col.axis = WG$TEXT_MUTED)

plot(NA, xlim = c(1, MONTH_END), ylim = c(ymin, ymax),
     axes = FALSE, xlab = "", ylab = "")

polygon(c(clim$doy, rev(clim$doy)), c(clim$record_high, rev(clim$record_low)),
        col = WG$RECORD_BAND, border = NA)
polygon(c(clim$doy, rev(clim$doy)), c(clim$normal_high, rev(clim$normal_low)),
        col = WG$NORMAL_BAND, border = NA)

abline(h = ybreaks, col = WG$GRID, lwd = 0.5)
abline(v = MONTH_STARTS[-1], col = WG$GRID, lwd = 0.7)
abline(h = 0, col = WG$GRID, lwd = 0.9, lty = 2)

segments(yr$doy, yr$bar_low,   yr$doy, yr$bar_high, col = WG$BAR_NEUTRAL, lwd = 1.2)
segments(yr$doy, yr$warm_from, yr$doy, yr$warm_to,  col = WG$WARM,        lwd = 1.2)
segments(yr$doy, yr$cold_from, yr$doy, yr$cold_to,  col = WG$COLD,        lwd = 1.2)

points(yr$doy[hi_mask], yr$temp_max_c[hi_mask], pch = 21,
       bg = WG$WARM, col = "white", cex = 0.6, lwd = 0.6)
points(yr$doy[lo_mask], yr$temp_min_c[lo_mask], pch = 21,
       bg = WG$COLD, col = "white", cex = 0.6, lwd = 0.6)

axis(1, at = MONTH_CENTERS, labels = MONTH_NAMES, tick = FALSE, line = -0.4, cex.axis = 1.0)
axis(2, at = ybreaks, labels = paste0(ybreaks, "°"), las = 1, tick = FALSE,
     line = -0.6, cex.axis = 1.0)

# --- Extremwerte -------------------------------------------------------------
i_hi <- which.max(yr$temp_max_c); i_lo <- which.min(yr$temp_min_c)
segments(yr$doy[i_hi] - 26, yr$temp_max_c[i_hi] + 6,
         yr$doy[i_hi], yr$temp_max_c[i_hi], col = WG$WARM, lwd = 0.7)
text(yr$doy[i_hi] - 26, yr$temp_max_c[i_hi] + 6.5, adj = c(0.5, 0), cex = 0.78, col = WG$WARM,
     labels = sprintf("wärmster Tag\n%s: %s °C",
                      de_date(yr$date[i_hi]), de_num(yr$temp_max_c[i_hi])))
segments(yr$doy[i_lo] + 28, yr$temp_min_c[i_lo] - 5,
         yr$doy[i_lo], yr$temp_min_c[i_lo], col = WG$COLD, lwd = 0.7)
text(yr$doy[i_lo] + 28, yr$temp_min_c[i_lo] - 5.5, adj = c(0.5, 1), cex = 0.78, col = WG$COLD,
     labels = sprintf("kältester Tag\n%s: %s °C",
                      de_date(yr$date[i_lo]), de_num(yr$temp_min_c[i_lo])))

# --- Legende -----------------------------------------------------------------
legend(
  "topleft", inset = c(0.005, 0.005), bty = "o", bg = WG$BACKGROUND,
  box.col = WG$GRID, box.lwd = 0.6, cex = 0.78, y.intersp = 1.35, seg.len = 1.4,
  legend = c(
    sprintf("Rekordspanne %d–%d", s$record_from, s$record_to),
    sprintf("Normalspanne %d–%d", s$reference_from, s$reference_to),
    sprintf("Tagesspanne %d", s$year),
    "über der Normalspanne", "unter der Normalspanne", "neuer Tagesrekord"
  ),
  pch = c(15, 15, NA, NA, NA, 21),
  lty = c(NA, NA, 1, 1, 1, NA),
  lwd = c(NA, NA, 3, 3, 3, 0.6),
  pt.cex = c(1.6, 1.6, NA, NA, NA, 0.7),
  pt.bg = c(NA, NA, NA, NA, NA, WG$WARM),
  col = c(WG$RECORD_BAND, WG$NORMAL_BAND, WG$BAR_NEUTRAL, WG$WARM, WG$COLD, "white")
)

# --- Titelblock und Fußzeile -------------------------------------------------
# outer = TRUE geht hier nicht, weil oma = 0 ist; stattdessen über die
# Zeilenposition im oberen Rand (line zählt von der Plotkante nach außen).
mtext(sprintf("%s · %d", s$station_name, s$year), side = 3, line = 5.4, adj = 0,
      cex = 1.85, font = 2, col = WG$TEXT)
mtext(wg_subtitle(s), side = 3, line = 3.6, adj = 0, cex = 0.92, col = WG$TEXT_MUTED)
mtext(wg_stats_line(s), side = 3, line = 2.1, adj = 0, cex = 0.85, col = WG$TEXT)
mtext(wg_footer(s, "base graphics"), side = 1, line = 2.0, adj = 0,
      cex = 0.65, col = WG$TEXT_MUTED)

invisible(dev.off())
cat("geschrieben:", path, "\n")
