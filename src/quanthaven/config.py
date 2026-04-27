from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUANTHAVEN_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    artifacts_dir: Path = Field(default=PROJECT_ROOT / "artifacts")
    runtime_dir: Path = Field(default=PROJECT_ROOT / "runtime")
    webhook_secret: str = Field(default="local-demo-secret")
    disable_auth: bool = Field(default=True)
    initial_capital: float = Field(default=10_000.0)
    fee_bps_per_side: float = Field(default=5.0)
    slippage_bps_per_side: float = Field(default=5.0)

    @property
    def backtest_results_path(self) -> Path:
        return self.artifacts_dir / "backtest_results.json"

    @property
    def report_markdown_path(self) -> Path:
        return self.artifacts_dir / "report.md"

    @property
    def report_html_path(self) -> Path:
        return self.artifacts_dir / "report.html"

    @property
    def database_path(self) -> Path:
        return self.runtime_dir / "signals.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    return settings

