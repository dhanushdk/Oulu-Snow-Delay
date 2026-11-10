from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
CLEAN_FILE = PROJECT_DIR / "data" / "clean" / "oulu_snow_clean.csv"

AIRPORT_FILE = RAW_DIR / "oulu_airport_2022-09-01_2026-11-09.csv"
PELLONPAA_FILE = RAW_DIR / "oulu_oulunsalo_pellonpaa_2022-09-01_2024-12-03.csv"
KAUKOVAINIO_FILE = RAW_DIR / "oulu_kaukovainio_2023-11-09_2026-11-09.csv"

STATION_SWITCH_DATE = pd.Timestamp("2024-09-01")

COLUMN_NAMES = {
    "Average temperature [°C]": "AvgTemp_C",
    "Minimum temperature [°C]": "MinTemp_C",
    "Maximum temperature [°C]": "MaxTemp_C",
    "Snow depth [cm]": "SnowDepth_cm",
    "Precipitation amount [mm]": "Precip_mm",
}


def load_fmi_file(path: Path) -> pd.DataFrame:
    """Read one FMI daily file and return it with a Date index and numeric values."""
    df = pd.read_csv(path)

    df["Date"] = pd.to_datetime(df[["Year", "Month", "Day"]])

    df = df.rename(columns=COLUMN_NAMES)

    for column in COLUMN_NAMES.values():
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df.set_index("Date")


def season_start_year(dates: pd.DatetimeIndex) -> pd.Index:
    """A season runs from 1 Sep to 31 Aug. Jan-Aug belong to the previous year's season."""
    return dates.year.where(dates.month >= 9, dates.year - 1)


def main() -> None:
    airport = load_fmi_file(AIRPORT_FILE)
    pellonpaa = load_fmi_file(PELLONPAA_FILE)
    kaukovainio = load_fmi_file(KAUKOVAINIO_FILE)

    weather = airport[["AvgTemp_C", "MinTemp_C", "MaxTemp_C"]].copy()

    snow_columns = ["SnowDepth_cm", "Precip_mm"]
    snow_early = pellonpaa.loc[pellonpaa.index < STATION_SWITCH_DATE, snow_columns].copy()
    snow_early["SnowStation"] = "Oulu Oulunsalo Pellonpää"

    snow_late = kaukovainio.loc[kaukovainio.index >= STATION_SWITCH_DATE, snow_columns].copy()
    snow_late["SnowStation"] = "Oulu Kaukovainio"

    snow = pd.concat([snow_early, snow_late])

    weather = weather.join(snow)

    weather["SnowDepth_cm"] = weather["SnowDepth_cm"].clip(lower=0)
    weather["Precip_mm"] = weather["Precip_mm"].clip(lower=0)

    start_year = season_start_year(weather.index)
    weather["Season"] = [f"{y}/{str(y + 1)[2:]}" for y in start_year]
    season_start = pd.to_datetime([f"{y}-09-01" for y in start_year])
    weather["DayOfSeason"] = (weather.index - season_start).days + 1

    weather["HasSnow"] = (weather["SnowDepth_cm"] >= 1).astype(int)
    weather["IsFrostDay"] = (weather["AvgTemp_C"] < 0).astype(int)

    def precip_type(row: pd.Series) -> str:
        if pd.isna(row["Precip_mm"]) or row["Precip_mm"] == 0:
            return "None"
        return "Snow" if row["AvgTemp_C"] <= 0 else "Rain"

    weather["PrecipType"] = weather.apply(precip_type, axis=1)
    weather["TempStation"] = "Oulu airport"

    weather = weather.reset_index()
    weather["Date"] = weather["Date"].dt.strftime("%Y-%m-%d")
    CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(CLEAN_FILE, index=False)

    print(f"Saved {len(weather)} rows to {CLEAN_FILE}")
    print(f"Date range: {weather['Date'].min()} to {weather['Date'].max()}")
    print("Missing values per column:")
    print(weather.isna().sum()[weather.isna().sum() > 0].to_string() or "  none")


if __name__ == "__main__":
    main()
