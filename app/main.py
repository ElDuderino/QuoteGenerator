import os
import io
from typing import Optional

from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dotenv import load_dotenv
import logging

from app.database import QuoteDatabase
from app.filesystem import ImageStorage
from app.auth_funcs import router as auth_router, User, get_current_active_user
from app.quote_generator import generate_quote_text, generate_image_prompt
from app.image_generator import generate_image_via_imagen, overlay_text_on_image

# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env in the project root (if present)
load_dotenv()

# This application requires the new openai>=1.0.0 SDK. We instantiate a
# client per-request (simple and explicit). We no longer include any legacy
# fallback logic for older openai versions.


app = FastAPI(title="Daily Business Quote Image")

# Include auth router
app.include_router(auth_router)

# Initialize database and image storage
db = QuoteDatabase()
image_storage = ImageStorage()


class QuoteRequest(BaseModel):
    seed: Optional[str] = None


@app.post("/quote-image")
def quote_image(req: QuoteRequest, current_user: User = Depends(get_current_active_user)):
    try:
        # Get recent quotes to avoid repetition
        recent_quotes = db.get_recent_quotes(20)
        quote = generate_quote_text(req.seed, recent_quotes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        img_prompt = generate_image_prompt(quote)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Use Google Imagen for background generation
        raw_img_bytes = generate_image_via_imagen(img_prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Use a modest-but-larger text scale so the quote is more prominent.
        # This default produces font sizes comfortably above the 18px floor
        # for common image widths.
        overlay_img_bytes = overlay_text_on_image(raw_img_bytes, quote, text_scale=0.03)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to overlay text: {e}")

    try:
        # First insert the quote to get an ID, then generate filenames
        quote_id = db.insert_quote(
            quote_text=quote,
            raw_image_filename="temp",  # Temporary placeholder
            overlay_image_filename="temp",  # Temporary placeholder
            seed=req.seed,
            image_prompt=img_prompt
        )

        # Generate proper filenames using the quote ID
        raw_filename, overlay_filename = image_storage.generate_filenames(quote_id)

        # Update the database with the actual filenames
        db.update_filenames(quote_id, raw_filename, overlay_filename)

        # Save images to filesystem
        image_storage.save_images(raw_img_bytes, overlay_img_bytes, raw_filename, overlay_filename)

        logger.info(f"Saved quote {quote_id}: '{quote}' with images {raw_filename}, {overlay_filename}")

    except Exception as e:
        logger.exception("Failed to save quote and images: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save quote data: {e}")

    return StreamingResponse(io.BytesIO(overlay_img_bytes), media_type="image/png")


@app.get("/quotes")
def list_quotes(current_user: User = Depends(get_current_active_user)):
    """List all saved quotes with their metadata."""
    try:
        quotes = db.get_all_quotes()
        return {"quotes": quotes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quotes: {e}")


@app.get("/quotes/{quote_id}")
def get_quote(quote_id: int, current_user: User = Depends(get_current_active_user)):
    """Get a specific quote by ID."""
    try:
        quote = db.get_quote_by_id(quote_id)
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        return quote
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quote: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8101)
