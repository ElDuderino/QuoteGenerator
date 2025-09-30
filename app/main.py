import os
import io
import textwrap
from typing import Optional

from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from PIL import Image, ImageDraw, ImageFont

from dotenv import load_dotenv
from openai import OpenAI
import logging
import random

from app.image_prompt_generator import build_image_prompt_instructions
from app.database import QuoteDatabase
from app.filesystem import ImageStorage
from app.auth_funcs import router as auth_router, User, get_current_active_user

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


def _get_openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")
    return key


def generate_quote_text(seed: Optional[str] = None) -> str:
    key = _get_openai_api_key()

    system = (
        "You are a helpful assistant that produces a single concise quote that is: random, daily, wise, likely to go viral, and actionable business advice. Return only the quote text, do not include quotation marks or attribution."
    )

    user_prompt = "Create one short (max 20 words) business advice quote"
    if seed:
        user_prompt += f" inspired by: {seed}"
    
    # Get recent quotes to avoid repetition
    recent_quotes = db.get_recent_quotes(20)
    if recent_quotes:
        recent_quote_texts = [q['quote_text'] for q in recent_quotes]
        user_prompt += f"\n\nDO NOT create anything similar to these recent quotes: {', '.join(recent_quote_texts[:10])}"

    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=1.2
        )

        # New SDK returns choices with message content
        quote = resp.choices[0].message.content.strip()

        # Keep only first line
        quote = quote.splitlines()[0]
        return quote
    except Exception as e:
        raise RuntimeError(f"OpenAI quote generation failed: {e}")

def generate_image_prompt(quote_text: Optional[str] = None) -> str:
    key = _get_openai_api_key()

    system = (
        """You are a helpful assistant that produces prompts for AIs to create the most amazing viral images for quotes
        You have expert knowledge of what makes an image shareable and viral"
        You are a marketing wizard and will make images that are shared everywhere"""
    )

    final_instructions = build_image_prompt_instructions(quote=quote_text)

    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": final_instructions},
            ],
            temperature=0.6
        )

        # New SDK returns choices with message content
        generated_prompt = resp.choices[0].message.content.strip()

        # Keep only first line
        generated_prompt = generated_prompt.splitlines()[0]
        
        # Log the generated prompt
        logger.info("Generated image prompt: %s", generated_prompt)
        
        return generated_prompt
    except Exception as e:
        raise RuntimeError(f"OpenAI image prompt generation failed: {e}")



def generate_image_via_imagen(prompt: str) -> bytes:
    """
    Generate an image using Google Imagen / Generative Images API.

    The function expects an API key in IMAGEN_API_KEY or GOOGLE_API_KEY and an
    endpoint URL in IMAGEN_ENDPOINT (optional). If IMAGEN_ENDPOINT is not set,
    a reasonable default is used but you should set the correct endpoint for
    your account. Environment variables are loaded from .env at startup.
    """
    # Prefer GEMINI_API_KEY (used in the genai examples), then fall back to
    # IMAGEN_API_KEY or GOOGLE_API_KEY.
    key = os.getenv("GEMINI_API_KEY") or os.getenv("IMAGEN_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or IMAGEN_API_KEY or GOOGLE_API_KEY environment variable is required for Imagen generation")

    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        logger.exception("google-genai library is required for Imagen generation: %s", e)
        raise RuntimeError("google-genai package is required. Install with: pip install google-genai")

    try:
        # instantiate client with provided API key
        client = genai.Client(api_key=key)

        logger.info("Calling Google GenAI generate_images model for prompt (len=%d)", len(prompt))
        # Generate a random seed for reproducible image variation
        seed = random.randint(0, 2**32 - 1)
        logger.info("Using seed %d for Imagen image generation", seed)

        result = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
                # allow person generation as needed; adjust as required
                person_generation=types.PersonGeneration.ALLOW_ADULT,
                aspect_ratio="1:1",
            ),
        )

        if not getattr(result, "generated_images", None):
            logger.error("Imagen returned no generated_images: %s", result)
            raise RuntimeError("Imagen API returned no images")

        # Use the first generated image
        generated_image = result.generated_images[0]
        image_bytes = getattr(getattr(generated_image, "image", None), "image_bytes", None)
        if not image_bytes:
            logger.error("Imagen response missing image bytes: %s", generated_image)
            raise RuntimeError("Imagen did not return image bytes")

        return bytes(image_bytes)
    except Exception as e:
        logger.exception("Imagen image generation failed: %s", e)
        raise RuntimeError(f"Imagen image generation failed: {e}")


def overlay_text_on_image(image_bytes: bytes, text: str, text_scale: float = 0.03) -> bytes:
    with Image.open(io.BytesIO(image_bytes)).convert("RGBA") as base:
        width, height = base.size

        txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt)

        # Choose a font size based on image width and provided text_scale
        try:
            # text_scale is fraction of image width used to estimate font size
            # Ensure a sensible minimum so text isn't tiny on small images.
            # Increase the guaranteed floor to 18px so shorter images render
            # noticeably larger text by default.
            font_size = max(18, int(width * text_scale))

            # Try common font locations (prefer bold). Also try a few common
            # font file names which Pillow can often resolve (e.g. bundled
            # DejaVuSans). This increases the chance of getting a scalable
            # TrueType font instead of falling back to the tiny bitmap default.
            font = None
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            ]
            for path in font_paths:
                if os.path.exists(path):
                    try:
                        font = ImageFont.truetype(path, font_size)
                        break
                    except Exception:
                        continue

            # Try a few common font names that Pillow may be able to locate
            # from its bundled fonts or the system font path.
            if font is None:
                for name in [
                    "DejaVuSans-Bold.ttf",
                    "DejaVuSans.ttf",
                    "LiberationSans-Bold.ttf",
                    "LiberationSans-Regular.ttf",
                    "FreeSans.ttf",
                    "Arial.ttf",
                ]:
                    try:
                        font = ImageFont.truetype(name, font_size)
                        break
                    except Exception:
                        continue

            # Final fallback to the default bitmap font (rare). Keep it, but
            # try hard to avoid it because it cannot be resized.
            if font is None:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Helper to compute text size in a Pillow-version-compatible way
        def _text_size(draw_obj, s, fnt):
            # Preferred: textbbox (returns left, top, right, bottom)
            if hasattr(draw_obj, "textbbox"):
                l, t, r, b = draw_obj.textbbox((0, 0), s, font=fnt)
                return (r - l, b - t)
            # Fallback to textsize (older Pillow)
            if hasattr(draw_obj, "textsize"):
                return draw_obj.textsize(s, font=fnt)
            # Fallback to font.getsize
            if hasattr(fnt, "getsize"):
                return fnt.getsize(s)
            # As a last resort, estimate
            return (len(s) * 8, 12)

        # Wrap text to fit pixel width using the chosen font
        max_text_width = int(width * 0.82)
        def wrap_text_by_pixel(draw_obj, text, fnt, max_width_px):
            words = text.split()
            if not words:
                return [""]
            lines = []
            current = words[0]
            for w in words[1:]:
                cand = current + " " + w
                w_px, _ = _text_size(draw_obj, cand, fnt)
                if w_px <= max_width_px:
                    current = cand
                else:
                    lines.append(current)
                    current = w
            lines.append(current)
            return lines

        lines = []
        for paragraph in text.split("\n"):
            lines.extend(wrap_text_by_pixel(draw, paragraph, font, max_text_width))


        # Compute total text height
        line_heights = [_text_size(draw, line, font)[1] for line in lines]
        total_text_height = sum(line_heights) + (len(lines) - 1) * 8

        # If the chosen font is very small (for example when Pillow falls
        # back to its bitmap default font), scale up the rendered text by
        # drawing it on a temporary image and then upscaling that region.
        # This ensures a minimum readable size even when a TrueType font is
        # not available on the host system.
        sample_h = line_heights[0] if line_heights else 0
        upscale_layer = None
        upscale_factor = 1
        MIN_PX = 14
        if sample_h < MIN_PX:
            # Compute integer upscale factor to reach at least MIN_PX
            import math
            upscale_factor = max(1, math.ceil(MIN_PX / max(1, sample_h)))
            # Create a small temporary RGBA image containing only the text
            text_block_height = total_text_height + int(font_size * 1.2)
            text_block = Image.new("RGBA", (width, text_block_height), (0, 0, 0, 0))
            tb_draw = ImageDraw.Draw(text_block)

            # Draw semi-transparent rectangle and text onto the small block
            padding_x = int(width * 0.06)
            padding_y = int(font_size * 0.6)
            rect_top_local = 0
            rect_left_local = padding_x
            rect_right_local = width - padding_x
            rect_bottom_local = text_block_height
            tb_draw.rectangle([rect_left_local, rect_top_local, rect_right_local, rect_bottom_local], fill=(0, 0, 0, 180))

            y_local = int(padding_y * 0.3)
            for line in lines:
                w, h = _text_size(tb_draw, line, font)
                x_local = (width - w) // 2
                tb_draw.text((x_local, y_local), line, font=font, fill=(255, 255, 255, 255))
                y_local += h + int(font_size * 0.2)

            # Upscale the text block
            new_size = (text_block.width * upscale_factor, text_block.height * upscale_factor)
            upscale_layer = text_block.resize(new_size, resample=Image.NEAREST)
            # Adjust total_text_height to the upscaled height for positioning
            total_text_height = upscale_layer.height

        # Position text centered vertically and horizontally
        y = (height - total_text_height) // 2

        if upscale_layer is not None:
            # Paste the pre-rendered & upscaled text block centered vertically
            x_paste = (width - upscale_layer.width) // 2
            y_paste = y
            txt.paste(upscale_layer, (x_paste, y_paste), upscale_layer)
        else:
            # Draw semi-transparent rectangle behind text for readability
            padding_x = int(width * 0.06)
            padding_y = int(font_size * 0.6)
            rect_top = y - padding_y
            rect_left = padding_x
            rect_right = width - padding_x
            rect_bottom = y + total_text_height + padding_y
            # Slightly stronger background for readability on busy images
            draw.rectangle([rect_left, rect_top, rect_right, rect_bottom], fill=(0, 0, 0, 180))

            # Draw each line centered
            for line in lines:
                w, h = _text_size(draw, line, font)
                x = (width - w) // 2
                draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
                y += h + int(font_size * 0.2)

        out = Image.alpha_composite(base, txt).convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()


@app.post("/quote-image")
def quote_image(req: QuoteRequest, current_user: User = Depends(get_current_active_user)):
    try:
        quote = generate_quote_text(req.seed)
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
