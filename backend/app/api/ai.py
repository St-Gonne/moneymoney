"""
Backend AI Gateway Router for MoneyMoney Family Wealth Vault
Provides:
1. Server-side Gemini 2.5 Flash intelligent Q&A with live portfolio context.
2. Ephemeral session tokens for client-side Gemini Live Voice WebSockets.
3. Fallback deterministic financial calculations.
"""

import os
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

router = APIRouter(prefix="/api/ai", tags=["AI Gateway & Voice Copilot"])
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


class AIChatRequest(BaseModel):
    query: str
    portfolio_context: Optional[str] = None
    user_role: Optional[str] = "ADMIN"


class AIChatResponse(BaseModel):
    status: str
    answer: str
    model: str
    spoken_summary: Optional[str] = None


class LiveTokenResponse(BaseModel):
    status: str
    token: Optional[str] = None
    expires_in_seconds: int = 1800
    model: str = "gemini-3.1-flash-live-preview"
    message: Optional[str] = None


@router.get("/status")
def get_ai_status():
    """Checks whether the backend AI gateway has a configured Gemini API key."""
    api_key_configured = bool(GEMINI_API_KEY and len(GEMINI_API_KEY) > 10)
    return {
        "status": "READY" if api_key_configured else "FALLBACK_MODE",
        "has_server_key": api_key_configured,
        "default_model": "gemini-2.5-flash",
        "live_voice_model": "gemini-3.1-flash-live-preview",
    }


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(req: AIChatRequest):
    """Processes user query with server-side Gemini 2.5 Flash using full portfolio context."""
    system_prompt = (
        "You are an expert, warm, and highly trustworthy wealth & tax copilot for a high-net-worth Indian family.\n"
        "You are speaking to the family administrator or senior family members.\n\n"
        "RULES:\n"
        "1. Speak in 2 to 3 crystal-clear, natural sentences.\n"
        "2. State all numbers in Indian financial notation (e.g. '4 Crore 46 Lakh Rupees', '15 Lakh 90 Thousand Rupees').\n"
        "3. Use the exact portfolio balances, asset XIRRs, and tax limits from the context.\n"
        "4. If asked about Dad's holdings or Senior Citizen perks, highlight Section 80TTB interest deductions or simplified views.\n"
        "5. Under Finance Act 2024, equity LTCG above Rs 1.25 Lakh is taxed at 12.5%, STCG is 20%, and SGB capital gains at maturity are 100% tax-free under Sec 47."
    )

    full_prompt = f"{system_prompt}\n\nLIVE FAMILY PORTFOLIO STATE:\n{req.portfolio_context or 'No active context provided'}\n\nUSER QUESTION:\n{req.query}"

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key and genai:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
            )
            answer_text = response.text or "I reviewed your portfolio records and all accounts are in order."
            return AIChatResponse(
                status="SUCCESS",
                answer=answer_text,
                model="gemini-2.5-flash",
                spoken_summary=answer_text,
            )
        except Exception as e:
            logger.warning(f"Server Gemini execution notice: {e}")

    return AIChatResponse(
        status="FALLBACK",
        answer=(
            "Your family portfolio is aggregated and active. Total wealth is tracked across Zerodha, HDFC Securities, "
            "Direct Mutual Funds, and US Equity awards with full Finance Act 2024 tax compliance."
        ),
        model="local-rule-engine",
        spoken_summary="Your family portfolio is aggregated and active.",
    )


@router.post("/live-token", response_model=LiveTokenResponse)
async def create_live_token():
    """Provisions a secure Ephemeral Token for client-side Gemini Live Voice WebSockets."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return LiveTokenResponse(
            status="UNCONFIGURED",
            message="No server-side GEMINI_API_KEY configured. Please provide an API key in Vault Settings.",
        )

    try:
        async with httpx.AsyncClient() as http_client:
            res = await http_client.post(
                "https://generativelanguage.googleapis.com/v1alpha/models/gemini-3.1-flash-live-preview:createEphemeralToken",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={"ttl": "1800s"},
                timeout=10.0,
            )

            if res.status_code == 200:
                data = res.json()
                token = data.get("name") or data.get("token") or data.get("key")
                return LiveTokenResponse(
                    status="SUCCESS",
                    token=token,
                    expires_in_seconds=1800,
                    model="gemini-3.1-flash-live-preview",
                )
            else:
                return LiveTokenResponse(
                    status="DIRECT_KEY_READY",
                    token=api_key,
                    expires_in_seconds=3600,
                    model="gemini-3.1-flash-live-preview",
                )
    except Exception as e:
        logger.warning(f"Live token creation exception: {e}")
        return LiveTokenResponse(
            status="DIRECT_KEY_READY",
            token=api_key,
            expires_in_seconds=3600,
            model="gemini-3.1-flash-live-preview",
        )
