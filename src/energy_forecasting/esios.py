import pandas as pd
import requests
import json
from pathlib import Path

# ESIOS indicator IDs used in this project
ACTUAL_DEMAND_INDICATOR = 1293
REE_D1_FORECAST_INDICATOR = 1775

PUBLIC_ESIOS_TOKEN = (
    "request_your_personal_token_sending_email_to_consultasios@ree.es"
)

def download_indicator(
    indicator_id: int,
    start_date: str,
    end_date: str,
    api_key: str = PUBLIC_ESIOS_TOKEN,
)-> list[dict]:
    
    current_start = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date) 

    values=[]

    url = f"https://api.esios.ree.es/indicators/{indicator_id}"

    headers = {
    "Accept": "application/json; application/vnd.esios-api-v1+json",
    "Content-Type": "application/json",
    "X-API-KEY": api_key,
    }

    while current_start < end_date:
        current_end = min(current_start + 
                          pd.DateOffset(months=1), end_date)
        
        request_end = current_end- pd.Timedelta(seconds=1)

        current_start_str = current_start.strftime("%Y-%m-%dT%H:%M:%S")
        request_end_str = request_end.strftime("%Y-%m-%dT%H:%M:%S")

        params = {
            "start_date": current_start_str,
            "end_date": request_end_str
        }

        response = requests.get(url, params=params, headers=headers,timeout=30)


        if response.status_code==200:
            data = response.json()
            values.extend(data["indicator"]["values"])
        
        else:
            raise requests.HTTPError(
                f"HTTP error {response.status_code}"
                f"(from {current_start_str} to {request_end_str}) while downloading indicator {indicator_id} from ESIOS API. ",
                response=response,
                )
        
        current_start = current_end

    return values

def to_hourly_series(values: list[dict]) -> pd.Series:

    df = pd.DataFrame(values)
    df.datetime_utc= pd.to_datetime(df.datetime_utc)
    df.set_index("datetime_utc", inplace=True)
    df.sort_index(inplace=True)
    
    hourly = df["value"].resample("1h").mean()

    return hourly

def download_price(
    indicator_id: int,
    geo_id: int,
    start,
    end,
    name: str,
    cache_dir,
    api_key: str = PUBLIC_ESIOS_TOKEN,
) -> pd.Series:
    """
    Download an ESIOS price indicator in monthly chunks,
    reusing cached raw responses when available.
    """

    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")

    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    first_month = pd.Timestamp(
        year=start.year,
        month=start.month,
        day=1,
        tz="UTC",
    )

    last_month = pd.Timestamp(
        year=end.year,
        month=end.month,
        day=1,
        tz="UTC",
    )

    month_edges = pd.date_range(
        first_month,
        last_month
        + pd.offsets.MonthBegin(1),
        freq="MS",
    )

    headers = {
        "Accept": (
            "application/json; "
            "application/vnd.esios-api-v1+json"
        ),
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }

    observations = []

    for left, right in zip(
        month_edges[:-1],
        month_edges[1:],
    ):
        cache_path = (
            cache_dir
            / (
                f"{indicator_id}_"
                f"{geo_id}_"
                f"{left:%Y-%m}.json"
            )
        )

        if cache_path.exists():
            values = json.loads(
                cache_path.read_text(
                    encoding="utf-8"
                )
            )

        else:
            response = requests.get(
                (
                    "https://api.esios.ree.es/"
                    f"indicators/{indicator_id}"
                ),
                params={
                    "start_date":
                        left.isoformat(),

                    "end_date": (
                        right
                        - pd.Timedelta(seconds=1)
                    ).isoformat(),

                    "geo_ids[]":
                        geo_id,
                },
                headers=headers,
                timeout=60,
            )

            response.raise_for_status()

            values = (
                response.json()
                ["indicator"]["values"]
            )

            if not values:
                raise ValueError(
                    "No ESIOS data for "
                    f"indicator {indicator_id}, "
                    f"{left:%Y-%m}."
                )

            cache_path.write_text(
                json.dumps(values),
                encoding="utf-8",
            )

        observations.extend(values)

    frame = pd.DataFrame(observations)

    frame = frame.loc[
        frame["geo_id"].eq(geo_id)
    ].copy()

    frame["datetime_utc"] = pd.to_datetime(
        frame["datetime_utc"],
        utc=True,
    )

    frame = frame.loc[
        frame["datetime_utc"].ge(start)
        & frame["datetime_utc"].lt(end)
    ]

    frame = (
        frame[
            ["datetime_utc", "value"]
        ]
        .drop_duplicates()
    )

    if frame.empty:
        raise ValueError(
            f"Empty price series for {name}."
        )

    if frame["datetime_utc"].duplicated().any():
        raise ValueError(
            f"Duplicate timestamps for {name}."
        )

    series = (
        frame
        .set_index("datetime_utc")["value"]
        .sort_index()
        .rename(name)
    )

    series = pd.to_numeric(
        series,
        errors="raise",
    )

    if series.isna().any():
        raise ValueError(
            f"Missing values for {name}."
        )

    return series