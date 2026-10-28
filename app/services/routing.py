
from math import asin, cos, radians, sin, sqrt, ceil
from typing import Literal

import httpx

from app.schemas import AttractionInput


Location = tuple[float, float]  # latitude, longitude
TravelMatrix = list[list[int | None]]


def haversine_km(a: Location, b: Location) -> float:
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    value = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )
    value = min(1.0, max(0.0, value))

    return 6371.0 * 2 * asin(sqrt(value))


def estimate_minutes(a: Location, b: Location) -> int:
    """Local fallback; not a real road travel-time estimate."""
    return ceil(haversine_km(a, b) / 25.0 * 60.0)


def build_travel_time_matrix(
    start: Location,
    attractions: list[AttractionInput],
    provider: Literal["haversine", "osrm"] = "haversine",
    osrm_base_url: str = "https://router.project-osrm.org",
) -> TravelMatrix:
    """
    Matrix order:
      index 0 = trip starting location
      index 1 = attractions[0]
      index 2 = attractions[1]
      ...

    matrix[i][j] = estimated travel minutes from i to j.
    None means the route could not be found.
    """
    locations: list[Location] = [
        start,
        *[
            (a.latitude, a.longitude)
            for a in attractions
        ],
    ]

    n = len(locations)

    if provider == "haversine":
        return [
            [
                0 if i == j else estimate_minutes(
                    locations[i], locations[j]
                )
                for j in range(n)
            ]
            for i in range(n)
        ]

    if provider != "osrm":
        raise ValueError(f"Unsupported routing provider: {provider}")

    # Keep requests bounded. Larger trips can be batched later.
    if n > 50:
        raise ValueError(
            "At most 50 locations per OSRM request in this prototype."
        )

    # OSRM coordinate order is longitude,latitude.
    coordinates = ";".join(
        f"{lon},{lat}" for lat, lon in locations
    )

    url = (
        f"{osrm_base_url.rstrip('/')}/table/v1/driving/"
        f"{coordinates}"
    )

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                url,
                params={"annotations": "duration"},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            "Routing provider request failed."
        ) from exc

    if data.get("code") != "Ok":
        raise RuntimeError(
            f"Routing provider returned: {data.get('code', 'unknown error')}"
        )

    durations = data.get("durations")

    if not isinstance(durations, list) or len(durations) != n:
        raise RuntimeError("Routing provider returned an invalid matrix.")

    matrix: TravelMatrix = []

    for row in durations:
        if not isinstance(row, list) or len(row) != n:
            raise RuntimeError("Routing provider returned an invalid row.")

        matrix_row = []
        for seconds in row:
            if seconds is None:
                matrix_row.append(None)
            elif not isinstance(seconds, (int, float)) or seconds < 0:
                raise RuntimeError("Invalid travel duration received.")
            else:
                matrix_row.append(ceil(seconds / 60.0))

        matrix.append(matrix_row)

    return matrix
