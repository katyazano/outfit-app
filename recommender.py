"""
Rules-based recommendation engine.

Given an Event (with weather + type) and the user's closet (list of Garments),
produce a ranked list of candidate Outfits.

Deliberately NOT ML at this stage — see the write-up at the bottom for why,
and where a learned model would slot in later without changing this interface.
"""

from dataclasses import dataclass, field
from itertools import product

from models import Garment, GarmentCategory, Formality, LayerPosition, EventType, Event


# ---------- Rule tables (tune these as you use the app) ----------

# Which formality levels are acceptable for each event type.
EVENT_FORMALITY_MAP: dict[EventType, set[Formality]] = {
    EventType.WORK: {Formality.SMART_CASUAL, Formality.FORMAL},
    EventType.CASUAL_OUTING: {Formality.CASUAL, Formality.SMART_CASUAL},
    EventType.PARTY: {Formality.SMART_CASUAL, Formality.FORMAL},
    EventType.DATE: {Formality.SMART_CASUAL, Formality.FORMAL},
    EventType.FORMAL: {Formality.FORMAL},
    EventType.SPORT: {Formality.CASUAL},
    EventType.TRAVEL: {Formality.CASUAL, Formality.SMART_CASUAL},
}

COLD_THRESHOLD_C = 15
HOT_THRESHOLD_C = 25


# ---------- Output shape ----------

@dataclass
class OutfitSuggestion:
    top: Garment | None
    bottom: Garment | None  # None if a dress is used instead
    dress: Garment | None
    outerwear: Garment | None
    shoes: Garment | None
    accessories: list[Garment] = field(default_factory=list)
    mid_layer: Garment | None = None  # e.g. cardigan/sweater under the outerwear, cold-weather only
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)  # human-readable "why this" for the UI

    def garments(self) -> list[Garment]:
        items = [self.top, self.bottom, self.dress, self.outerwear, self.shoes, self.mid_layer]
        return [g for g in items if g is not None] + self.accessories


# ---------- Step 1: filter closet down to what's even eligible ----------

def filter_by_formality(garments: list[Garment], event_type: EventType) -> list[Garment]:
    allowed = EVENT_FORMALITY_MAP.get(event_type, set(Formality))
    return [g for g in garments if g.formality in allowed]


def filter_by_weather(garments: list[Garment], temp_c: float | None, condition: str | None) -> list[Garment]:
    if temp_c is None:
        return garments  # no weather data yet, don't filter

    result = []
    for g in garments:
        if temp_c < COLD_THRESHOLD_C:
            # need something suited to cold, or an all-season piece
            if g.season not in (g.season.COLD, g.season.ALL) and g.category != GarmentCategory.OUTERWEAR:
                continue
        elif temp_c > HOT_THRESHOLD_C:
            # exclude heavy cold-only pieces (but allow accessories through)
            if g.season == g.season.COLD and g.category != GarmentCategory.ACCESSORY:
                continue

        if condition == "rain" and g.category == GarmentCategory.SHOES:
            # prefer closed/waterproof shoes when it's raining, if that info exists in tags
            tags = g.tags or []
            if "open" in tags or "sandal" in tags:
                continue

        result.append(g)
    return result


def filter_by_dress_code(garments: list[Garment], event: Event) -> list[Garment]:
    """Very simple keyword matching against free-text dress code notes,
    e.g. 'no skirts' or 'pants only' typed in when creating the event."""
    notes = (event.dress_code_notes or "").lower()
    if not notes:
        return garments

    banned_tags = []
    if "no skirt" in notes or "pants only" in notes:
        banned_tags.append("skirt")
    if "no jeans" in notes:
        banned_tags.append("jeans")

    if not banned_tags:
        return garments

    return [g for g in garments if not any(t in (g.tags or []) for t in banned_tags)]


# ---------- Step 2: build combinations ----------

def build_combinations(eligible: list[Garment], event: Event) -> list[OutfitSuggestion]:
    by_cat = {cat: [] for cat in GarmentCategory}
    for g in eligible:
        by_cat[g.category].append(g)

    combos: list[OutfitSuggestion] = []

    # Path A: top + bottom
    for top, bottom, shoes in product(
        by_cat[GarmentCategory.TOP] or [None],
        by_cat[GarmentCategory.BOTTOM] or [None],
        by_cat[GarmentCategory.SHOES] or [None],
    ):
        if top is None or bottom is None:
            continue
        combos.append(OutfitSuggestion(top=top, bottom=bottom, dress=None, outerwear=None, shoes=shoes))

    # Path B: dress instead of top+bottom
    for dress, shoes in product(
        by_cat[GarmentCategory.DRESS] or [None],
        by_cat[GarmentCategory.SHOES] or [None],
    ):
        if dress is None:
            continue
        combos.append(OutfitSuggestion(top=None, bottom=None, dress=dress, outerwear=None, shoes=shoes))

    # Attach outerwear + accessories to every combo (cheap to add, big impact on cold days)
    outerwear_options = by_cat[GarmentCategory.OUTERWEAR] or [None]

    # Mid-layer only enters the search space when it's cold enough to matter —
    # otherwise this triples the combo count for a piece nobody needs on a warm day.
    is_cold = event.weather_temp_c is not None and event.weather_temp_c < COLD_THRESHOLD_C
    mid_layer_candidates = [g for g in eligible if g.layer == LayerPosition.MID] if is_cold else []
    mid_layer_options = mid_layer_candidates or [None]

    expanded = []
    for combo in combos:
        for outer, mid in product(outerwear_options, mid_layer_options):
            expanded.append(OutfitSuggestion(
                top=combo.top, bottom=combo.bottom, dress=combo.dress,
                outerwear=outer, shoes=combo.shoes, mid_layer=mid,
                accessories=by_cat[GarmentCategory.ACCESSORY][:1],  # cap at 1 to avoid combinatorial blowup
            ))
    return expanded


# ---------- Step 3: score ----------

def score_outfit(outfit: OutfitSuggestion, event: Event) -> OutfitSuggestion:
    score = 0.0
    reasons = []

    garments = outfit.garments()
    if not garments:
        outfit.score = -999
        return outfit

    # Reward formality match consistency (all pieces the same formality tier reads as more "put together")
    formalities = {g.formality for g in garments}
    if len(formalities) == 1:
        score += 1.0
        reasons.append("Consistent formality across pieces")

    # Reward outerwear on cold days, penalize it (slightly) on hot days
    if event.weather_temp_c is not None:
        if event.weather_temp_c < COLD_THRESHOLD_C and outfit.outerwear:
            score += 2.0
            reasons.append(f"Added layer for {event.weather_temp_c}°C")
        if event.weather_temp_c > HOT_THRESHOLD_C and outfit.outerwear:
            score -= 1.5

        # Full base -> mid -> outer stack reads as more deliberate on cold days,
        # and a naked outer shell over just a t-shirt is a common real-world miss.
        if event.weather_temp_c < COLD_THRESHOLD_C:
            if outfit.mid_layer and outfit.outerwear:
                score += 1.0
                reasons.append("Layered mid piece under outerwear")
            elif outfit.outerwear and not outfit.mid_layer and event.weather_temp_c < COLD_THRESHOLD_C - 5:
                score -= 0.5  # quite cold and skipping the mid layer entirely

    # Slight boost for outfits reusing pieces marked as favorites
    if any(getattr(g, "is_favorite", False) for g in garments):
        score += 0.5

    outfit.score = score
    outfit.reasons = reasons
    return outfit


# ---------- Entry point ----------

def recommend_outfits(event: Event, closet: list[Garment], top_n: int = 3) -> list[OutfitSuggestion]:
    eligible = [g for g in closet if g.is_active]
    eligible = filter_by_formality(eligible, event.event_type)
    eligible = filter_by_weather(eligible, event.weather_temp_c, event.weather_condition)
    eligible = filter_by_dress_code(eligible, event)

    combos = build_combinations(eligible, event)
    scored = [score_outfit(c, event) for c in combos]
    scored.sort(key=lambda c: c.score, reverse=True)

    return scored[:top_n]


"""
Where this goes next (phase 2, once you have usage data):

- Track `was_worn` on chosen outfits. Once you have ~30-50 data points,
  swap `score_outfit` for a lightweight model (even logistic regression
  on garment/event features) trained on what you actually picked vs. what
  was suggested. The function signature (Event, list[Garment]) -> ranked
  list[OutfitSuggestion] doesn't need to change — only the internals of
  score_outfit / recommend_outfits.
- CLIP embeddings on PinterestPin images could feed a "visual similarity"
  term into score_outfit: embed each candidate outfit's garment photos,
  compare to your saved pins, add the similarity as another scoring term.
"""