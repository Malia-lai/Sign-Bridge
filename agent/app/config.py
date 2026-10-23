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
        self.TEMPERATURE = self.temperature


settings = Settings()
config = settings
Config = Settings


def get_settings() -> Settings:
    return settings
