
def calculate_attraction_risk(
    weather: float,
    crowd: float,
    availability: float,
) -> float:
    """Combine independent disruption probabilities."""
    return 1 - (
        (1 - weather)
        * (1 - crowd)
        * (1 - availability)
    )


def calculate_trip_risk(stop_risks: list[float]) -> float:
    """Approximate probability of at least one disruption."""
    survival_probability = 1.0

    for risk in stop_risks:
        survival_probability *= 1 - risk

    return 1 - survival_probability
