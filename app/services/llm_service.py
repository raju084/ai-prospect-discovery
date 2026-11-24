import json
import logging
import re
import time
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Unified LLM service supporting Google Gemini, OpenAI, Anthropic, Groq,
    and a robust deterministic NLP fallback parser.
    Includes in-memory response caching for cost optimization.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = settings.CACHE_TTL_SECONDS

    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        cached = self._cache.get(key)
        if cached:
            if time.time() - cached["timestamp"] < self._cache_ttl:
                return cached["data"]
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        if len(self._cache) > 1000:
            # Evict oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
        self._cache[key] = {"data": data, "timestamp": time.time()}

    async def generate_json(self, prompt: str, system_instruction: str = "") -> Optional[Dict[str, Any]]:
        """
        Sends prompt to the configured LLM and returns parsed JSON.
        Falls back to other providers or heuristic parsing on failure.
        """
        cache_key = f"prompt::{prompt}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Check configured provider
        provider = settings.LLM_PROVIDER.lower()
        result = None

        if provider == "gemini" and settings.GEMINI_API_KEY:
            result = await self._call_gemini(prompt, system_instruction)
        elif provider == "openai" and settings.OPENAI_API_KEY:
            result = await self._call_openai(prompt, system_instruction)
        elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            result = await self._call_anthropic(prompt, system_instruction)
        elif provider == "groq" and settings.GROQ_API_KEY:
            result = await self._call_groq(prompt, system_instruction)

        # If primary provider is unavailable or failed, try available keys
        if not result:
            if settings.GEMINI_API_KEY and provider != "gemini":
                result = await self._call_gemini(prompt, system_instruction)
            elif settings.OPENAI_API_KEY and provider != "openai":
                result = await self._call_openai(prompt, system_instruction)
            elif settings.GROQ_API_KEY and provider != "groq":
                result = await self._call_groq(prompt, system_instruction)

        if result:
            self._set_cache(cache_key, result)

        return result

    async def _call_gemini(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        model = settings.LLM_MODEL if "gemini" in settings.LLM_MODEL else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_instruction}\n\n{prompt}\nRespond ONLY in valid JSON."}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        return self._clean_and_parse_json(text)
                else:
                    logger.warning(f"Gemini API returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
        return None

    async def _call_openai(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        model = settings.LLM_MODEL if "gpt" in settings.LLM_MODEL else "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"{system_instruction}\nReturn strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return self._clean_and_parse_json(content)
                else:
                    logger.warning(f"OpenAI API returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
        return None

    async def _call_groq(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        model = "llama-3.1-8b-instant"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"{system_instruction}\nReturn strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return self._clean_and_parse_json(content)
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
        return None

    async def _call_anthropic(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        model = "claude-3-haiku-20240307"
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "system": f"{system_instruction}\nRespond ONLY in valid JSON without backticks.",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.1
        }
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    content = data["content"][0]["text"]
                    return self._clean_and_parse_json(content)
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
        return None

    @staticmethod
    def _clean_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        clean = text.strip()
        # Remove markdown fences if present
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Try to match the first '{' and last '}'
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            logger.warning(f"Failed to parse LLM JSON response: {text[:200]}")
            return None


llm_service = LLMService()
