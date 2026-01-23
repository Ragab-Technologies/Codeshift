"""API configuration settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Configuration settings for the PyResolve API."""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_unlimited: str = ""

    # Anthropic (for server-side LLM calls)
    anthropic_api_key: str = ""

    # API settings
    pyresolve_api_url: str = "https://py-resolve.replit.app"
    api_key_prefix: str = "pyr_"

    # Tier quotas
    tier_free_files: int = 100
    tier_free_llm_calls: int = 50
    tier_pro_files: int = 1000
    tier_pro_llm_calls: int = 500
    tier_unlimited_files: int = 999999999
    tier_unlimited_llm_calls: int = 999999999

    # Environment
    environment: str = "development"

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "extra": "ignore",
    }

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def get_tier_limits(self, tier: str) -> dict[str, int]:
        """Get quota limits for a tier."""
        limits = {
            "free": {
                "files_per_month": self.tier_free_files,
                "llm_calls_per_month": self.tier_free_llm_calls,
            },
            "pro": {
                "files_per_month": self.tier_pro_files,
                "llm_calls_per_month": self.tier_pro_llm_calls,
            },
            "unlimited": {
                "files_per_month": self.tier_unlimited_files,
                "llm_calls_per_month": self.tier_unlimited_llm_calls,
            },
        }
        return limits.get(tier, limits["free"])


@lru_cache
def get_settings() -> APISettings:
    """Get cached API settings."""
    return APISettings()
