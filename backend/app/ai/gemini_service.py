"""Gemini 2.5 API integration service using httpx."""

import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


async def generate_gemini(
    prompt: str,
    system_instruction: str | None = None,
    json_mode: bool = False,
) -> str:
    """Send a request to Gemini 2.5 Flash API."""
    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured.")
        raise ValueError("GEMINI_API_KEY is not configured in settings.")

    # Using the standard gemini-2.5-flash API endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [
                {"text": system_instruction}
            ]
        }

    if json_mode:
        payload["generationConfig"] = {
            "responseMimeType": "application/json"
        }

    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"Gemini API returned error {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing Gemini response: {e}. Raw data: {data}")
            raise RuntimeError("Invalid response structure received from Gemini API")


async def generate_ai(
    prompt: str,
    system_instruction: str | None = None,
    json_mode: bool = False,
) -> str:
    """Unified AI text generation with Gemini as primary and Groq as fallback."""
    try:
        return await generate_gemini(prompt, system_instruction, json_mode)
    except Exception as e:
        logger.warning(f"Primary Gemini call failed, attempting Groq fallback: {e}")
        from app.ai.groq_service import generate_groq
        try:
            return await generate_groq(prompt, system_instruction, json_mode)
        except Exception as groq_err:
            logger.error(f"Groq fallback also failed: {groq_err}")
            raise RuntimeError(f"AI engines failed: Gemini error: {e}, Groq error: {groq_err}")

