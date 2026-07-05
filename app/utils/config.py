"""
RuralCare AI — Application Configuration
Loads all settings from environment variables with safe defaults.
"""

import os
from functools import lru_cache
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Resolve project root from this file's location so all paths work
# regardless of which directory Streamlit / uvicorn is launched from.
_HERE         = os.path.dirname(os.path.abspath(__file__))          # app/utils/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))             # project root

load_dotenv(dotenv_path=os.path.join(_PROJECT_ROOT, ".env"))


@dataclass
class AppConfig:
    # LLM
    llm_provider: str        = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama"))
    anthropic_api_key: str   = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str      = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    google_api_key: str      = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))

    # Ollama
    ollama_base_url: str     = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str        = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2"))
    ollama_embed_model: str  = field(default_factory=lambda: os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))

    # Embeddings provider
    embed_provider: str      = field(default_factory=lambda: os.getenv("EMBED_PROVIDER", "ollama"))

    # Vector DB
    chroma_db_path: str      = field(default_factory=lambda: os.getenv("CHROMA_DB_PATH") or os.path.join(_PROJECT_ROOT, "data", "chroma"))

    # Relational DB
    sqlite_path: str         = field(default_factory=lambda: os.getenv("SQLITE_PATH") or os.path.join(_PROJECT_ROOT, "data", "ruralcare.db"))
    database_url: str        = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # LangSmith
    langsmith_api_key: str   = field(default_factory=lambda: os.getenv("LANGSMITH_API_KEY", ""))
    langsmith_project: str   = field(default_factory=lambda: os.getenv("LANGSMITH_PROJECT", "ruralcare-ai"))

    # Translation
    translate_provider: str  = field(default_factory=lambda: os.getenv("TRANSLATE_PROVIDER", "google"))
    google_translate_key: str = field(default_factory=lambda: os.getenv("GOOGLE_TRANSLATE_API_KEY", ""))

    # Maps
    maps_provider: str       = field(default_factory=lambda: os.getenv("MAPS_PROVIDER", "openstreetmap"))
    google_maps_key: str     = field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY", ""))

    # App
    log_level: str           = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    demo_mode: bool          = field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() == "true")
    max_input_length: int    = field(default_factory=lambda: int(os.getenv("MAX_INPUT_LENGTH", "2000")))
    rag_top_k: int           = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "5")))
    rag_score_threshold: float = field(default_factory=lambda: float(os.getenv("RAG_SCORE_THRESHOLD", "0.65")))


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()
