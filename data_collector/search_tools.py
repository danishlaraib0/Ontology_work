"""
search_tools.py
================
Unified search interface combining:
  • Google GenAI (Gemma 4 / Gemini models) with Google Search Grounding
  • Tavily & DuckDuckGo (structured web context)
  • Exponential backoff for rate limit (429 / RESOURCE_EXHAUSTED / 504) handling
  • Groq fallback LLM

All functions are synchronous and robustly retried with progressive backoff.
"""
from __future__ import annotations

import json
import time
import random
import logging
import urllib.request
import urllib.parse
import concurrent.futures
from typing import Any, Callable


from google import genai
from google.genai import types as genai_types
from tavily import TavilyClient

from .config import (
    GEMINI_API_KEY, TAVILY_API_KEY, GROQ_API_KEY, GEMINI_MODEL,
    GEMINI_MODEL_FALLBACK, GEMINI_MODEL_FINAL,
    DDGS_MAX_RESULTS, TAVILY_MAX_RESULTS
)

logger = logging.getLogger(__name__)

# ── Clients ────────────────────────────────────────────────────────────────
_gemini_client: genai.Client | None = None
_tavily_client: TavilyClient | None = None


def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _get_tavily() -> TavilyClient | None:
    global _tavily_client
    if _tavily_client is None and TAVILY_API_KEY:
        _tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    return _tavily_client


# ── Exponential Backoff Core ───────────────────────────────────────────────
def is_rate_limit_or_transient_error(exc: Exception) -> bool:
    """Detect if an exception is due to rate limits or transient gateway issues."""
    if isinstance(exc, (TimeoutError, concurrent.futures.TimeoutError)):
        return True
    err_str = str(exc).upper()
    transient_indicators = [
        "RESOURCE_EXHAUSTED",
        "429",
        "TOO MANY REQUESTS",
        "QUOTA",
        "RATE LIMIT",
        "DEADLINE_EXCEEDED",
        "504",
        "GATEWAY TIMEOUT",
        "UNAVAILABLE",
        "503",
        "500",
        "INTERNAL",
        "SERVER ERROR",
        "CONNECTION RESET",
        "TIMEOUT",
    ]
    return any(ind in err_str for ind in transient_indicators)


def is_fatal_model_error(exc: Exception) -> bool:
    """Detect if model is completely unavailable/deprecated (404/NOT_FOUND)."""
    err_str = str(exc).upper()
    return "404" in err_str or "NOT_FOUND" in err_str or "NOT FOUND" in err_str


def run_with_timeout(func: Callable[[], Any], timeout_sec: float = 180.0) -> Any:
    """Execute a function with a timeout to prevent hanging."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        return future.result(timeout=timeout_sec)


def call_with_exponential_backoff(
    action_name: str,
    func: Callable[[], Any],
    *,
    max_retries: int = 4,
    initial_delay: float = 4.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    per_call_timeout: float = 180.0,
) -> Any:
    """
    Execute a callable with exponential backoff and jitter.
    Progressively increases wait time on 429/quota/transient errors.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return run_with_timeout(func, timeout_sec=per_call_timeout)
        except Exception as exc:
            if is_fatal_model_error(exc):
                logger.warning(f"  ❌ [{action_name}] Fatal model error (404 Not Found): {exc}. Skipping retries.")
                raise exc

            if attempt == max_retries:
                logger.error(f"  ❌ [{action_name}] Exhausted all {max_retries} attempts. Last error: {exc}")
                raise exc

            if is_rate_limit_or_transient_error(exc):
                jitter = random.uniform(0.5, 2.0)
                delay = min(initial_delay * (backoff_factor ** (attempt - 1)) + jitter, max_delay)
                logger.warning(
                    f"  ⏳ [{action_name}] Rate limit / transient error encountered: {type(exc).__name__}."
                    f" Backing off exponentially for {delay:.1f}s before retry ({attempt}/{max_retries})..."
                )
                time.sleep(delay)
            else:
                logger.warning(
                    f"  ⚠️  [{action_name}] Unexpected error: {exc}."
                    f" Waiting 2.0s before retry ({attempt}/{max_retries})..."
                )
                time.sleep(2.0)



# ── DuckDuckGo (best-effort, may fail in sandboxed environments) ───────────
def ddg_search(query: str, max_results: int = DDGS_MAX_RESULTS) -> list[dict]:
    """Run a DuckDuckGo text search. Returns list of {title, url, body}."""
    results = []
    try:
        try:
            from ddgs import DDGS as DDGS2
            with DDGS2() as d:
                for r in d.text(query, max_results=max_results):
                    results.append({
                        "title":  r.get("title", ""),
                        "url":    r.get("href", r.get("url", "")),
                        "body":   r.get("body", ""),
                        "source": "duckduckgo",
                    })
            return results
        except ImportError:
            pass
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":  r.get("title", ""),
                    "url":    r.get("href", ""),
                    "body":   r.get("body", ""),
                    "source": "duckduckgo",
                })
    except Exception as exc:
        logger.warning(f"DDG search failed for '{query}': {exc}")
    return results


# ── Tavily ─────────────────────────────────────────────────────────────────
def tavily_search(query: str, max_results: int = TAVILY_MAX_RESULTS) -> list[dict]:
    """Tavily search — returns richer results with extracted content and backoff."""
    client = _get_tavily()
    if not client:
        logger.info("Tavily key not configured; skipping.")
        return []

    def _do_search():
        resp = client.search(query, max_results=max_results, include_raw_content=False)
        items = []
        for r in resp.get("results", []):
            items.append({
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "body":    r.get("content", ""),
                "score":   r.get("score", 0),
                "source":  "tavily",
            })
        return items

    try:
        return call_with_exponential_backoff(f"TavilySearch('{query[:30]}')", _do_search, max_retries=3, initial_delay=2.0)
    except Exception as exc:
        logger.warning(f"Tavily search failed for '{query}': {exc}")
        return []


# ── Combined search ────────────────────────────────────────────────────────
def combined_search(query: str) -> list[dict]:
    """Run Tavily (primary) and DDG (supplementary); deduplicate by URL."""
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    # Tavily first (fast, structured)
    for r in tavily_search(query):
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            all_results.append(r)

    # If Tavily had few or no results, supplement with DDG
    if len(all_results) < 2:
        for r in ddg_search(query):
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    return all_results



# ── Groq LLM fallback ─────────────────────────────────────────────────────
def groq_complete(prompt: str, *, temperature: float = 0.15, max_tokens: int = 8192) -> str:
    """
    Call Groq API (OpenAI-compatible) as LLM fallback when Google quota is hit.
    """
    if not GROQ_API_KEY:
        logger.warning("Groq API key not set; cannot use fallback.")
        return ""

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps({
        "model": "qwen/qwen3-8b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }).encode()

    def _call_groq():
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        return body["choices"][0]["message"]["content"].strip()

    try:
        return call_with_exponential_backoff("GroqFallback", _call_groq, max_retries=3, initial_delay=3.0)
    except Exception as exc:
        logger.error(f"Groq fallback failed: {exc}")
        return ""


def _extract_response_text(response: Any) -> str:
    """Safely extract text content from a google-genai response object."""
    if not response:
        return ""
    try:
        if getattr(response, "text", None):
            return response.text.strip()
    except Exception:
        pass

    if hasattr(response, "candidates") and response.candidates:
        for cand in response.candidates:
            if hasattr(cand, "content") and cand.content and hasattr(cand.content, "parts") and cand.content.parts:
                parts = [p.text for p in cand.content.parts if getattr(p, "text", None)]
                if parts:
                    return "".join(parts).strip()
    return ""


# ── Plain LLM Call with Exponential Backoff ─────────────────────────────────
def gemini_plain_call(
    prompt: str,
    *,
    model: str = GEMINI_MODEL,
    temperature: float = 0.15,
    max_tokens: int = 8192,
    retries_per_model: int = 2,
) -> str:
    """
    Call LLM WITHOUT grounding tools — fast structured synthesis.
    Cascade: Gemini 3.1 Flash Lite -> Gemini 3.5 Flash Lite -> Gemma 4 -> Groq
    Applies exponential backoff on rate limits / 429s.
    """
    client = _get_gemini()
    _raw_cascade = [model, GEMINI_MODEL_FALLBACK, GEMINI_MODEL_FINAL]
    cascade: list[str] = list(dict.fromkeys(_raw_cascade))

    for current_model in cascade:
        logger.info(f"  🤖 LLM plain call attempting: [{current_model}]")

        def _invoke():
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    top_p=0.95,
                ),
            )
            text = _extract_response_text(response)
            if not text:
                raise ValueError(f"Empty response text received from [{current_model}]")
            return text

        try:
            text = call_with_exponential_backoff(
                f"PlainSynthesis:{current_model}",
                _invoke,
                max_retries=retries_per_model,
                initial_delay=3.0,
                backoff_factor=2.0,
                max_delay=60.0,
            )
            if text:
                logger.info(f"  ✅ LLM plain response received from [{current_model}]")
                return text
        except Exception as exc:
            logger.warning(f"  ⚠️  Model [{current_model}] failed after backoff: {exc}. Advancing cascade...")

    # If all GenAI models fail, try Groq
    logger.warning("  🔄 Google GenAI cascade exhausted. Attempting Groq fallback...")
    groq_resp = groq_complete(prompt, temperature=temperature, max_tokens=max_tokens)
    if groq_resp:
        return groq_resp

    logger.error("❌ All models in cascade exhausted for plain call.")
    return ""


# ── Google Search Grounded Call with Exponential Backoff ────────────────────
def gemini_grounded_search_with_tool(
    prompt: str,
    *,
    model: str = GEMINI_MODEL,
    temperature: float = 0.15,
    max_tokens: int = 8192,
    retries_per_model: int = 2,
) -> str:
    """
    Call model with real-time Google Search Grounding.
    Cascade: Gemma 4 -> Gemini 3.1 Flash Lite -> Gemini 3.5 Flash Lite -> Plain Synthesis
    Applies exponential backoff on rate limits / 429s for each model in cascade.
    """
    client = _get_gemini()
    _raw_cascade = [model, GEMINI_MODEL_FALLBACK, GEMINI_MODEL_FINAL]
    cascade: list[str] = list(dict.fromkeys(_raw_cascade))

    # Phase 1: Try Google Search Grounding across model cascade
    for current_model in cascade:
        logger.info(f"  🌐 Attempting Google Search Grounding with [{current_model}]...")

        def _invoke_grounded():
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    top_p=0.95,
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                ),
            )
            text = _extract_response_text(response)
            if not text:
                raise ValueError(f"Empty grounded response received from [{current_model}]")
            return text

        try:
            text = call_with_exponential_backoff(
                f"GoogleGrounding:{current_model}",
                _invoke_grounded,
                max_retries=retries_per_model,
                initial_delay=3.0,
                backoff_factor=2.0,
                max_delay=60.0,
            )
            if text:
                logger.info(f"  ✅ Google Search Grounded response received from [{current_model}]")
                return text
        except Exception as exc:
            logger.warning(
                f"  ⚠️  Google Grounding with [{current_model}] failed after backoff: {exc}. Advancing cascade..."
            )

    # Phase 2: If grounded tool fails for all models, fallback to plain synthesis with context
    logger.info("  🔄 Grounded search unavailable across cascade — falling back to plain LLM synthesis")
    result = gemini_plain_call(prompt, model=GEMINI_MODEL, temperature=temperature, max_tokens=max_tokens)
    if result:
        return result

    logger.error("❌ All models in cascade exhausted for grounded search.")
    return ""


def gemini_synthesise(
    prompt: str,
    context_chunks: list[str],
    *,
    model: str = GEMINI_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 8192,
) -> str:
    """
    Synthesise information from context_chunks using model cascade with exponential backoff.
    """
    context_text = "\n\n---\n\n".join(context_chunks[:15])  # cap to avoid overflow

    full_prompt = f"""{prompt}

## Retrieved Context

{context_text}

## Instructions
- Base your answer on the context above and automotive domain knowledge.
- Be factual, structured, and specific.
- Output strictly valid JSON where requested.
"""
    return gemini_plain_call(
        full_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
