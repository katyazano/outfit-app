"""
Manual pin upload.

No Pinterest API involved — the user saves a pin from Pinterest (or anywhere)
as an image on their phone/computer, then uploads it directly to the app.
Same end result as an API import (a tagged PinterestPin row), just without
the OAuth step. Swap this out for pinterest_import.py later if you ever
want automatic board syncing.
"""

from storage import upload_image
from vision_tagging import tag_pinterest_pin


def upload_pin(image_bytes: bytes, filename: str) -> dict:
    """
    Uploads a manually-saved inspiration image and returns a dict ready
    to insert as a PinterestPin row, tags already filled in.
    """
    image_url = upload_image(image_bytes, filename, prefix="pins/")
    tags = tag_pinterest_pin(image_url)

    return {
        "board_url": None,  # nothing to link to without the API
        "image_url": image_url,
        "dominant_colors": tags.get("dominant_colors"),
        "inferred_formality": tags.get("inferred_formality"),
        # style_tags from vision isn't a PinterestPin column yet (only Garment has `tags`) —
        # add a `style_tags` ARRAY(String) column to PinterestPin if you want to keep these,
        # otherwise they're currently discarded here.
    }