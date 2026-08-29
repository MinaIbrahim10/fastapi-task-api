import os

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()


def validate_auth_config() -> None:
    """Fail early when required Supabase configuration is missing."""
    missing = []

    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")

    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )

    if not SUPABASE_URL.startswith("https://"):
        raise RuntimeError(
            "SUPABASE_URL must be an HTTPS URL"
        )


validate_auth_config()

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


def auth_config_status() -> dict:
    """
    Return safe configuration metadata.

    Never expose the Supabase key.
    """
    return {
        "configured": True,
        "provider": "supabase",
        "project_url": SUPABASE_URL,
        "key_loaded": bool(SUPABASE_KEY),
    }
