"""Katalog der DWD-Tagesdatensätze (CDC open data) und ihrer Spalten.

Alle hier gelisteten Datensätze liegen als Tageswerte auf
https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/
und decken für die Stationen 4928 / 4931 mindestens zehn Jahre ab.

Für jeden Datensatz wird festgehalten:

* ``path``      Unterverzeichnis auf dem DWD-Server
* ``subdirs``   ``historical`` / ``recent`` (bzw. ``""`` wenn es nur eine Datei gibt)
* ``pattern``   Regex für den Dateinamen, ``{sid}`` = fünfstellige Stations-ID
* ``columns``   Rohspalte -> sprechender Spaltenname der Ausgabe-CSV
* ``qn``        Name der Qualitätsniveau-Spalte(n) in der Rohdatei
"""

from __future__ import annotations

from dataclasses import dataclass, field

BASE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/"
    "observations_germany/climate/daily"
)

STATIONS = {
    4928: "Stuttgart (Schnarrenberg)",
    4931: "Stuttgart-Echterdingen",
}

#: DWD kodiert fehlende Werte durchgängig so.
MISSING = -999


@dataclass(frozen=True)
class Dataset:
    key: str
    path: str
    label: str
    pattern: str
    columns: dict[str, str]
    qn: tuple[str, ...] = ()
    subdirs: tuple[str, ...] = ("historical", "recent")
    #: Datensätze ohne ``recent``-Verzeichnis werden bei jedem Lauf komplett
    #: geprüft, aber nur bei geändertem Last-Modified neu geladen.
    note: str = ""

    def filename_regex(self, station_id: int) -> str:
        return self.pattern.format(sid=f"{station_id:05d}")

    def url(self, subdir: str) -> str:
        return f"{BASE_URL}/{self.path}/{subdir}/" if subdir else f"{BASE_URL}/{self.path}/"


DATASETS: dict[str, Dataset] = {}


def _add(ds: Dataset) -> None:
    DATASETS[ds.key] = ds


_add(
    Dataset(
        key="kl",
        path="kl",
        label="Klima – Basisparameter (Temperatur, Niederschlag, Wind, Sonne, Druck)",
        pattern=r"tageswerte_KL_{sid}_.*\.zip",
        qn=("QN_3", "QN_4"),
        columns={
            "FX": "wind_gust_max_ms",
            "FM": "wind_speed_mean_ms",
            "RSK": "precip_mm",
            "RSKF": "precip_form",
            "SDK": "sunshine_h",
            "SHK_TAG": "snow_depth_cm",
            "NM": "cloud_cover_okta",
            "VPM": "vapour_pressure_hpa",
            "PM": "pressure_hpa",
            "TMK": "temp_mean_c",
            "UPM": "humidity_pct",
            "TXK": "temp_max_c",
            "TNK": "temp_min_c",
            "TGK": "temp_min_ground_c",
        },
    )
)

_add(
    Dataset(
        key="more_precip",
        path="more_precip",
        label="Niederschlag – erweiterte Parameter (inkl. Neuschnee)",
        pattern=r"tageswerte_RR_{sid}_.*\.zip",
        qn=("QN_6",),
        columns={
            "RS": "precip_rr_mm",
            "RSF": "precip_rr_form",
            "SH_TAG": "snow_depth_rr_cm",
            "NSH_TAG": "fresh_snow_cm",
        },
    )
)

_add(
    Dataset(
        key="soil_temperature",
        path="soil_temperature",
        label="Erdbodentemperaturen in 2–50 cm Tiefe",
        pattern=r"tageswerte_EB_{sid}_.*\.zip",
        qn=("QN_2",),
        columns={
            "V_TE002M": "soil_temp_2cm_c",
            "V_TE005M": "soil_temp_5cm_c",
            "V_TE010M": "soil_temp_10cm_c",
            "V_TE020M": "soil_temp_20cm_c",
            "V_TE050M": "soil_temp_50cm_c",
        },
    )
)

_add(
    Dataset(
        key="solar",
        path="solar",
        label="Strahlung (global, diffus, atmosphärische Gegenstrahlung)",
        pattern=r"tageswerte_ST_{sid}_row\.zip",
        subdirs=("",),
        qn=("QN_592",),
        columns={
            "ATMO_STRAHL": "radiation_longwave_jcm2",
            "FD_STRAHL": "radiation_diffuse_jcm2",
            "FG_STRAHL": "radiation_global_jcm2",
            "SD_STRAHL": "sunshine_solar_h",
        },
        note="nur eine Gesamtdatei ('row'), es gibt kein recent/historical",
    )
)

_add(
    Dataset(
        key="weather_phenomena",
        path="weather_phenomena",
        label="Wettererscheinungen (Nebel, Gewitter, Sturm, Tau, Reif, Hagel …)",
        pattern=r"wetter_tageswerte_{sid}_.*\.zip",
        qn=("QN_4",),
        columns={
            "NEBEL": "wx_fog",
            "GEWITTER": "wx_thunderstorm",
            "STURM_6": "wx_storm_bft6",
            "STURM_8": "wx_storm_bft8",
            "TAU": "wx_dew",
            "GLATTEIS": "wx_glaze",
            "REIF": "wx_hoarfrost",
            "GRAUPEL": "wx_graupel",
            "HAGEL": "wx_hail",
        },
    )
)

_add(
    Dataset(
        key="more_weather_phenomena",
        path="more_weather_phenomena",
        label="Wettererscheinungen an Niederschlagsstationen",
        pattern=r"wetter_tageswerte_RR_{sid}_.*\.zip",
        qn=("QN_6",),
        columns={
            "RR_GRAUPEL": "wxrr_graupel",
            "RR_HAGEL": "wxrr_hail",
            "RR_NEBEL": "wxrr_fog",
            "RR_GEWITTER": "wxrr_thunderstorm",
        },
    )
)

_add(
    Dataset(
        key="water_equiv",
        path="water_equiv",
        label="Schneehöhe und Wasseräquivalent der Schneedecke",
        pattern=r"tageswerte_Wa_{sid}_.*\.zip",
        qn=("QN_6",),
        columns={
            "ASH_6": "snow_depth_we_cm",
            "SH_TAG": "snow_depth_total_cm",
            "WASH_6": "water_equiv_total_mm",
            "WAAS_6": "water_equiv_snowpack_mm",
        },
        note="wird für 4928/4931 seit 2015 bzw. 1999 nicht mehr fortgeführt",
    )
)


#: Reihenfolge der Spalten in der zusammengeführten Tages-CSV.
MERGED_COLUMN_ORDER: list[str] = ["station_id", "date"]
for _ds in DATASETS.values():
    MERGED_COLUMN_ORDER.extend(_ds.columns.values())


#: Kurzbeschreibungen der Ausgabespalten (für data_dictionary.csv).
COLUMN_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "wind_gust_max_ms": ("m/s", "Tagesmaximum der Windspitze"),
    "wind_speed_mean_ms": ("m/s", "Tagesmittel der Windgeschwindigkeit"),
    "precip_mm": ("mm", "Tagessumme des Niederschlags"),
    "precip_form": ("Code", "Niederschlagsform (0 kein Nd., 1 nur Regen, 4 unbekannt, 6 Regen, 7 Schnee, 8 Regen+Schnee, 9 ohne Messung)"),
    "sunshine_h": ("h", "Tagessumme der Sonnenscheindauer"),
    "snow_depth_cm": ("cm", "Schneehöhe (Tageswert)"),
    "cloud_cover_okta": ("1/8", "Tagesmittel des Bedeckungsgrades"),
    "vapour_pressure_hpa": ("hPa", "Tagesmittel des Dampfdrucks"),
    "pressure_hpa": ("hPa", "Tagesmittel des Luftdrucks"),
    "temp_mean_c": ("°C", "Tagesmittel der Lufttemperatur in 2 m"),
    "humidity_pct": ("%", "Tagesmittel der relativen Feuchte"),
    "temp_max_c": ("°C", "Tagesmaximum der Lufttemperatur in 2 m"),
    "temp_min_c": ("°C", "Tagesminimum der Lufttemperatur in 2 m"),
    "temp_min_ground_c": ("°C", "Tagesminimum der Lufttemperatur in 5 cm"),
    "precip_rr_mm": ("mm", "Niederschlagshöhe (Niederschlagsmessnetz)"),
    "precip_rr_form": ("Code", "Niederschlagsform (Niederschlagsmessnetz)"),
    "snow_depth_rr_cm": ("cm", "Schneehöhe (Niederschlagsmessnetz)"),
    "fresh_snow_cm": ("cm", "Neuschneehöhe"),
    "soil_temp_2cm_c": ("°C", "Erdbodentemperatur in 2 cm Tiefe"),
    "soil_temp_5cm_c": ("°C", "Erdbodentemperatur in 5 cm Tiefe"),
    "soil_temp_10cm_c": ("°C", "Erdbodentemperatur in 10 cm Tiefe"),
    "soil_temp_20cm_c": ("°C", "Erdbodentemperatur in 20 cm Tiefe"),
    "soil_temp_50cm_c": ("°C", "Erdbodentemperatur in 50 cm Tiefe"),
    "radiation_longwave_jcm2": ("J/cm²", "Tagessumme der atmosphärischen Gegenstrahlung"),
    "radiation_diffuse_jcm2": ("J/cm²", "Tagessumme der diffusen Himmelsstrahlung"),
    "radiation_global_jcm2": ("J/cm²", "Tagessumme der Globalstrahlung"),
    "sunshine_solar_h": ("h", "Tagessumme der Sonnenscheindauer (Strahlungsmessnetz)"),
    "wx_fog": ("0/1", "Nebel beobachtet"),
    "wx_thunderstorm": ("0/1", "Gewitter beobachtet"),
    "wx_storm_bft6": ("0/1", "Sturm ab 6 Bft beobachtet"),
    "wx_storm_bft8": ("0/1", "Sturm ab 8 Bft beobachtet"),
    "wx_dew": ("0/1", "Tau beobachtet"),
    "wx_glaze": ("0/1", "Glatteis beobachtet"),
    "wx_hoarfrost": ("0/1", "Reif beobachtet"),
    "wx_graupel": ("0/1", "Graupel beobachtet"),
    "wx_hail": ("0/1", "Hagel beobachtet"),
    "wxrr_graupel": ("0/1", "Graupel (Niederschlagsmessnetz)"),
    "wxrr_hail": ("0/1", "Hagel (Niederschlagsmessnetz)"),
    "wxrr_fog": ("0/1", "Nebel (Niederschlagsmessnetz)"),
    "wxrr_thunderstorm": ("0/1", "Gewitter (Niederschlagsmessnetz)"),
    "snow_depth_we_cm": ("cm", "Schneehöhe zum Messtermin"),
    "snow_depth_total_cm": ("cm", "Gesamtschneehöhe"),
    "water_equiv_total_mm": ("mm", "Gesamtwasseräquivalent der Schneedecke"),
    "water_equiv_snowpack_mm": ("mm", "Wasseräquivalent der Schneedecke (Messtermin)"),
}
