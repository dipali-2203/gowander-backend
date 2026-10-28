
from app.schemas import AttractionInput
from app.services.routing import build_travel_time_matrix


def test_haversine_matrix_is_square_and_nonnegative():
    attractions = [
        AttractionInput(
            id="a",
            name="Place A",
            category="history",
            latitude=17.39,
            longitude=78.48,
            cost=100,
            visit_minutes=60,
            preference_score=0.9,
        ),
        AttractionInput(
            id="b",
            name="Place B",
            category="food",
            latitude=17.40,
            longitude=78.49,
            cost=50,
            visit_minutes=30,
            preference_score=0.8,
        ),
    ]

    matrix = build_travel_time_matrix(
        start=(17.385, 78.4867),
        attractions=attractions,
        provider="haversine",
    )

    assert len(matrix) == 3
    assert all(len(row) == 3 for row in matrix)

    for i in range(3):
        assert matrix[i][i] == 0
        assert all(
            value is None or value >= 0
            for value in matrix[i]
        )


def test_haversine_matrix_is_symmetric():
    attractions = [
        AttractionInput(
            id="a",
            name="Place A",
            category="history",
            latitude=17.39,
            longitude=78.48,
            cost=100,
            visit_minutes=60,
            preference_score=0.9,
        ),
        AttractionInput(
            id="b",
            name="Place B",
            category="food",
            latitude=17.40,
            longitude=78.49,
            cost=50,
            visit_minutes=30,
            preference_score=0.8,
        ),
    ]

    matrix = build_travel_time_matrix(
        start=(17.385, 78.4867),
        attractions=attractions,
    )

    assert matrix[0][1] == matrix[1][0]
    assert matrix[1][2] == matrix[2][1]
