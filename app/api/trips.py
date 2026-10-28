from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import os

from app.database import get_db
from app.models import Trip, Attraction
from app.schemas import (
    AttractionInput,
    ItineraryResponse,
    OptimizeRequest,
    Preferences,
    TripCreate,
    ReplanRequest,
    ReplanResponse,
)
from app.services.planner import generate_greedy_itinerary
from app.services.routing import build_travel_time_matrix

router = APIRouter(prefix="/api/v1/trips", tags=["Trips"])


@router.post("", status_code=201)
def create_trip(
    request: TripCreate,
    db: Session = Depends(get_db),
):
    trip = Trip(
        destination=request.destination,
        start_date=request.start_date,
        end_date=request.end_date,
        budget=request.budget,
        available_minutes_per_day=request.available_minutes_per_day,
        start_latitude=request.start_latitude,
        start_longitude=request.start_longitude,
        preferences=request.preferences.model_dump(),
    )

    db.add(trip)
    db.commit()
    db.refresh(trip)

    return {
        "id": trip.id,
        "destination": trip.destination,
        "start_date": str(trip.start_date),
        "end_date": str(trip.end_date),
        "budget": trip.budget,
    }


@router.get("/{trip_id}")
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
):
    trip = db.get(Trip, trip_id)

    if trip is None:
        raise HTTPException(
            status_code=404,
            detail="Trip not found",
        )

    return {
        "id": trip.id,
        "destination": trip.destination,
        "start_date": str(trip.start_date),
        "end_date": str(trip.end_date),
        "budget": trip.budget,
        "preferences": trip.preferences,
        "latest_itinerary": trip.latest_itinerary,
    }


@router.post(
    "/{trip_id}/optimize",
    response_model=ItineraryResponse,
)
def optimize_trip(
    trip_id: int,
    request: OptimizeRequest,
    db: Session = Depends(get_db),
):
    trip = db.get(Trip, trip_id)

    if trip is None:
        raise HTTPException(
            status_code=404,
            detail="Trip not found",
        )

    preferences = Preferences.model_validate(trip.preferences)

    # Select the routing provider from the environment.
    provider = os.getenv("ROUTING_PROVIDER", "haversine")

    # Build the travel-time matrix before running the planner.
    try:
        travel_matrix = build_travel_time_matrix(
            start=(
                trip.start_latitude,
                trip.start_longitude,
            ),
            attractions=request.attractions,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve travel-time data.",
        ) from exc

    # Generate the itinerary using the matrix.
    try:
        result = generate_greedy_itinerary(
            attractions=request.attractions,
            preferences=preferences,
            start_latitude=trip.start_latitude,
            start_longitude=trip.start_longitude,
            budget=trip.budget,
            available_minutes=trip.available_minutes_per_day,
            travel_matrix=travel_matrix,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    response = ItineraryResponse(
        trip_id=trip.id,
        algorithm="greedy",
        **result,
    )

    trip.latest_itinerary = response.model_dump(mode="json")
    db.commit()

    return response

from sqlalchemy import func

@router.post(
    "/{trip_id}/optimize-saved",
    response_model=ItineraryResponse,
)
def optimize_saved_trip(
    trip_id: int,
    db: Session = Depends(get_db),
):
    trip = db.get(Trip, trip_id)

    if trip is None:
        raise HTTPException(
            status_code=404,
            detail="Trip not found",
        )

    saved_attractions = (
        db.query(Attraction)
        .filter(
            func.lower(Attraction.destination)
            == trip.destination.strip().lower()
        )
        .order_by(Attraction.id)
        .all()
    )

    if not saved_attractions:
        raise HTTPException(
            status_code=404,
            detail="No saved attractions found for this destination.",
        )

    # Convert database records into the planner's input schema.
    attractions = [
        AttractionInput(
            id=a.id,
            name=a.name,
            category=a.category,
            latitude=a.latitude,
            longitude=a.longitude,
            cost=a.cost,
            visit_minutes=a.visit_minutes,
            preference_score=a.preference_score,
            weather_risk=a.weather_risk,
            crowd_risk=a.crowd_risk,
            availability_risk=a.availability_risk,
        )
        for a in saved_attractions
    ]

    preferences = Preferences.model_validate(trip.preferences)

    provider = os.getenv("ROUTING_PROVIDER", "haversine")

    try:
        travel_matrix = build_travel_time_matrix(
            start=(trip.start_latitude, trip.start_longitude),
            attractions=attractions,
            provider=provider,
        )

        result = generate_greedy_itinerary(
            attractions=attractions,
            preferences=preferences,
            start_latitude=trip.start_latitude,
            start_longitude=trip.start_longitude,
            budget=trip.budget,
            available_minutes=trip.available_minutes_per_day,
            travel_matrix=travel_matrix,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve travel-time data.",
        ) from exc

    response = ItineraryResponse(
        trip_id=trip.id,
        algorithm="greedy",
        **result,
    )

    trip.latest_itinerary = response.model_dump(mode="json")
    db.commit()

    return response

@router.post(
    "/{trip_id}/replan",
    response_model=ReplanResponse,
)
def replan_trip(
    trip_id: int,
    request: ReplanRequest,
    db: Session = Depends(get_db),
):
    # 1. Find the trip.
    trip = db.get(Trip, trip_id)

    if trip is None:
        raise HTTPException(
            status_code=404,
            detail="Trip not found",
        )

    # 2. Load attractions saved for this destination.
    saved_attractions = (
        db.query(Attraction)
        .filter(
            func.lower(Attraction.destination)
            == trip.destination.strip().lower()
        )
        .order_by(Attraction.id)
        .all()
    )

    if not saved_attractions:
        raise HTTPException(
            status_code=404,
            detail="No saved attractions found for this destination.",
        )

    # 3. Exclude attractions already visited or now closed.
    completed_ids = set(request.completed_attraction_ids)
    closed_ids = set(request.closed_attraction_ids)

    known_ids = {a.id for a in saved_attractions}

    excluded_closed_ids = sorted(closed_ids & known_ids)

    remaining_attractions = [
        AttractionInput(
            id=a.id,
            name=a.name,
            category=a.category,
            latitude=a.latitude,
            longitude=a.longitude,
            cost=a.cost,
            visit_minutes=a.visit_minutes,
            preference_score=a.preference_score,
            weather_risk=a.weather_risk,
            crowd_risk=a.crowd_risk,
            availability_risk=a.availability_risk,
        )
        for a in saved_attractions
        if a.id not in completed_ids
        and a.id not in closed_ids
    ]

    # 4. If no eligible attractions remain, return an empty plan.
    if not remaining_attractions:
        result = {
            "stops": [],
            "total_cost": 0.0,
            "total_travel_minutes": 0,
            "total_visit_minutes": 0,
            "satisfaction": 0.0,
            "risk_score": 0.0,
            "feasible": False,
            "warnings": [
                "No eligible attractions remain after excluding completed and closed attractions."
            ],
        }
    else:
        # 5. Load the travel preferences and routing provider.
        preferences = Preferences.model_validate(
            trip.preferences
        )
        provider = os.getenv(
            "ROUTING_PROVIDER",
            "haversine",
        )

        # 6. Calculate routes from the traveler's current location.
        try:
            travel_matrix = build_travel_time_matrix(
                start=(
                    request.current_latitude,
                    request.current_longitude,
                ),
                attractions=remaining_attractions,
                provider=provider,
            )

            # 7. Generate a new plan using remaining resources.
            result = generate_greedy_itinerary(
                attractions=remaining_attractions,
                preferences=preferences,
                start_latitude=request.current_latitude,
                start_longitude=request.current_longitude,
                budget=request.remaining_budget,
                available_minutes=request.remaining_minutes,
                travel_matrix=travel_matrix,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=502,
                detail="Could not retrieve travel-time data.",
            ) from exc

    # 8. Return the new plan and record which stops were completed
    #    or excluded because they were closed.
    response = ReplanResponse(
        trip_id=trip.id,
        algorithm="greedy_replan",
        completed_attraction_ids=sorted(completed_ids),
        excluded_closed_attraction_ids=excluded_closed_ids,
        **result,
    )

    trip.latest_itinerary = response.model_dump(mode="json")
    db.commit()

    return response