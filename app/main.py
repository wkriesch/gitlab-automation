import logging
import secrets
import asyncio
import threading
from flask import Flask, request, jsonify
from app.config import get_settings
from app.gitlab_client import GitLabClient
from app.rules_engine import RulesEngine
from app.handler import WebhookHandler

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

app = Flask(__name__)

# Initialize components
gitlab_client = GitLabClient()
rules_engine = RulesEngine()
webhook_handler = WebhookHandler(gitlab_client, rules_engine)

initialized = False
init_lock = threading.Lock()

async def ensure_initialized():
    """
    Thread-safe and async-safe lazy initialization of services.
    Validates connection and runs bot auto-discovery during the first request.
    """
    global initialized
    if not initialized:
        with init_lock:
            if not initialized:
                logger.info("Initializing GitLab Client and validating connection...")
                try:
                    await gitlab_client.initialize()
                    initialized = True
                    logger.info("Service initialization completed successfully.")
                except Exception as e:
                    logger.critical(f"Failed to initialize services: {e}")
                    raise RuntimeError("Initialization failed") from e

@app.route("/health", methods=["GET"])
async def health_check():
    """
    Endpoint for health checks.
    """
    try:
        await ensure_initialized()
        return jsonify({"status": "ok", "app": "gitlab-automation-framework", "initialized": True}), 200
    except Exception as e:
        return jsonify({"status": "error", "reason": str(e), "initialized": False}), 500

@app.route("/webhook", methods=["POST"])
async def handle_webhook():
    """
    Handles GitLab webhook events (Issue Hook).
    Securely validates X-Gitlab-Token using constant-time string comparison.
    """
    # 1. Initialize client on first call
    try:
        await ensure_initialized()
    except Exception as e:
        logger.error(f"Cannot process webhook: server failed to initialize: {e}")
        return jsonify({"error": "Server initialization failed"}), 500

    # 2. Secure token validation
    webhook_secret = settings.gitlab_webhook_secret
    if webhook_secret:
        client_token = request.headers.get("X-Gitlab-Token", "")
        
        # Security: Use secrets.compare_digest for constant-time comparison to prevent timing attacks.
        if not client_token or not secrets.compare_digest(client_token, webhook_secret):
            logger.warning("Unauthorized access attempt: Invalid X-Gitlab-Token header.")
            return jsonify({"error": "Invalid webhook token"}), 401

    # 3. Parse payload
    payload = request.get_json(silent=True)
    if payload is None:
        logger.error("Failed to parse JSON body (missing or invalid JSON)")
        return jsonify({"error": "Malformed JSON payload"}), 400

    # 4. Process webhook event
    try:
        result = await webhook_handler.handle_event(payload)
        return jsonify(result), 202
    except Exception as e:
        logger.error(f"Error handling event: {e}", exc_info=True)
        return jsonify({"error": "Internal error processing webhook event"}), 500

if __name__ == "__main__":
    # Warn if webhook secret is not configured
    if not settings.gitlab_webhook_secret:
        logger.warning(
            "Security Warning: GITLAB_WEBHOOK_SECRET is not configured. "
            "Webhook endpoint is accessible without authentication headers."
        )
    logger.info("Starting Flask application on port 8000...")
    app.run(host="0.0.0.0", port=8000, debug=False)
