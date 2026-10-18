"""Shared optional .env configuration for native Python entry points."""
from pathlib import Path
from dotenv import load_dotenv


def load_environment(path=None):
    # Use only this project's .env, never search parent folders. Compose settings
    # and explicit environment variables always take precedence over the file.
    env_path=Path(path) if path is not None else Path(__file__).resolve().parent.parent/'.env'
    return load_dotenv(env_path,override=False,interpolate=False,encoding='utf-8')
