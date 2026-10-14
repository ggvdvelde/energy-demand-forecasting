import json
from pathlib import Path

import requests


REDATA_DEMAND_URL = (
    "https://apidatos.ree.es/es/datos/demanda/evolucion"
)


def download_annual_demand_ccaa(
    region_ids: dict[str, int],
    start_year: int,
    end_year: int,
    output_dir: Path,
) -> None:

    output_dir.mkdir(parents=True, exist_ok=True)

    for region, geo_id in region_ids.items():
        for year in range(start_year, end_year + 1):

            output_path = output_dir / f"{geo_id}_{year}.json"

            if output_path.exists():
                continue

            params = {
                "start_date": f"{year}-01-01T00:00",
                "end_date": f"{year}-12-31T23:59",
                "time_trunc": "year",
                "geo_trunc": "electric_system",
                "geo_limit": "ccaa",
                "geo_ids": geo_id,
            }

            response = requests.get(
                REDATA_DEMAND_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            output_path.write_text(
                json.dumps(
                    response.json(),
                    ensure_ascii=False,
                    indent=2,
                )
            )