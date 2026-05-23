from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class E2ESettings:
    host: str = "127.0.0.1"
    streamlit_port: int = 8521
    fastapi_port: int = 8021
    headless: bool = True
    action_timeout_ms: int = 15_000
    navigation_timeout_ms: int = 30_000
    output_dir: Path = Path("test-results") / "playwright"
    admin_username: str = "admin"
    admin_password: str = "admin123"

    @property
    def streamlit_url(self) -> str:
        return f"http://{self.host}:{self.streamlit_port}"

    @property
    def fastapi_url(self) -> str:
        return f"http://{self.host}:{self.fastapi_port}"

    @property
    def database_url(self) -> str:
        return f"sqlite:///data/test-runtime/e2e-platform-{self.streamlit_port}.db"


def load_settings() -> E2ESettings:
    return E2ESettings(
        streamlit_port=int(os.getenv("E2E_STREAMLIT_PORT", "8521")),
        fastapi_port=int(os.getenv("E2E_FASTAPI_PORT", "8021")),
        headless=os.getenv("E2E_HEADLESS", "true").strip().lower() not in {"0", "false", "no"},
        output_dir=Path(os.getenv("E2E_OUTPUT_DIR", "test-results/playwright")),
        admin_username=os.getenv("E2E_ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("E2E_ADMIN_PASSWORD", os.getenv("AUTH_ADMIN_PASSWORD", "admin123")),
    )
