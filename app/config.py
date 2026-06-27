import os
import logging
from dotenv import load_dotenv

# Configure a startup logger for configuration validations
logger = logging.getLogger("config_initializer")

# Load environment variables from .env file if it exists
load_dotenv()

class Settings:
    def __init__(self):
        self.gitlab_api_url = os.getenv("GITLAB_API_URL", "https://gitlab.com").rstrip("/")
        self._gitlab_access_token = os.getenv("GITLAB_ACCESS_TOKEN")
        self._gitlab_webhook_secret = os.getenv("GITLAB_WEBHOOK_SECRET")
        self.gitlab_bot_username = os.getenv("GITLAB_BOT_USERNAME")
        self.rules_file_path = os.getenv("RULES_FILE_PATH", "config/rules.yaml")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.disable_loop_prevention = os.getenv("DISABLE_LOOP_PREVENTION", "false").lower() in ("true", "1", "yes")

        self._validate_settings()

    def _validate_settings(self):
        """
        Performs validation on runtime configuration settings.
        Ensures correct formats and security practices on startup.
        """
        # Validate GitLab API URL
        if not (self.gitlab_api_url.startswith("http://") or self.gitlab_api_url.startswith("https://")):
            raise ValueError(
                f"Configuration Error: Invalid GITLAB_API_URL '{self.gitlab_api_url}'. "
                f"URL must start with 'http://' or 'https://'."
            )

        # Validate Logging Level
        allowed_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in allowed_log_levels:
            raise ValueError(
                f"Configuration Error: Invalid LOG_LEVEL '{self.log_level}'. "
                f"Must be one of: {', '.join(allowed_log_levels)}."
            )

        # Security check: warn if token is missing
        # Token validation is deferred to property access, but we check and warn here
        if not self._gitlab_access_token:
            logger.warning("Security Warning: GITLAB_ACCESS_TOKEN is not set. Requests to GitLab API will fail.")

        # Security check: validate webhook secret strength
        if self._gitlab_webhook_secret:
            if len(self._gitlab_webhook_secret) < 16:
                logger.warning(
                    "Security Warning: GITLAB_WEBHOOK_SECRET is set but is too short (< 16 characters). "
                    "Use a stronger secret to prevent brute-force token matching."
                )

    @property
    def gitlab_access_token(self) -> str:
        if not self._gitlab_access_token:
            raise ValueError("Configuration Error: GITLAB_ACCESS_TOKEN environment variable is not set.")
        return self._gitlab_access_token

    @property
    def gitlab_webhook_secret(self) -> str | None:
        return self._gitlab_webhook_secret

# Instantiate a single configuration instance
_settings = Settings()

def get_settings() -> Settings:
    return _settings
