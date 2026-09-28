from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from storage import upload_image
from vision_tagging import tag_garment_photo

router = APIRouter(prefix="/garments", tags=["garments"])


@router.post("/tag-preview")
async def tag_preview(file: UploadFile = File(...)):
    """
    Uploads the photo to R2 AND returns auto-tag suggestions, in one call —
    saves a round trip since the client needs the image_url either way to
    later call POST /garments. Nothing is written to the database yet;
    the client shows these as pre-filled/editable fields first.
    """
    contents = await file.read()
    image_url = upload_image(contents, file.filename, prefix="garments/")

    try:
        tags = tag_garment_photo(image_url=image_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Tagging failed: {e}")

    return {"image_url": image_url, "suggestion": schemas.GarmentTagSuggestion(**tags)}


@router.post("", response_model=schemas.GarmentOut)
def create_garment(garment: schemas.GarmentCreate, db: Session = Depends(get_db)):
    """
    Saves a garment after the user has reviewed/edited the tag-preview
    suggestions (or typed everything manually). image_url must already
    point to an uploaded photo — upload to S3 client-side or add a
    separate /garments/upload-photo endpoint if you'd rather do it here.
    """
    db_garment = models.Garment(**garment.model_dump())
    db.add(db_garment)
    db.commit()
    db.refresh(db_garment)
    return db_garment


@router.get("", response_model=list[schemas.GarmentOut])
def list_garments(
    category: models.GarmentCategory | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(models.Garment)
    if active_only:
        query = query.filter(models.Garment.is_active == True)
    if category:
        query = query.filter(models.Garment.category == category)
    return query.all()


@router.patch("/{garment_id}", response_model=schemas.GarmentOut)
def update_garment(garment_id: str, updates: schemas.GarmentBase, db: Session = Depends(get_db)):
    db_garment = db.query(models.Garment).filter(models.Garment.id == garment_id).first()
    if not db_garment:
        raise HTTPException(status_code=404, detail="Garment not found")
    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(db_garment, field, value)
    db.commit()
    db.refresh(db_garment)
    return db_garment


@router.delete("/{garment_id}")
def deactivate_garment(garment_id: str, db: Session = Depends(get_db)):
    """Soft delete — see models.Garment.is_active. Keeps outfit history intact."""
    db_garment = db.query(models.Garment).filter(models.Garment.id == garment_id).first()
    if not db_garment:
        raise HTTPException(status_code=404, detail="Garment not found")
    db_garment.is_active = False
    db.commit()
    return {"status": "deactivated"}
