"""
parser.py
==========
Robust JSON extraction from LLM responses.

LLMs sometimes wrap JSON in markdown fences, add preamble text, or return
malformed JSON. This module handles all those cases gracefully.
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Any | None:
    """
    Extract the first valid JSON object or array from a string.
    
    Handles:
      - Bare JSON
      - ```json ... ``` fenced blocks
      - ``` ... ``` fenced blocks
      - JSON embedded in prose
    
    Returns parsed Python object, or None on failure.
    """
    if not text or not text.strip():
        return None

    # 1. Try raw parse first (most common happy-path)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from ```json ... ``` fence
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text, re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3. Try finding first { ... } or [ ... ] block
    for pattern in (
        r"(\{[\s\S]*\})",   # object
        r"(\[[\s\S]*\])",   # array
    ):
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Try to fix common issues: trailing commas, single quotes
                fixed = _attempt_fix(candidate)
                if fixed:
                    return fixed

    logger.warning("Could not extract JSON from LLM response.")
    logger.debug(f"LLM response was:\n{text[:500]}")
    return None


def _attempt_fix(text: str) -> Any | None:
    """Attempt basic JSON repair on malformed strings."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Replace single quotes used as string delimiters (simple heuristic)
    # Only do this if no double quotes present
    if '"' not in text:
        text = text.replace("'", '"')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def safe_parse(raw: str, layer_name: str = "") -> dict | list | None:
    """
    Parse LLM output and log errors with context.
    Returns None if parsing fails completely.
    """
    result = extract_json(raw)
    if result is None:
        logger.error(
            f"[{layer_name}] Failed to parse JSON. "
            f"Raw response (first 300 chars):\n{raw[:300]}"
        )
    return result


def merge_search_context(search_results: list[dict], max_items: int = 8) -> str:
    """
    Convert a list of search result dicts into a readable context string
    for inclusion in LLM prompts.
    """
    lines = []
    for i, r in enumerate(search_results[:max_items], 1):
        title = r.get("title", "")
        url   = r.get("url", "")
        body  = r.get("body", "")[:400]   # truncate per result
        if title or body:
            lines.append(f"[{i}] {title}\nURL: {url}\n{body}\n")
    return "\n".join(lines)

