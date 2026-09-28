from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from recommender import recommend_outfits

router = APIRouter(prefix="/outfits", tags=["outfits"])


@router.get("/recommend", response_model=list[schemas.OutfitSuggestionOut])
def get_recommendations(event_id: str, top_n: int = 3, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    closet = db.query(models.Garment).filter(models.Garment.is_active == True).all()
    suggestions = recommend_outfits(event, closet, top_n=top_n)

    if not suggestions:
        raise HTTPException(
            status_code=422,
            detail="No eligible combinations found — check that your closet has enough "
                   "pieces tagged for this event's formality/weather.",
        )
    return suggestions


@router.post("", response_model=schemas.OutfitOut)
def save_outfit(outfit: schemas.OutfitSave, db: Session = Depends(get_db)):
    """Persist an outfit the user picked (from recommendations or built manually)."""
    db_outfit = models.Outfit(name=outfit.name, event_id=outfit.event_id)
    db.add(db_outfit)
    db.flush()  # get db_outfit.id before attaching links

    for garment_id in outfit.garment_ids:
        db.add(models.OutfitGarment(outfit_id=db_outfit.id, garment_id=garment_id))

    db.commit()
    db.refresh(db_outfit)
    return db_outfit


@router.get("", response_model=list[schemas.OutfitOut])
def list_outfits(favorites_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Outfit)
    if favorites_only:
        query = query.filter(models.Outfit.is_favorite == True)
    return query.order_by(models.Outfit.created_at.desc()).all()


@router.patch("/{outfit_id}/worn")
def mark_worn(outfit_id: str, db: Session = Depends(get_db)):
    """Feeds the phase-2 'learns your taste' idea noted in recommender.py."""
    db_outfit = db.query(models.Outfit).filter(models.Outfit.id == outfit_id).first()
    if not db_outfit:
        raise HTTPException(status_code=404, detail="Outfit not found")
    db_outfit.was_worn = True
    db.commit()
    return {"status": "marked worn"}
