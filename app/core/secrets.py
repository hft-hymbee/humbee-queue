"""
Secrets Manager
===============
Loads secrets from either a local secrets.json file (for LOCAL development)
or AWS Secrets Manager (in PROD).

Usage:
    from core.secrets import secrets_manager
    smtp_user = secrets_manager.get_secret("smtp", "username")
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger("core.secrets")


class SecretsManager:
    """
    Two-layer secrets management:
      ENV=LOCAL  → Load from secrets.json (gitignored)
      ENV=QA     → Load from AWS Secrets Manager: "humbee-queue-qa-secret-json"
      ENV=PROD   → Load from AWS Secrets Manager: "humbee-queue-prod-secret-json"
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

        In QA/PROD mode, reads from AWS Secrets Manager:
            secrets_manager.get_secret("smtp", "username")
            → reads parsed JSON secret value
        """
        if self.env == "LOCAL":
            return self._load_from_local(group, key)
        else:
            return self._load_from_aws(group, key)

    def _load_from_local(self, group: str, key: str) -> Any:
        """Load secrets from the local secrets.json file."""
        if not self._cache:
            secrets_path = os.getenv("SECRETS_FILE_PATH", "secrets.json")
            try:
                with open(secrets_path) as f:
                    self._cache = json.load(f)
            except FileNotFoundError:
                logger.error(
                    f"secrets.json not found at '{secrets_path}'. "
                    f"Copy secrets.json.example to secrets.json and fill in values."
                )
                raise FileNotFoundError(
                    f"secrets.json not found at '{secrets_path}'. "
                    f"Copy secrets.json.example to secrets.json and fill in values."
                )
        try:
            return self._cache[group][key]
        except KeyError:
            logger.error(f"Secret not found in local file: secrets.json['{group}']['{key}'] does not exist")
            raise KeyError(
                f"Secret not found: secrets.json['{group}']['{key}'] does not exist."
            )

    def _load_from_aws(self, group: str, key: str) -> Any:
        """Load secrets from AWS Secrets Manager."""
        if not self._cache:
            import boto3
            
            secret_name_map = {
                "QA": "humbee-queue-qa-secret-json",
                "PROD": "humbee-queue-prod-secret-json",
            }
            
            if self.env not in secret_name_map:
                logger.error(f"Unsupported environment for AWS Secrets Manager: {self.env}")
                raise ValueError(f"Unsupported environment for AWS Secrets Manager: {self.env}")
                
            secret_name = secret_name_map[self.env]
            aws_region = os.getenv("AWS_REGION", "ap-south-1")
            
            session = boto3.Session(region_name=aws_region)
            client = session.client("secretsmanager")
            
            try:
                response = client.get_secret_value(SecretId=secret_name)
                secret_string = response.get("SecretString")
                if not secret_string:
                    logger.error(f"SecretString is empty for secret: {secret_name}")
                    raise ValueError(f"SecretString is empty for secret: {secret_name}")
                self._cache = json.loads(secret_string)
            except Exception as e:
                logger.error(f"Failed to fetch secret '{secret_name}' from AWS Secrets Manager: {e}")
                raise RuntimeError(f"Failed to fetch secret '{secret_name}' from AWS Secrets Manager: {e}")

        try:
            return self._cache[group][key]
        except KeyError:
            logger.error(f"Secret not found in AWS secret: ['{group}']['{key}'] does not exist")
            raise KeyError(
                f"Secret not found: AWS Secret ['{group}']['{key}'] does not exist."
            )


# Singleton instance
secrets_manager = SecretsManager()
