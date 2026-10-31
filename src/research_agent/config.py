"""Central configuration and environment loader."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, ValidationError


def parse_dotenv(content: str) -> dict[str, str]:
    """Parse simple key-value pairs from .env content without third-party dependencies."""
    parsed: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()

        # Handle comments for unquoted values
        if not (val.startswith(('"', "'")) and len(val) >= 2):
            val = val.split(" #", 1)[0].split("\t#", 1)[0].strip()

        # Strip surrounding matching quotes
        if len(val) >= 2 and ((val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'"))):
            val = val[1:-1]

        if key:
            parsed[key] = val
    return parsed


class Settings(BaseModel):
    """Central settings model for budgets, limits, and runtime configuration."""
    model_config = ConfigDict(extra="ignore")

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"
    llm_min_interval_s: float = 6.5
    llm_extra_body: str = ""
    llm_json_mode: bool = True
    llm_price_in_per_m: float = 0.30
    llm_price_out_per_m: float = 2.50
    llm_max_tokens: int = 4096
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2
    tavily_api_key: str = ""

    min_question_chars: int = 8
    max_question_chars: int = 500
    request_timeout_s: float = 30.0
    max_steps: int = 5
    max_tool_calls: int = 12

    tool_timeout_s: float = 10.0
    tool_max_retries: int = 2
    max_download_bytes: int = 2 * 1024 * 1024
    page_char_limit: int = 6000
    search_results_per_query: int = 5
    cache_ttl_s: int = 86400
    cache_dir: str = ".cache"
    runs_dir: str = "runs"
    faults: list[str] = Field(default_factory=list)

    min_source_score: float = 0.25
    max_sources_per_domain: int = 2
    max_sources_for_synthesis: int = 8

    parallelism: int = 4
    max_pages_to_fetch: int = 6
    run_deadline_s: float = 150.0
    max_follow_up_rounds: int = 1

    @classmethod
    def from_env(cls, env_path: str | Path | None = ".env") -> Settings:
        """Load settings from OS environment with fallback to an optional .env file."""
        merged: dict[str, Any] = {}

        # 1. Read .env file if it exists
        if env_path:
            p = Path(env_path)
            if p.is_file():
                merged.update(parse_dotenv(p.read_text(encoding="utf-8")))

        # 2. Existing OS environment variables take precedence
        for key, val in os.environ.items():
            merged[key] = val

        # Map case-insensitively to model fields
        field_values: dict[str, Any] = {}
        for field_name in cls.model_fields.keys():
            upper = field_name.upper()
            if upper in merged:
                field_values[field_name] = merged[upper]
            elif field_name in merged:
                field_values[field_name] = merged[field_name]

        # Support RA_FAULTS / FAULTS comma-separated list
        raw_faults = merged.get("RA_FAULTS") or merged.get("FAULTS")
        if raw_faults:
            if isinstance(raw_faults, str):
                field_values["faults"] = [f.strip() for f in raw_faults.split(",") if f.strip()]
            elif isinstance(raw_faults, list):
                field_values["faults"] = raw_faults

        return cls(**field_values)

