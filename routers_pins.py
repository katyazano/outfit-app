from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from pin_upload import upload_pin

router = APIRouter(prefix="/pins", tags=["pins"])


@router.post("", response_model=schemas.PinOut)
async def create_pin(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    try:
        pin_data = upload_pin(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pin upload/tagging failed: {e}")

    db_pin = models.PinterestPin(**pin_data)
    db.add(db_pin)
    db.commit()
    db.refresh(db_pin)
    return db_pin


@router.get("", response_model=list[schemas.PinOut])
def list_pins(db: Session = Depends(get_db)):
    return db.query(models.PinterestPin).order_by(models.PinterestPin.imported_at.desc()).all()