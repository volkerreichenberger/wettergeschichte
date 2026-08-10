#!/usr/bin/env Rscript
# NYT-Klimadiagramm mit ggplot2.
#
# Dieselben Daten und Farben wie die Python-Varianten. ggplot2 baut das Bild
# aus Ebenen: zwei Flächen für Rekord- und Normalspanne, darüber die
# Tagesbalken, darüber die Rekordpunkte.
#
#   Rscript plots/R/nyt_ggplot2.R --station 4931 --year 2026

suppressPackageStartupMessages({
  library(ggplot2)
})

source(file.path(dirname(sub("^--file=", "",
  grep("^--file=", commandArgs(FALSE), value = TRUE)[1])), "wg_common.R"))

opts <- wg_args()
d <- wg_load(opts$station, opts$year, opts$derived)
clim <- d$clim; yr <- d$year; s <- d$summary

# --- Flächen und Balken ins lange Format bringen, damit die Legende entsteht ---
band_levels <- c(
  sprintf("Rekordspanne %d–%d", s$record_from, s$record_to),
  sprintf("Normalspanne %d–%d", s$reference_from, s$reference_to)
)
bands <- rbind(
  data.frame(doy = clim$doy, lo = clim$record_low, hi = clim$record_high, band = band_levels[1]),
  data.frame(doy = clim$doy, lo = clim$normal_low, hi = clim$normal_high, band = band_levels[2])
)
bands$band <- factor(bands$band, levels = band_levels)

bar_levels <- c(sprintf("Tagesspanne %d", s$year),
                "über der Normalspanne", "unter der Normalspanne")
bars <- rbind(
  data.frame(doy = yr$doy, lo = yr$bar_low,   hi = yr$bar_high, kind = bar_levels[1]),
  data.frame(doy = yr$doy, lo = yr$warm_from, hi = yr$warm_to,  kind = bar_levels[2]),
  data.frame(doy = yr$doy, lo = yr$cold_from, hi = yr$cold_to,  kind = bar_levels[3])
)
bars <- bars[!is.na(bars$lo) & !is.na(bars$hi), ]
# Reihenfolge bestimmt, was oben liegt: farbige Spitzen über dem grauen Balken.
bars$kind <- factor(bars$kind, levels = bar_levels)
bars <- bars[order(bars$kind), ]

# pandas schreibt Wahrheitswerte als "True"/"False" – in R sind das Strings.
hi_mask <- as.logical(yr$is_record_high)
lo_mask <- as.logical(yr$is_record_low)
# rep() statt Recycling: in einem Jahr ohne Kälterekord wäre die Auswahl leer,
# und data.frame() bricht bei 0 Zeilen gegen 1 Farbe ab.
records <- rbind(
  data.frame(doy = yr$doy[hi_mask], y = yr$temp_max_c[hi_mask],
             col = rep(WG$WARM, sum(hi_mask))),
  data.frame(doy = yr$doy[lo_mask], y = yr$temp_min_c[lo_mask],
             col = rep(WG$COLD, sum(lo_mask)))
)

ymin <- min(clim$record_low, yr$temp_min_c, na.rm = TRUE) - 2
# Oben etwas Luft für die Beschriftung des wärmsten Tages, sonst schneidet
# ggplot2 den Text an der Skalengrenze ab.
ymax <- max(clim$record_high, yr$temp_max_c, na.rm = TRUE) + 9
ybreaks <- seq(floor(ymin / 5) * 5, ceiling(ymax / 5) * 5, by = 5)

extremes <- data.frame(
  doy = c(yr$doy[which.max(yr$temp_max_c)], yr$doy[which.min(yr$temp_min_c)]),
  y   = c(max(yr$temp_max_c, na.rm = TRUE), min(yr$temp_min_c, na.rm = TRUE)),
  col = c(WG$WARM, WG$COLD)
)
extremes$label <- c(
  sprintf("wärmster Tag\n%s: %s °C",
          de_date(yr$date[which.max(yr$temp_max_c)]), de_num(extremes$y[1])),
  sprintf("kältester Tag\n%s: %s °C",
          de_date(yr$date[which.min(yr$temp_min_c)]), de_num(extremes$y[2]))
)
extremes$nudge_x <- c(-26, 28)
extremes$nudge_y <- c(6, -5)

p <- ggplot() +
  geom_ribbon(data = bands, aes(x = doy, ymin = lo, ymax = hi, fill = band)) +
  geom_vline(xintercept = MONTH_STARTS[-1], colour = WG$GRID, linewidth = 0.25) +
  geom_hline(yintercept = 0, colour = WG$GRID, linewidth = 0.35, linetype = "dashed") +
  geom_linerange(data = bars, aes(x = doy, ymin = lo, ymax = hi, colour = kind),
                 linewidth = 0.45) +
  geom_point(data = records, aes(x = doy, y = y), colour = records$col,
             size = 1.3, stroke = 0.3) +
  geom_segment(data = extremes,
               aes(x = doy + nudge_x, xend = doy, y = y + nudge_y, yend = y),
               colour = extremes$col, linewidth = 0.3) +
  geom_text(data = extremes, aes(x = doy + nudge_x, y = y + nudge_y, label = label),
            colour = extremes$col, size = 3.2, lineheight = 1.1,
            vjust = ifelse(extremes$nudge_y > 0, -0.1, 1.1)) +
  scale_fill_manual(values = stats::setNames(c(WG$RECORD_BAND, WG$NORMAL_BAND), band_levels),
                    name = NULL) +
  scale_colour_manual(values = stats::setNames(c(WG$BAR_NEUTRAL, WG$WARM, WG$COLD), bar_levels),
                      name = NULL) +
  guides(fill = guide_legend(order = 1), colour = guide_legend(order = 2)) +
  scale_x_continuous(breaks = MONTH_CENTERS, labels = MONTH_NAMES,
                     limits = c(1, MONTH_END), expand = c(0, 0)) +
  scale_y_continuous(breaks = ybreaks, labels = paste0(ybreaks, "°"),
                     limits = c(ymin, ymax)) +
  labs(
    title = sprintf("%s · %d", s$station_name, s$year),
    subtitle = paste(wg_subtitle(s), wg_stats_line(s), sep = "\n"),
    caption = wg_footer(s, "ggplot2"),
    x = NULL, y = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(
    plot.background = element_rect(fill = WG$BACKGROUND, colour = NA),
    panel.background = element_blank(),
    panel.grid.major.x = element_blank(),
    panel.grid.minor = element_blank(),
    panel.grid.major.y = element_line(colour = WG$GRID, linewidth = 0.25),
    plot.title = element_text(size = 24, face = "bold", margin = margin(b = 6)),
    plot.subtitle = element_text(size = 12, colour = WG$TEXT_MUTED, lineheight = 1.6,
                                 margin = margin(b = 14)),
    plot.caption = element_text(size = 8.5, colour = WG$TEXT_MUTED, hjust = 0,
                                margin = margin(t = 12)),
    plot.caption.position = "plot",
    plot.title.position = "plot",
    axis.text = element_text(size = 11, colour = WG$TEXT_MUTED),
    legend.position = "inside",
    legend.position.inside = c(0.09, 0.86),
    legend.background = element_rect(fill = WG$BACKGROUND, colour = WG$GRID, linewidth = 0.3),
    legend.key.size = unit(11, "pt"),
    legend.text = element_text(size = 9),
    legend.spacing.y = unit(1, "pt"),
    legend.margin = margin(6, 8, 6, 8),
    plot.margin = margin(18, 22, 12, 14)
  )

path <- wg_out("nyt_ggplot2", opts$station, opts$year, opts$output)
ggsave(path, p, width = opts$width, height = opts$height, dpi = opts$dpi,
       device = if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else NULL,
       bg = WG$BACKGROUND)
cat("geschrieben:", path, "\n")
