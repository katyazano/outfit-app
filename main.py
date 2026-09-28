from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

from database import engine
from models import Base
import routers_garments
import routers_events
import routers_outfits
import routers_pins

# Single-user app, no auth layer for now — see routers if you ever need
# to add it back (your project-management-api already has a pattern for
# JWT + role-based access if this ever needs multiple users).
app = FastAPI(title="Outfit Recommender")

Base.metadata.create_all(bind=engine)  # fine for a personal project; swap for
# Alembic migrations once you start changing the schema often

app.include_router(routers_garments.router)
app.include_router(routers_events.router)
app.include_router(routers_outfits.router)
app.include_router(routers_pins.router)


@app.get("/")
def root():
    return {"status": "ok"}