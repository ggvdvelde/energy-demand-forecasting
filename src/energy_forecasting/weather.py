import requests
import xarray as xr
from io import BytesIO
import time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from pathlib import Path


def _gdex_file_exists(run_date: str, forecast_hour: int) -> bool:
    year = run_date[:4]
    
    catalog_url = (
        "https://tds.gdex.ucar.edu/thredds/catalog/files/g/d084001/"
        f"{year}/{run_date}/catalog.html"
        )
    
    response = requests.get(catalog_url, timeout=30)
    response.raise_for_status()
    
    filename = (
        f"gfs.0p25.{run_date}00.f{forecast_hour:03d}.grib2"
        )
    
    return filename in response.text


def download_gfs_run(run_date:str,
                     forecast_hours: range = range(21, 49, 3), 
                     max_workers: int = 4) -> xr.Dataset:
    
    """Download the 00 UTC run, with lead times from 21 to 48 hours."""
    
    params = {
        "var": "Temperature_height_above_ground",
        "north": 44.5,
        "south": 35.0,
        "west": -10.0,
        "east": 4.5,
        "vertCoord": 2,
        "accept": "netCDF",
    }
    base_url = (
        "https://tds.gdex.ucar.edu/thredds/ncss/grid/files/g/d084001/"
        f"{run_date[:4]}/{run_date}/"
        f"gfs.0p25.{run_date}00.f"
        )

    def download_hour(fh):
        url = f"{base_url}{fh:03d}.grib2"
        for attempt in range(3):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=60
                    )

                response.raise_for_status()

                # Check that the response is actually a readable NetCDF
                
                with xr.open_dataset(
                    BytesIO(response.content),
                    engine="scipy"
                    ) as ds:
                    ds.load()

                return response.content

            except (requests.RequestException, OSError, IndexError, ValueError, KeyError) as e:

                print(
                    f"Retry run={run_date}, fh={fh}, "
                    f"attempt={attempt + 1}/3"
                    )

                if attempt == 2:
                    if isinstance(e, requests.HTTPError):
                        status = e.response.status_code

                        if status in (400, 404):
                            if _gdex_file_exists(run_date, fh):
                                return None

                    raise

                time.sleep(2 ** attempt)

    # Limit simultaneous requests; map preserves the forecast-hour order.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        contents = list(executor.map(download_hour, forecast_hours))

    weather_list = []
    for fh, content in zip(forecast_hours, contents):
        if content is None:
            continue
        # Load the small grid into memory before closing its NetCDF reader.
        with xr.open_dataset(BytesIO(content), engine="scipy") as ds:
            ds = ds.load()
            rename_dims = {
                dim: "datetime_utc"
                for dim in ds["Temperature_height_above_ground"].dims
                if dim.startswith("time")
            }
            ds=ds.rename(rename_dims)
            ds = ds.assign_coords(forecast_hour=("datetime_utc", [fh]))
            weather_list.append(ds)

    if not weather_list:
        raise RuntimeError(f"No forecast hours downloaded for run {run_date}")
    
    # Include every lead time, keeping the same output variables as before.
    weather_data = xr.concat(
        weather_list,
        dim="datetime_utc",
        data_vars="all",
        coords="minimal",
        compat="equals",
        join="exact",
    ).rename({"Temperature_height_above_ground": "temperature_K"})
    weather_data["longitude"] = weather_data["longitude"] - 360

    vertical_dims = [
    dim
    for dim in weather_data["temperature_K"].dims
    if dim not in {"datetime_utc", "latitude", "longitude"}
    ]

    for dim in vertical_dims:
        if weather_data.sizes[dim] == 1:
            weather_data = weather_data.squeeze(dim, drop=True)

    return weather_data

def download_gfs_month(year, month):

    missing_leads = []

    previous_day = (
        pd.Timestamp(f"{year}{month}01") - pd.Timedelta(days=1)
        ).strftime("%Y%m%d")
    
    run_dates=pd.date_range(start=previous_day, periods = pd.Period(f"{year}{month}01").days_in_month, freq="D")
    monthly_runs = []

    for run_date in run_dates:
        run_str = run_date.strftime("%Y%m%d")

        ds = download_gfs_run(run_str)
        ds = ds.swap_dims({"datetime_utc": "forecast_hour"})

        expected_hours = list(range(21, 49, 3))
        available_hours = ds["forecast_hour"].values.tolist()

        missing_hours = [
            fh for fh in expected_hours
            if fh not in available_hours
            ]

        for fh in missing_hours:
            missing_leads.append((run_str, fh))

        ds = ds.reindex(forecast_hour=expected_hours)

        run_time = pd.Timestamp(ds["reftime"].values)
        ds = ds.drop_vars(
            ["datetime_utc", "reftime", "LatLon_721X1440-0p13S-180p00E",],
            errors="ignore",
            )
        ds = ds.expand_dims(run_time_utc=[run_time])
        monthly_runs.append(ds)

    if len(missing_leads) > 4:
        raise RuntimeError(
            f"Too many missing leads in {year}-{month}: {missing_leads}"
            )

    if len(monthly_runs) != len(run_dates):
        raise RuntimeError(
            f"Incomplete month {year}-{month}: "
            f"{len(monthly_runs)}/{len(run_dates)} runs"
            )

    weather_month = xr.concat(
        monthly_runs,
        dim="run_time_utc",
        data_vars="minimal",
        coords="different",
        compat="equals",
        join="exact"
        )

    weather_month["lead_available"] = (
        ~weather_month["temperature_K"]
        .isnull()
        .all(dim=("latitude", "longitude"))
        )
    
    return weather_month

def download_and_save_month(
    year: int,
    month: int,
    output_dir: Path,
) -> None:

    output_dir.mkdir(parents=True, exist_ok=True)
    
    final_path = output_dir / f"gfs_{year}_{month:02d}.nc"
    temp_path = output_dir / f"gfs_{year}_{month:02d}.tmp.nc"

    # Month already completed
    if final_path.exists():
        print(f"Already exists: {final_path.name} -> skip")
        return

    print(f"Downloading {year}-{month:02d}...")

    weather_month = download_gfs_month(
        str(year),
        f"{month:02d}"
    )

    # Write temporary file first
    weather_month.to_netcdf(temp_path)

    # Rename only after successful write
    temp_path.replace(final_path)

    print(f"Saved: {final_path.name}")

def load_weather_history(weather_dir: Path) -> xr.Dataset:
    """Load and concatenate the monthly raw GFS files."""

    weather_files = sorted(
        weather_dir.glob("gfs_????_??.nc")
    )

    monthly_datasets = []

    for path in weather_files:
        with xr.open_dataset(path) as ds:
            monthly_datasets.append(ds.load())

    return xr.concat(
        monthly_datasets,
        dim="run_time_utc",
    )

def mask_temperature_range(
    temperature: xr.DataArray,
    min_k: float = 150.0,
    max_k: float = 350.0,
) -> tuple[xr.DataArray, xr.DataArray]:

    invalid = (
        (temperature < min_k)
        | (temperature > max_k)
    )

    return temperature.where(~invalid), invalid

def temporal_consistency_audit(
    temperature: xr.DataArray,
) -> xr.Dataset:

    expected = (
        temperature.shift(forecast_hour=1)
        + temperature.shift(forecast_hour=-1)
    ) / 2

    residual = abs(temperature - expected)

    return xr.Dataset({
        "max_residual": residual.max(
            dim=["latitude", "longitude"]
        ),
        "fraction_gt_10K": (
            residual > 10
        ).mean(
            dim=["latitude", "longitude"]
        ),
        "fraction_gt_20K": (
            residual > 20
        ).mean(
            dim=["latitude", "longitude"]
        ),
    })