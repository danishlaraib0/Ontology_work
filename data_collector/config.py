"""
config.py — Load environment variables and expose module-wide settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Locate the project root .env (two levels up from this file) ────────────
_HERE = Path(__file__).resolve().parent          # data_collector/
_ROOT = _HERE.parent                              # project root
_ENV  = _ROOT / ".env"

load_dotenv(dotenv_path=_ENV, override=False)

# ── API Keys ───────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "").strip().strip('"')
TAVILY_API_KEY   = os.environ.get("TAVILY_API_KEY", "").strip().strip('"')
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY",   "").strip().strip('"')

# ── Neo4j Graph DB Config ──────────────────────────────────────────────────
NEO4J_URI        = os.environ.get("NEO4J_URI", "bolt://localhost:7687").strip().strip('"')
NEO4J_USER       = os.environ.get("NEO4J_USER", "neo4j").strip().strip('"')
NEO4J_PASSWORD   = os.environ.get("NEO4J_PASSWORD", "password").strip().strip('"')
NEO4J_DATABASE   = os.environ.get("NEO4J_DATABASE", "neo4j").strip().strip('"')

# ── Model selection ────────────────────────────────────────────────────────
# Primary: gemini-3.1-flash-lite (15 RPM, 250k TPM, 500 RPD)
# Secondary: gemini-3.5-flash-lite
# Tertiary: gemma-4-26b-a4b-it
GEMINI_MODEL          = "gemini-3.1-flash-lite"
GEMINI_MODEL_FALLBACK = "gemini-3.5-flash-lite"
GEMINI_MODEL_FINAL    = "gemma-4-26b-a4b-it"

# ── Output paths ───────────────────────────────────────────────────────────
DATA_DIR = _ROOT / "data_collector" / "output"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Search config ──────────────────────────────────────────────────────────
DDGS_MAX_RESULTS   = 10   # DuckDuckGo results per query
TAVILY_MAX_RESULTS = 5    # Tavily results per query
