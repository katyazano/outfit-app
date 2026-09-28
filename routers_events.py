from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from weather import get_weather_snapshot

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=schemas.EventOut)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    db_event = models.Event(**event.model_dump())

    if event.location:
        try:
            snapshot = get_weather_snapshot(event.location, event.date)
            db_event.weather_temp_c = snapshot["temp_c"]
            db_event.weather_condition = snapshot["condition"]
        except Exception:
            # Don't block event creation on a weather API hiccup —
            # the user can retry via PATCH once the service is back.
            pass

    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.get("", response_model=list[schemas.EventOut])
def list_events(db: Session = Depends(get_db)):
    return db.query(models.Event).order_by(models.Event.date).all()


@router.get("/{event_id}", response_model=schemas.EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event


@router.post("/{event_id}/refresh-weather", response_model=schemas.EventOut)
def refresh_weather(event_id: str, db: Session = Depends(get_db)):
    """Manually re-fetch weather — useful as the event date gets closer
    and the forecast becomes available/more accurate."""
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db_event.location:
        raise HTTPException(status_code=400, detail="Event has no location set")

    snapshot = get_weather_snapshot(db_event.location, db_event.date)
    db_event.weather_temp_c = snapshot["temp_c"]
    db_event.weather_condition = snapshot["condition"]
    db.commit()
    db.refresh(db_event)
    return db_event
