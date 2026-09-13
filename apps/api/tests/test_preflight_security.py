import sys
from pathlib import Path

from core.settings import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from preflight_security import checks  # noqa: E402


def test_production_preflight_fails_closed_for_demo_settings():
    result = checks(Settings(MODEL_PROVIDER="mock"), production=True)
    assert not all(item.ok for item in result)
    assert any(item.name == "model" and not item.ok for item in result)


def test_production_preflight_accepts_explicit_secure_settings():
    settings = Settings(
        ENVIRONMENT="production",
        MODEL_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        DATABASE_URL="postgresql://example/db",
        AUTH_COOKIE_SECURE=True,
        AUTH_ALLOWED_ORIGINS="https://app.example.com",
        ENABLE_DEMO_SIMULATION=False,
        ALLOW_MEMORY_CHECKPOINT_FALLBACK=False,
    )
    assert all(item.ok for item in checks(settings, production=True))
