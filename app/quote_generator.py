"""Quote generation module."""
import os
from typing import Optional

from openai import OpenAI


def _get_openai_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")
    return key


def generate_quote_text(seed: Optional[str] = None, recent_quotes: Optional[list] = None) -> str:
    """Generate a business quote using OpenAI GPT-4.

    Args:
        seed: Optional seed text to inspire the quote
        recent_quotes: Optional list of recent quote dicts to avoid repetition

    Returns:
        Generated quote text

    Raises:
        RuntimeError: If quote generation fails
    """
    key = _get_openai_api_key()

    system = (
        "You are a helpful assistant that produces a single concise quote that is: random, daily, wise, likely to go viral, and actionable business advice. Return only the quote text, do not include quotation marks or attribution."
    )

    user_prompt = "Create one short (max 20 words) business advice quote"
    if seed:
        user_prompt += f" inspired by: {seed}"

    # Add recent quotes to avoid repetition
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
    """Generate an image prompt for the given quote using OpenAI GPT-4.

    Args:
        quote_text: The quote text to generate an image prompt for

    Returns:
        Generated image prompt

    Raises:
        RuntimeError: If image prompt generation fails
    """
    from app.image_prompt_generator import build_image_prompt_instructions
    import logging

    logger = logging.getLogger(__name__)
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
