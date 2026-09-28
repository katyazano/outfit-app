"""
Data model for the outfit recommendation app.

Core entities:
- Garment: a physical clothing item in the user's closet
- Outfit: a saved combination of garments
- OutfitGarment: junction table (many-to-many, with position/role info)
- Event: something the user is dressing for (has type, date, weather)
- PinterestPin: an inspiration image imported from a Pinterest board
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum, Float
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


# ---------- Enums ----------

class GarmentCategory(str, enum.Enum):
    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    ACCESSORY = "accessory"
    BAG = "bag"


class Formality(str, enum.Enum):
    CASUAL = "casual"
    SMART_CASUAL = "smart_casual"
    FORMAL = "formal"


class Season(str, enum.Enum):
    WARM = "warm"
    COLD = "cold"
    RAIN = "rain"
    ALL = "all"


class EventType(str, enum.Enum):
    WORK = "work"
    CASUAL_OUTING = "casual_outing"
    PARTY = "party"
    DATE = "date"
    FORMAL = "formal"
    SPORT = "sport"
    TRAVEL = "travel"


class ImageSource(str, enum.Enum):
    PHOTO = "photo"
    DRAWING = "drawing"
    PINTEREST = "pinterest"


class LayerPosition(str, enum.Enum):
    BASE = "base"       # e.g. t-shirt, camisole
    MID = "mid"          # e.g. sweater, cardigan
    OUTER = "outer"       # e.g. coat, jacket


# ---------- Core tables ----------

class Garment(Base):
    __tablename__ = "garments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(120), nullable=False)
    category = Column(SAEnum(GarmentCategory), nullable=False)
    color = Column(String(50), nullable=True)
    pattern = Column(String(50), nullable=True)  # e.g. "solid", "striped", "floral"
    formality = Column(SAEnum(Formality), nullable=False, default=Formality.CASUAL)
    season = Column(SAEnum(Season), nullable=False, default=Season.ALL)
    layer = Column(SAEnum(LayerPosition), nullable=True)  # optional: only meaningful for top/outerwear pieces
    tags = Column(ARRAY(String), nullable=True)  # free-form, e.g. ["denim", "vintage"]

    image_url = Column(String(500), nullable=False)
    image_source = Column(SAEnum(ImageSource), nullable=False, default=ImageSource.PHOTO)

    is_active = Column(Boolean, default=True)  # soft-delete: still own it but donated/lost etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    outfit_links = relationship("OutfitGarment", back_populates="garment")


class Outfit(Base):
    __tablename__ = "outfits"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(120), nullable=True)
    event_id = Column(UUID(as_uuid=False), ForeignKey("events.id"), nullable=True)

    is_favorite = Column(Boolean, default=False)
    was_worn = Column(Boolean, default=False)  # feeds future "learn my taste" logic
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="outfits")
    garment_links = relationship("OutfitGarment", back_populates="outfit", cascade="all, delete-orphan")


class OutfitGarment(Base):
    """Junction table: which garments make up an outfit, and what role they play."""
    __tablename__ = "outfit_garments"

    outfit_id = Column(UUID(as_uuid=False), ForeignKey("outfits.id"), primary_key=True)
    garment_id = Column(UUID(as_uuid=False), ForeignKey("garments.id"), primary_key=True)
    role = Column(String(30), nullable=True)  # e.g. "top", "layer", "footwear" (redundant w/ category but useful for layering logic)

    outfit = relationship("Outfit", back_populates="garment_links")
    garment = relationship("Garment", back_populates="outfit_links")


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(120), nullable=False)
    event_type = Column(SAEnum(EventType), nullable=False)
    date = Column(DateTime, nullable=False)
    location = Column(String(200), nullable=True)  # for weather lookup
    dress_code_notes = Column(Text, nullable=True)  # free text, e.g. "no jeans allowed"

    # snapshot of weather at planning time (filled by weather API call)
    weather_temp_c = Column(Float, nullable=True)
    weather_condition = Column(String(50), nullable=True)  # "rain", "clear", "windy"

    created_at = Column(DateTime, default=datetime.utcnow)

    outfits = relationship("Outfit", back_populates="event")


class PinterestPin(Base):
    """Inspiration image saved by the user — manually uploaded for now.
    board_url is optional since there's no API pulling board metadata yet;
    if you later add the Pinterest API, populate it then."""
    __tablename__ = "pinterest_pins"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    board_url = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=False)

    # auto-extracted via CLIP/vision model
    extracted_tags = Column(ARRAY(String), nullable=True)
    dominant_colors = Column(ARRAY(String), nullable=True)
    inferred_formality = Column(SAEnum(Formality), nullable=True)

    imported_at = Column(DateTime, default=datetime.utcnow)
