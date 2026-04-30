"""
Secrets Manager
===============
Loads secrets from either a local secrets.json file (for LOCAL development)
or from environment variables (K8s Secrets in PROD).

Usage:
    from core.secrets import secrets_manager
    smtp_user = secrets_manager.get_secret("smtp", "username")
"""

import json
import os
from typing import Any


class SecretsManager:
    """
    Two-layer secrets management:
      ENV=LOCAL  → Load from secrets.json (gitignored)
      ENV=PROD   → K8s Secrets mounted as environment variables
    """

    def __init__(self):
        self.env = os.getenv("ENV", "LOCAL")
        self._cache: dict = {}

    def get_secret(self, group: str, key: str) -> Any:
        """
        Get a secret value by group and key.

        In LOCAL mode, reads from secrets.json:
            secrets_manager.get_secret("smtp", "username")
            → reads secrets.json["smtp"]["username"]

        In PROD mode, reads from environment variables:
            secrets_manager.get_secret("smtp", "username")
            → reads os.environ["SMTP_USERNAME"]
        """
        if self.env == "LOCAL":
            return self._load_from_json(group, key)
        else:
            env_key = f"{group.upper()}_{key.upper()}"
            value = os.environ.get(env_key)
            if value is None:
                raise KeyError(
                    f"Secret not found: env var '{env_key}' is not set. "
                    f"Ensure K8s Secret is mounted correctly."
                )
            return value

    def _load_from_json(self, group: str, key: str) -> Any:
        """Load secrets from the local secrets.json file."""
        if not self._cache:
            secrets_path = os.getenv("SECRETS_FILE_PATH", "secrets.json")
            try:
                with open(secrets_path) as f:
                    self._cache = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"secrets.json not found at '{secrets_path}'. "
                    f"Copy secrets.json.example to secrets.json and fill in values."
                )
        try:
            return self._cache[group][key]
        except KeyError:
            raise KeyError(
                f"Secret not found: secrets.json['{group}']['{key}'] does not exist."
            )


# Singleton instance
secrets_manager = SecretsManager()
