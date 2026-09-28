from datetime import datetime

from pydantic import BaseModel

from models import GarmentCategory, Formality, Season, LayerPosition, ImageSource, EventType


# ---------- Garment ----------

class GarmentBase(BaseModel):
    name: str
    category: GarmentCategory
    color: str | None = None
    pattern: str | None = None
    formality: Formality = Formality.CASUAL
    season: Season = Season.ALL
    layer: LayerPosition | None = None
    tags: list[str] | None = None


class GarmentCreate(GarmentBase):
    image_url: str
    image_source: ImageSource = ImageSource.PHOTO


class GarmentOut(GarmentBase):
    id: str
    image_url: str
    image_source: ImageSource
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Returned right after auto-tagging, before the user confirms/edits and
# actually calls POST /garments. Mirrors GarmentCreate but every field is
# optional since the vision model might not have filled in everything.
class GarmentTagSuggestion(BaseModel):
    category: GarmentCategory | None = None
    color: str | None = None
    pattern: str | None = None
    formality: Formality | None = None
    season: Season | None = None
    layer: LayerPosition | None = None
    tags: list[str] | None = None
    confidence: str | None = None


# ---------- Event ----------

class EventCreate(BaseModel):
    name: str
    event_type: EventType
    date: datetime
    location: str | None = None
    dress_code_notes: str | None = None


class EventOut(EventCreate):
    id: str
    weather_temp_c: float | None = None
    weather_condition: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Outfit suggestion (response shape, not a DB row) ----------

class OutfitSuggestionOut(BaseModel):
    top: GarmentOut | None
    bottom: GarmentOut | None
    dress: GarmentOut | None
    outerwear: GarmentOut | None
    mid_layer: GarmentOut | None
    shoes: GarmentOut | None
    accessories: list[GarmentOut]
    score: float
    reasons: list[str]


# ---------- Outfit (saved) ----------

class OutfitSave(BaseModel):
    name: str | None = None
    event_id: str | None = None
    garment_ids: list[str]  # flat list; role/category on each Garment tells you what it is


class OutfitOut(BaseModel):
    id: str
    name: str | None
    event_id: str | None
    is_favorite: bool
    was_worn: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Pin ----------

class PinOut(BaseModel):
    id: str
    board_url: str | None
    image_url: str
    dominant_colors: list[str] | None
    inferred_formality: Formality | None
    imported_at: datetime

    class Config:
        from_attributes = True
