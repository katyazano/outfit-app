"""
Vision-based auto-tagging.

Takes a garment photo (freshly uploaded, before it's saved to the closet)
and returns a best-guess set of Garment fields for the user to review/edit,
rather than typing everything by hand.

Uses the Claude API's vision support (image content blocks) with a prompt
that constrains output to your model's enum values, so the response maps
directly onto GarmentCreate without extra parsing logic.

Docs: https://docs.claude.com/en/docs/build-with-claude/vision
"""

import base64
import json
import os

import anthropic

from models import GarmentCategory, Formality, Season, LayerPosition

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

TAGGING_PROMPT = f"""You are tagging a clothing item photo for a wardrobe app.
Look at the image and return ONLY a JSON object (no markdown, no preamble) with these fields:

- "category": one of {[c.value for c in GarmentCategory]}
- "color": the dominant color, one or two words, lowercase
- "pattern": one of "solid", "striped", "floral", "plaid", "graphic", "other"
- "formality": one of {[f.value for f in Formality]}
- "season": one of {[s.value for s in Season]}
- "layer": one of {[l.value for l in LayerPosition]}, or null if not applicable
  (only tops/outerwear get a layer; bottoms/shoes/accessories should be null)
- "tags": a list of 2-5 short lowercase keywords useful for search/filtering
  (e.g. ["denim", "cropped"], or ["skirt"] for skirts — this tag matters for
  dress-code filtering elsewhere in the app, so always include "skirt" if applicable)
- "confidence": your confidence in this tagging, one of "high", "medium", "low"

If you're unsure about a field, make your best guess rather than leaving it out,
but reflect the uncertainty in "confidence" so the UI can prompt the user to
double check low-confidence tags.
"""


def _image_block(image_path: str | None = None, image_url: str | None = None) -> dict:
    if image_url:
        return {"type": "image", "source": {"type": "url", "url": image_url}}

    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    media_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def tag_garment_photo(image_path: str | None = None, image_url: str | None = None) -> dict:
    """
    Pass either a local image_path (freshly uploaded file, before S3 upload)
    or an image_url (already-hosted image, e.g. after S3 upload). Returns a
    dict matching the fields above, ready to pre-fill a GarmentCreate form.
    """
    if not image_path and not image_url:
        raise ValueError("Provide either image_path or image_url")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                _image_block(image_path=image_path, image_url=image_url),
                {"type": "text", "text": TAGGING_PROMPT},
            ],
        }],
    )

    raw_text = message.content[0].text.strip()
    # Model is instructed to return raw JSON, but strip fences defensively anyway.
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw_text)


def tag_pinterest_pin(image_url: str) -> dict:
    """
    Same idea, but for a Pinterest pin — we care less about exact category
    and more about overall style signal to steer the recommender later
    (dominant colors + formality + freeform style tags).
    """
    prompt = f"""You are analyzing a fashion inspiration image from Pinterest.
Return ONLY a JSON object (no markdown) with:

- "dominant_colors": list of 1-3 colors, lowercase
- "inferred_formality": one of {[f.value for f in Formality]}
- "style_tags": list of 2-5 short lowercase style keywords
  (e.g. ["minimalist", "monochrome"], ["boho", "layered"])
"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "url", "url": image_url}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    raw_text = message.content[0].text.strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw_text)