#!/usr/bin/env Rscript
# Fünf Jahre im direkten Vergleich, mit ggplot2 und patchwork.
#
# Oben das 31-Tage-Mittel der Tagesmitteltemperatur je Jahr, unten der seit
# Jahresbeginn aufsummierte Niederschlag. Die Kennzahlen rechts sind auf den
# Stichtag des laufenden Jahres gekürzt – sonst vergleicht man ein Rumpfjahr
# mit vollen Jahren.
#
#   Rscript plots/R/fuenf_jahre_ggplot2.R --station 4931 --year 2026

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
})

source(file.path(dirname(sub("^--file=", "",
  grep("^--file=", commandArgs(FALSE), value = TRUE)[1])), "wg_common.R"))

opts <- wg_args(list(years = 5L, height = 10))
d <- wg_load(opts$station, opts$year, opts$derived)
clim <- d$clim; yr <- d$year; rec <- d$recent; s <- d$summary

years <- utils::tail(sort(unique(rec$year)), opts$years)
rec <- rec[rec$year %in% years, ]
rec$year_f <- factor(rec$year, levels = years)
pal <- stats::setNames(utils::tail(YEAR_COLORS, length(years)), as.character(years))
newest <- max(years); previous <- sort(years, decreasing = TRUE)[2]
cutoff <- max(yr$doy)

# --- faire Kennzahlen: alle Jahre nur bis zum Stichtag ----------------------
sub <- rec[rec$doy <= cutoff, ]
stats_tab <- data.frame(
  year   = years,
  temp   = sapply(years, function(y) mean(sub$temp_mean_c[sub$year == y], na.rm = TRUE)),
  precip = sapply(years, function(y) sum(sub$precip_mm[sub$year == y], na.rm = TRUE)),
  hot    = sapply(years, function(y) sum(sub$temp_max_c[sub$year == y] >= 30, na.rm = TRUE))
)
rownames(stats_tab) <- as.character(stats_tab$year)
diff_last <- stats_tab[as.character(newest), "temp"] - stats_tab[as.character(previous), "temp"]

base_theme <- theme_minimal(base_size = 13) +
  theme(
    plot.background = element_rect(fill = WG$BACKGROUND, colour = NA),
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = WG$GRID, linewidth = 0.25),
    axis.text = element_text(size = 11, colour = WG$TEXT_MUTED),
    axis.title.y = element_text(size = 10.5, colour = WG$TEXT_MUTED),
    legend.position = "none",
    plot.margin = margin(4, 10, 4, 4)
  )

label_last <- function(df, ycol) {
  cur <- df[df$year == newest & !is.na(df[[ycol]]), ]
  cur[which.max(cur$doy), ]
}

# --- oben: geglättete Temperatur --------------------------------------------
temp_df <- rec[!is.na(rec$temp_smooth), ]
p_temp <- ggplot() +
  geom_line(data = clim, aes(doy, normal_mean), colour = WG$TEXT_MUTED,
            linewidth = 0.55, linetype = "dashed") +
  annotate("text", x = MONTH_STARTS[10],
           y = clim$normal_mean[clim$doy == MONTH_STARTS[10]] - 1.6,
           label = sprintf("Normal %d–%d", s$reference_from, s$reference_to),
           colour = WG$TEXT_MUTED, size = 3.2) +
  geom_vline(xintercept = MONTH_STARTS[-1], colour = WG$GRID, linewidth = 0.25) +
  geom_hline(yintercept = 0, colour = WG$GRID, linewidth = 0.3) +
  geom_line(data = temp_df[temp_df$year != newest, ],
            aes(doy, temp_smooth, colour = year_f, group = year_f), linewidth = 0.65) +
  geom_line(data = temp_df[temp_df$year == newest, ],
            aes(doy, temp_smooth, colour = year_f), linewidth = 1.2, lineend = "round") +
  geom_text(data = label_last(temp_df, "temp_smooth"),
            aes(doy, temp_smooth, label = year), colour = pal[as.character(newest)],
            hjust = -0.25, size = 4.2, fontface = "bold") +
  scale_colour_manual(values = pal) +
  scale_x_continuous(breaks = MONTH_CENTERS, labels = NULL, limits = c(1, MONTH_END),
                     expand = c(0, 0)) +
  labs(x = NULL, y = "31-Tage-Mittel der Tagesmitteltemperatur (°C)") +
  base_theme

# --- unten: kumulierter Niederschlag ----------------------------------------
p_prec <- ggplot() +
  geom_line(data = data.frame(doy = clim$doy, cum = cumsum(clim$normal_precip)),
            aes(doy, cum), colour = WG$TEXT_MUTED, linewidth = 0.55, linetype = "dashed") +
  geom_vline(xintercept = MONTH_STARTS[-1], colour = WG$GRID, linewidth = 0.25) +
  geom_line(data = rec[rec$year != newest, ],
            aes(doy, precip_cum, colour = year_f, group = year_f), linewidth = 0.6) +
  geom_line(data = rec[rec$year == newest, ],
            aes(doy, precip_cum, colour = year_f), linewidth = 1.1) +
  geom_text(data = label_last(rec, "precip_cum"),
            aes(doy, precip_cum, label = year), colour = pal[as.character(newest)],
            hjust = -0.25, size = 3.8, fontface = "bold") +
  scale_colour_manual(values = pal) +
  scale_x_continuous(breaks = MONTH_CENTERS, labels = MONTH_NAMES, limits = c(1, MONTH_END),
                     expand = c(0, 0)) +
  labs(x = NULL, y = "Niederschlag seit Jahresbeginn (mm)") +
  base_theme

# --- rechts: Kennzahlen als eigenes, leeres Panel ----------------------------
rows <- rev(seq_len(nrow(stats_tab)))
tab <- data.frame(
  y = rows,
  year = as.character(stats_tab$year),
  temp = de_num(stats_tab$temp),
  delta = vapply(stats_tab$year, function(y) {
    prev <- as.character(y - 1)
    if (prev %in% rownames(stats_tab)) {
      de_num(stats_tab[as.character(y), "temp"] - stats_tab[prev, "temp"], sign = TRUE)
    } else "–"
  }, character(1)),
  precip = sprintf("%.0f", stats_tab$precip),
  hot = sprintf("%d", stats_tab$hot),
  colour = pal[as.character(stats_tab$year)],
  face = ifelse(stats_tab$year == newest, "bold", "plain"),
  stringsAsFactors = FALSE
)
delta_colour <- ifelse(startsWith(tab$delta, "+"), WG$WARM,
                       ifelse(tab$delta == "–", WG$TEXT, WG$COLD))

# Die y-Achse ist bewusst viel höher als die Tabelle Zeilen hat: sonst zieht
# ggplot2 die fünf Zeilen über die gesamte Panelhöhe auseinander.
p_tab <- ggplot() +
  xlim(0, 1) + ylim(-19, nrow(tab) + 3.4) +
  annotate("text", x = 0, y = nrow(tab) + 3.0, hjust = 0, size = 4.0, fontface = "bold",
           label = sprintf("1. Januar bis %s", de_date(max(yr$date)))) +
  annotate("text", x = 0, y = nrow(tab) + 2.4, hjust = 0, size = 3.1, colour = WG$TEXT_MUTED,
           label = "alle Jahre auf denselben Zeitraum gekürzt") +
  annotate("text", x = c(0, 0.30, 0.55, 0.85), y = nrow(tab) + 1.3, hjust = 0,
           size = 3.2, colour = WG$TEXT_MUTED,
           label = c("Jahr", "Ø °C", "Δ Vorjahr", "mm")) +
  geom_text(data = tab, aes(0,    y, label = year),   hjust = 0, size = 3.7,
            colour = tab$colour, fontface = tab$face) +
  geom_text(data = tab, aes(0.30, y, label = temp),   hjust = 0, size = 3.7, fontface = tab$face) +
  geom_text(data = tab, aes(0.55, y, label = delta),  hjust = 0, size = 3.7,
            colour = delta_colour, fontface = tab$face) +
  geom_text(data = tab, aes(0.85, y, label = precip), hjust = 0, size = 3.7, fontface = tab$face) +
  annotate("text", x = 0, y = -1.0, hjust = 0, vjust = 1, size = 3.5, lineheight = 1.5,
           label = sprintf("%d liegt bis hierher %s K\n%s %d.\n\nZwischen dem wärmsten und dem\nkühlsten der %d Jahre liegen %s K.",
                           newest, de_num(abs(diff_last)),
                           if (diff_last > 0) "über" else "unter", previous,
                           length(years),
                           de_num(max(stats_tab$temp) - min(stats_tab$temp)))) +
  annotate("text", x = 0, y = -8.5, hjust = 0, vjust = 1, size = 3.2, lineheight = 1.6,
           colour = WG$TEXT_MUTED,
           label = paste0("Hitzetage (Tmax ≥ 30 °C)\n",
                          paste(sprintf("%d:  %d Tage", rev(stats_tab$year), rev(stats_tab$hot)),
                                collapse = "\n"))) +
  theme_void() +
  theme(plot.background = element_rect(fill = WG$BACKGROUND, colour = NA),
        plot.margin = margin(4, 4, 4, 14))

layout <- ((p_temp / p_prec) + plot_layout(heights = c(2.1, 1)) | p_tab) +
  plot_layout(widths = c(4, 1)) +
  plot_annotation(
    title = sprintf("%s · die letzten %d Jahre", s$station_name, length(years)),
    subtitle = sprintf(paste0("Ist %d wirklich wärmer als %d? 31-Tage-Mittel der ",
                              "Tagesmitteltemperatur und kumulierter Niederschlag"),
                       newest, previous),
    caption = wg_footer(s, "ggplot2 + patchwork"),
    theme = theme(
      plot.background = element_rect(fill = WG$BACKGROUND, colour = NA),
      plot.title = element_text(size = 24, face = "bold", margin = margin(b = 6)),
      plot.subtitle = element_text(size = 12, colour = WG$TEXT_MUTED, margin = margin(b = 14)),
      plot.caption = element_text(size = 8.5, colour = WG$TEXT_MUTED, hjust = 0,
                                  margin = margin(t = 12)),
      plot.caption.position = "plot",
      plot.title.position = "plot",
      plot.margin = margin(18, 22, 12, 14)
    )
  )

path <- wg_out("fuenf_jahre_ggplot2", opts$station, opts$year, opts$output)
ggsave(path, layout, width = opts$width, height = opts$height, dpi = opts$dpi,
       device = if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else NULL,
       bg = WG$BACKGROUND)
cat("geschrieben:", path, "\n")
