import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


class Settings:
    def __init__(self) -> None:
        self.output_language = _env("OUTPUT_LANGUAGE", "OUTPUT_LANG", "LANGUAGE", default="English")
        self.model_name = _env("MODEL_NAME", "LLM_MODEL", "MISTRAL_MODEL", default="mistral-small-latest")
        self.timeout = float(_env("TIMEOUT", "LLM_TIMEOUT", "REQUEST_TIMEOUT", default="30"))
        self.confidence_threshold = float(_env("CONFIDENCE_THRESHOLD", "CONFIDENCE", default="0.7"))
        self.mock_mode = _bool(_env("MOCK_MODE", default="false"))
        self.max_retries = int(_env("MAX_RETRIES", "RETRIES", default="3"))
        self.requests_per_minute = int(_env("REQUESTS_PER_MINUTE", default="30"))
        self.tokens_per_minute = int(_env("TOKENS_PER_MINUTE", default="14000"))
        self.max_output_tokens = int(_env("MAX_OUTPUT_TOKENS", default="1024"))
        self.mistral_api_key = _env("MISTRAL_API_KEY", "API_KEY", default="")
        self.temperature = float(_env("TEMPERATURE", default="0.1"))
        self.llm_provider = _env("LLM_PROVIDER", default="mistral").lower()
        self.gemini_api_key = _env("GEMINI_API_KEY", default="")
        self.gemini_model = _env("GEMINI_MODEL", default="")
        self.fallback_provider = _env("FALLBACK_PROVIDER", default="").lower()
        self.api_key = _env("API_KEY", "AGENT_API_KEY", default="")
        self.debug = _bool(_env("DEBUG", default="false"))
        self.rate_limit_per_minute = int(_env("RATE_LIMIT_PER_MINUTE", "IP_RATE_LIMIT", default="60"))
        self.max_words = int(_env("MAX_WORDS", "MAX_WORD_COUNT", default="100"))
        self.buffer_size = int(_env("BUFFER_SIZE", "WORD_BUFFER_SIZE", default="10"))
        self.cache_size = int(_env("CACHE_SIZE", "SENTENCE_CACHE_SIZE", default="128"))
        self.agent_retries = int(_env("AGENT_RETRIES", "AGENT_MAX_RETRIES", default="2"))
        self.fallback_to_mock = _bool(_env("FALLBACK_TO_MOCK", default="true"))
        self.emergency_keywords = _env("EMERGENCY_KEYWORDS", default="help,pain,danger,emergency,urgent,sos")
        self.supported_languages = _env("SUPPORTED_LANGUAGES", default="")
        self.history_size = int(_env("HISTORY_SIZE", "MAX_HISTORY", default="1000"))
        self.vocabulary_path = _env("VOCABULARY_PATH", "VOCAB_PATH", default="")
        self.prompt_template_path = _env("PROMPT_TEMPLATE_PATH", "SYSTEM_PROMPT_PATH", default="")
        self.prompt_templates_dir = _env("PROMPT_TEMPLATES_DIR", default="")
        self.prompt_ab_enabled = _bool(_env("PROMPT_AB_ENABLED", default="false"))
        self.prompt_variants = _env("PROMPT_VARIANTS", default="A,B")
        self.correction_learning = _bool(_env("CORRECTION_LEARNING", "LEARN_FROM_CORRECTIONS", default="true"))
        self.log_level = _env("LOG_LEVEL", default="INFO").upper()
        self.log_format = _env("LOG_FORMAT", default="console").lower()
        self.cors_origins = _env("CORS_ORIGINS", "ALLOWED_ORIGINS", "CORS_ALLOWED_ORIGINS", default="*")
        # uppercase aliases for env-style access
        self.OUTPUT_LANGUAGE = self.output_language
        self.MODEL_NAME = self.model_name
        self.TIMEOUT = self.timeout
        self.CONFIDENCE_THRESHOLD = self.confidence_threshold
        self.MOCK_MODE = self.mock_mode
        self.MISTRAL_API_KEY = self.mistral_api_key
        self.MAX_RETRIES = self.max_retries
        self.REQUESTS_PER_MINUTE = self.requests_per_minute
        self.TOKENS_PER_MINUTE = self.tokens_per_minute
        self.MAX_OUTPUT_TOKENS = self.max_output_tokens
        self.LLM_PROVIDER = self.llm_provider
        self.GEMINI_API_KEY = self.gemini_api_key
        self.GEMINI_MODEL = self.gemini_model
        self.FALLBACK_PROVIDER = self.fallback_provider
        self.API_KEY = self.api_key
        self.DEBUG = self.debug
        self.RATE_LIMIT_PER_MINUTE = self.rate_limit_per_minute
        self.LOG_LEVEL = self.log_level
        self.LOG_FORMAT = self.log_format
        self.CORS_ORIGINS = self.cors_origins
        self.ALLOWED_ORIGINS = self.cors_origins
        self.MAX_WORDS = self.max_words
        self.BUFFER_SIZE = self.buffer_size
        self.CACHE_SIZE = self.cache_size
        self.AGENT_RETRIES = self.agent_retries
        self.FALLBACK_TO_MOCK = self.fallback_to_mock
        self.EMERGENCY_KEYWORDS = self.emergency_keywords
        self.SUPPORTED_LANGUAGES = self.supported_languages
        self.HISTORY_SIZE = self.history_size
        self.VOCABULARY_PATH = self.vocabulary_path
        self.PROMPT_TEMPLATE_PATH = self.prompt_template_path
        self.PROMPT_TEMPLATES_DIR = self.prompt_templates_dir
        self.PROMPT_AB_ENABLED = self.prompt_ab_enabled
        self.PROMPT_VARIANTS = self.prompt_variants
        self.CORRECTION_LEARNING = self.correction_learning
        self.TEMPERATURE = self.temperature


settings = Settings()
config = settings
Config = Settings


def get_settings() -> Settings:
    return settings
