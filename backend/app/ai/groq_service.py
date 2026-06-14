"""Groq API integration service using httpx."""

import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


async def generate_groq(
    prompt: str,
    system_instruction: str | None = None,
    json_mode: bool = False,
) -> str:
    """Send a request to Groq's Chat Completion API as a fallback."""
    settings = get_settings()
    api_key = settings.groq_api_key

    if not api_key:
        logger.warning("GROQ_API_KEY is not configured.")
        raise ValueError("GROQ_API_KEY is not configured in settings.")

    url = "https://api.groq.com/openai/v1/chat/completions"

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"Groq API returned error {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
            return text
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing Groq response: {e}. Raw data: {data}")
            raise RuntimeError("Invalid response structure received from Groq API")
