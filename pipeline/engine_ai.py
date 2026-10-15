"""
Multi-LLM Quant Engine
Synthesizes institutional FastExpr alpha formulas using:
- Local Ollama AI (free, open-source, local agent - deepseek-r1, llama3, gemma)
- Google Gemini API
- OpenAI API
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an institutional quantitative researcher developing alphas for WorldQuant BRAIN.
Your goal is to output a single mathematically sound FastExpr expression for equity trading.

Rules:
1. Use standard operators: rank(), ts_delta(), ts_backfill(), ts_mean(), ts_rank(), power(), group_neutralize().
2. For Delay 0 event fields from news18 (e.g. nws18_bee), always aggregate with vec_avg().
3. Pair fundamental/sentiment quality with short-term mean reversion (e.g., -(close - ts_mean(vwap, 2)) / ts_mean(vwap, 2)).
4. Always wrap the final expression with group_neutralize(..., subindustry).
5. Output ONLY the raw formula lines. Do not include markdown codeblocks, explanations, or commentary.
"""

class CloudAIEngine:
    """Multi-LLM quantitative alpha synthesis engine."""

    @staticmethod
    def generate_alpha(
        provider: str = "gemini",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: str = "http://localhost:11434",
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates an alpha formula using the selected provider (gemini [default], openai, or ollama)."""
        prompt = prompt or (
            "Create a high-Sharpe (>2.0) equity alpha expression combining fundamental cash flow or earnings quality "
            "with short-term 2-day VWAP deviation mean-reversion. Use group_neutralize with subindustry."
        )

        provider_clean = (provider or "gemini").lower().strip()

        if provider_clean in ("gemini", "ai", "default"):
            api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini API key is required. Set GEMINI_API_KEY in .env or pass api_key.")
            model_name = model or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{SYSTEM_PROMPT}\n\nTask: {prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 600
                }
            }
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            provider_clean = "gemini"

        elif provider_clean == "ollama":
            model_name = model or os.getenv("OLLAMA_MODEL") or "deepseek-r1:latest"
            url = f"{endpoint.rstrip('/')}/api/generate"
            payload = {
                "model": model_name,
                "prompt": f"{SYSTEM_PROMPT}\n\nTask: {prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.4
                }
            }
            resp = requests.post(url, json=payload, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama error ({resp.status_code}): {resp.text}")
            data = resp.json()
            raw_text = data.get("response", "")

        elif provider_clean == "openai":
            if not api_key:
                raise ValueError("OpenAI API key is required.")
            model_name = model or "gpt-4o-mini"
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 600
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        # Clean code from markdown codeblocks or think tags (DeepSeek R1)
        clean_code = raw_text
        if "</think>" in clean_code:
            clean_code = clean_code.split("</think>")[-1]

        clean_code = clean_code.replace("```python", "").replace("```fastexpr", "").replace("```", "").strip()

        return {
            "name": f"AI_{provider_clean.capitalize()}_Alpha",
            "expr": clean_code,
            "region": "USA",
            "universe": "TOP3000",
            "delay": 1,
            "decay": 20,
            "neutralization": "SUBINDUSTRY",
            "engine": f"ai_{provider_clean}"
        }

    @staticmethod
    def fetch_ollama_models(endpoint: str = "http://localhost:11434") -> List[str]:
        """Queries local Ollama instance for installed models."""
        try:
            url = f"{endpoint.rstrip('/')}/api/tags"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name") for m in data.get("models", [])]
        except Exception as e:
            logger.debug(f"Could not connect to Ollama at {endpoint}: {e}")
        return []

    @staticmethod
    def validate_key(provider: str, api_key: str) -> bool:
        """Pings the API with a tiny prompt to verify key validity."""
        try:
            if provider.lower() == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
                resp = requests.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=10)
                return resp.status_code == 200
            elif provider.lower() == "openai":
                url = "https://api.openai.com/v1/models"
                resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
                return resp.status_code == 200
        except Exception:
            return False
        return False
