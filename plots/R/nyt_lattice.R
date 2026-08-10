#!/usr/bin/env Rscript
# NYT-Klimadiagramm mit lattice.
#
# lattice arbeitet nicht mit Ebenen, sondern mit einer Panel-Funktion: alles,
# was gezeichnet werden soll, steht in einem Block. Das ist kompakter als
# ggplot2, aber weniger leicht umzubauen.
#
#   Rscript plots/R/nyt_lattice.R --station 4931 --year 2026

suppressPackageStartupMessages({
  library(lattice)
  library(grid)
})

source(file.path(dirname(sub("^--file=", "",
  grep("^--file=", commandArgs(FALSE), value = TRUE)[1])), "wg_common.R"))

opts <- wg_args()
d <- wg_load(opts$station, opts$year, opts$derived)
clim <- d$clim; yr <- d$year; s <- d$summary

ymin <- min(clim$record_low, yr$temp_min_c, na.rm = TRUE) - 2
# Kopfraum für Legende und die Beschriftung des wärmsten Tages; lattice
# schneidet alles ab, was über die Panel-Grenze hinausragt.
ymax <- max(clim$record_high, yr$temp_max_c, na.rm = TRUE) + 11
ybreaks <- seq(floor(ymin / 5) * 5, ceiling(ymax / 5) * 5, by = 5)

hi_mask <- as.logical(yr$is_record_high)
lo_mask <- as.logical(yr$is_record_low)

panel_climate <- function(...) {
  # Rekord- und Normalspanne als geschlossene Polygone
  panel.polygon(c(clim$doy, rev(clim$doy)), c(clim$record_high, rev(clim$record_low)),
                col = WG$RECORD_BAND, border = NA)
  panel.polygon(c(clim$doy, rev(clim$doy)), c(clim$normal_high, rev(clim$normal_low)),
                col = WG$NORMAL_BAND, border = NA)

  panel.abline(h = ybreaks, col = WG$GRID, lwd = 0.5)
  panel.abline(v = MONTH_STARTS[-1], col = WG$GRID, lwd = 0.7)
  panel.abline(h = 0, col = WG$GRID, lwd = 0.8, lty = 2)

  panel.segments(yr$doy, yr$bar_low, yr$doy, yr$bar_high, col = WG$BAR_NEUTRAL, lwd = 1.2)
  panel.segments(yr$doy, yr$warm_from, yr$doy, yr$warm_to, col = WG$WARM, lwd = 1.2)
  panel.segments(yr$doy, yr$cold_from, yr$doy, yr$cold_to, col = WG$COLD, lwd = 1.2)

  panel.points(yr$doy[hi_mask], yr$temp_max_c[hi_mask], pch = 21,
               fill = WG$WARM, col = "white", cex = 0.6, lwd = 0.6)
  panel.points(yr$doy[lo_mask], yr$temp_min_c[lo_mask], pch = 21,
               fill = WG$COLD, col = "white", cex = 0.6, lwd = 0.6)

  # Extremwerte beschriften
  i_hi <- which.max(yr$temp_max_c); i_lo <- which.min(yr$temp_min_c)
  panel.segments(yr$doy[i_hi] - 26, yr$temp_max_c[i_hi] + 6,
                 yr$doy[i_hi], yr$temp_max_c[i_hi], col = WG$WARM, lwd = 0.6)
  panel.text(yr$doy[i_hi] - 26, yr$temp_max_c[i_hi] + 6.5, adj = c(0.5, 0),
             label = sprintf("wärmster Tag\n%s: %s °C",
                             de_date(yr$date[i_hi]), de_num(yr$temp_max_c[i_hi])),
             col = WG$WARM, cex = 0.75)
  panel.segments(yr$doy[i_lo] + 28, yr$temp_min_c[i_lo] - 5,
                 yr$doy[i_lo], yr$temp_min_c[i_lo], col = WG$COLD, lwd = 0.6)
  panel.text(yr$doy[i_lo] + 28, yr$temp_min_c[i_lo] - 5.5, adj = c(0.5, 1),
             label = sprintf("kältester Tag\n%s: %s °C",
                             de_date(yr$date[i_lo]), de_num(yr$temp_min_c[i_lo])),
             col = WG$COLD, cex = 0.75)

  # Legende von Hand – lattice kennt die selbst gezeichneten Ebenen nicht.
  legend_items <- list(
    list(type = "fill", col = WG$RECORD_BAND,
         label = sprintf("Rekordspanne %d–%d", s$record_from, s$record_to)),
    list(type = "fill", col = WG$NORMAL_BAND,
         label = sprintf("Normalspanne %d–%d", s$reference_from, s$reference_to)),
    list(type = "line", col = WG$BAR_NEUTRAL, label = sprintf("Tagesspanne %d", s$year)),
    list(type = "line", col = WG$WARM, label = "über der Normalspanne"),
    list(type = "line", col = WG$COLD, label = "unter der Normalspanne"),
    list(type = "point", col = WG$WARM, label = "neuer Tagesrekord")
  )
  x0 <- 8; y0 <- ymax - 1.5; dy <- (ymax - ymin) / 26
  grid.rect(x = unit(x0 - 4, "native"), y = unit(y0 + dy * 0.9, "native"),
            width = unit(96, "native"), height = unit(dy * (length(legend_items) + 0.9), "native"),
            just = c("left", "top"),
            gp = gpar(fill = WG$BACKGROUND, col = WG$GRID, alpha = 0.95, lwd = 0.6))
  for (i in seq_along(legend_items)) {
    it <- legend_items[[i]]; y <- y0 - (i - 1) * dy
    if (it$type == "fill") {
      panel.rect(x0, y - dy * 0.22, x0 + 9, y + dy * 0.22, col = it$col, border = NA)
    } else if (it$type == "line") {
      panel.segments(x0 + 4, y - dy * 0.3, x0 + 4, y + dy * 0.3, col = it$col, lwd = 2.2)
    } else {
      panel.points(x0 + 4.5, y, pch = 21, fill = it$col, col = "white", cex = 0.7, lwd = 0.6)
    }
    panel.text(x0 + 12, y, it$label, adj = c(0, 0.5), cex = 0.72, col = WG$TEXT)
  }
}

p <- xyplot(
  temp_max_c ~ doy, data = yr,
  xlim = c(1, MONTH_END), ylim = c(ymin, ymax),
  panel = panel_climate,
  xlab = NULL, ylab = NULL,
  scales = list(
    x = list(at = MONTH_CENTERS, labels = MONTH_NAMES, tck = 0, cex = 0.95),
    y = list(at = ybreaks, labels = paste0(ybreaks, "°"), tck = 0, cex = 0.95)
  ),
  par.settings = list(
    background = list(col = WG$BACKGROUND),
    axis.line = list(col = "transparent"),
    axis.text = list(col = WG$TEXT_MUTED),
    # Platz für den Titelblock, der außerhalb des Panels gezeichnet wird.
    layout.heights = list(top.padding = 15, bottom.padding = 5)
  )
)

path <- wg_out("nyt_lattice", opts$station, opts$year, opts$output)
wg_png(path, opts$width, opts$height, opts$dpi)
print(p)

# Titelblock und Fußzeile liegen außerhalb des Panels und werden direkt
# ins Gerät gezeichnet.
grid.text(sprintf("%s · %d", s$station_name, s$year),
          x = unit(14, "pt"), y = unit(1, "npc") - unit(24, "pt"),
          just = c("left", "top"), gp = gpar(fontsize = 24, fontface = "bold", col = WG$TEXT))
grid.text(wg_subtitle(s), x = unit(14, "pt"), y = unit(1, "npc") - unit(58, "pt"),
          just = c("left", "top"), gp = gpar(fontsize = 12, col = WG$TEXT_MUTED))
grid.text(wg_stats_line(s), x = unit(14, "pt"), y = unit(1, "npc") - unit(80, "pt"),
          just = c("left", "top"), gp = gpar(fontsize = 11, col = WG$TEXT))
grid.text(wg_footer(s, "lattice"), x = unit(14, "pt"), y = unit(14, "pt"),
          just = c("left", "bottom"), gp = gpar(fontsize = 8.5, col = WG$TEXT_MUTED))

invisible(dev.off())
cat("geschrieben:", path, "\n")
