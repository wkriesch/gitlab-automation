import logging
from typing import Dict, Any
from app.config import get_settings
from app.gitlab_client import GitLabClient
from app.rules_engine import RulesEngine
from app.actions import execute_actions

logger = logging.getLogger("webhook_handler")

class WebhookHandler:
    def __init__(self, gitlab_client: GitLabClient, rules_engine: RulesEngine):
        self.gitlab_client = gitlab_client
        self.rules_engine = rules_engine

    async def handle_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming GitLab webhook payloads.
        Checks for object kind, handles loop prevention, matches rules, and triggers actions.
        """
        object_kind = event_data.get("object_kind")
        
        # 1. Filter events: We currently only automate Issues
        if object_kind != "issue":
            logger.debug(f"Ignoring non-issue event of kind: '{object_kind}'")
            return {"status": "ignored", "reason": f"unsupported object kind: {object_kind}"}

        object_attributes = event_data.get("object_attributes", {})
        issue_iid = object_attributes.get("iid")
        project_id = object_attributes.get("project_id")
        action = object_attributes.get("action")

        # 2. Loop Prevention: Identify the user who triggered the webhook
        # If it was our Bot user, we ignore it to prevent infinite update cycles
        user_info = event_data.get("user", {})
        actor_username = user_info.get("username")
        
        settings = get_settings()
        if (
            not settings.disable_loop_prevention
            and actor_username 
            and self.gitlab_client.bot_username 
            and actor_username.lower() == self.gitlab_client.bot_username.lower()
        ):
            logger.info(
                f"Loop Prevention: Ignoring webhook for Issue #{issue_iid} in Project {project_id} "
                f"because it was triggered by the Bot user (@{actor_username})."
            )
            return {"status": "ignored", "reason": "loop prevention: event triggered by bot"}

        logger.info(
            f"Processing Issue webhook. Action: '{action}', Issue: #{issue_iid}, "
            f"Project ID: {project_id}, Actor: @{actor_username or 'unknown'}"
        )

        # 3. Rules Matching
        matched_rules = self.rules_engine.evaluate(event_data)
        
        if not matched_rules:
            logger.info(f"No rules matched for Issue #{issue_iid}")
            return {"status": "completed", "matched_rules_count": 0, "executed_actions": []}

        # 4. Actions Execution
        executed_rules_summary = []
        for rule in matched_rules:
            logger.info(f"Executing matched rule: '{rule.name}'")
            await execute_actions(
                gitlab_client=self.gitlab_client,
                actions=rule.actions,
                event_data=event_data
            )
            executed_rules_summary.append(rule.name)

        return {
            "status": "completed",
            "matched_rules_count": len(matched_rules),
            "executed_rules": executed_rules_summary
        }
