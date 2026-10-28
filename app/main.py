
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.trips import router
from app.api.attractions import router as attractions_router
from app.database import Base, engine
from app import models  # Register SQLAlchemy models

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Personalized Risk-Aware Trip Optimization API",
    version="0.1.0",
    description=(
        "Backend for personalized itinerary generation, "
        "risk evaluation, and dynamic replanning."
    ),
)

# Development configuration. Restrict origins in deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(attractions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
