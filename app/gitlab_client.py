import logging
from typing import Any, Dict
import httpx
from urllib.parse import quote_plus
from app.config import get_settings

logger = logging.getLogger("gitlab_client")

class GitLabClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.gitlab_api_url
        self.token = settings.gitlab_access_token
        self.bot_username = settings.gitlab_bot_username
        self.bot_user_id = None
        
    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self.base_url}/api/v4",
            headers={"Private-Token": self.token},
            timeout=10.0
        )
        
    async def initialize(self):
        """
        Validate token and auto-discover the Bot username and user ID.
        Runs on startup to ensure API connectivity and prevent event loops.
        """
        try:
            logger.info("Verifying GitLab API token and performing auto-discovery...")
            async with self._get_client() as client:
                response = await client.get("/user")
                response.raise_for_status()
                user_data = response.json()
                
                self.bot_user_id = user_data.get("id")
                discovered_username = user_data.get("username")
                
                # If bot_username is not manually configured, auto-discover it
                if not self.bot_username:
                    self.bot_username = discovered_username
                    logger.info(f"Auto-discovered GitLab Bot username: @{self.bot_username} (ID: {self.bot_user_id})")
                else:
                    logger.info(
                        f"GitLab Bot API connection verified. Configured username: @{self.bot_username}, "
                        f"Token username: @{discovered_username} (ID: {self.bot_user_id})"
                    )
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to authenticate with GitLab API: HTTP {e.response.status_code} - {e.response.text}")
            raise RuntimeError("GitLab API authentication failed. Verify GITLAB_ACCESS_TOKEN.") from e
        except Exception as e:
            logger.error(f"Error initializing GitLab client: {e}")
            raise RuntimeError("Could not connect to GitLab API.") from e

    async def close(self):
        """
        No-op since client is instantiated dynamically.
        """
        pass

    async def update_issue(self, project_id: int | str, issue_iid: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update issue details (e.g. weight, start_date, due_date, labels).
        PUT /projects/:id/issues/:issue_iid
        """
        encoded_project_id = quote_plus(str(project_id))
        url = f"/projects/{encoded_project_id}/issues/{issue_iid}"
        try:
            logger.info(f"Updating issue #{issue_iid} in project {project_id} with data: {updates}")
            async with self._get_client() as client:
                response = await client.put(url, json=updates)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to update issue #{issue_iid}: HTTP {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Network error while updating issue #{issue_iid}: {e}")
            raise

    async def assign_issue_to_epic(self, group_path: str, epic_iid: int, issue_id: int) -> Dict[str, Any]:
        """
        Link an issue to a group Epic.
        POST /groups/:id/epics/:epic_iid/issues/:issue_id
        Note: issue_id must be the global database ID of the issue, not the project-specific iid.
        """
        encoded_group_path = quote_plus(group_path)
        url = f"/groups/{encoded_group_path}/epics/{epic_iid}/issues/{issue_id}"
        try:
            logger.info(f"Assigning issue ID {issue_id} to Epic IID {epic_iid} in group {group_path}")
            async with self._get_client() as client:
                response = await client.post(url)
                
                # GitLab returns 201 Created on success, or 200 if already assigned
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            # We capture 403/404 specifically because the GitLab free tier or project configuration might not support epics
            if e.response.status_code in (403, 404):
                logger.warning(
                    f"Could not assign issue to epic (HTTP {e.response.status_code}). "
                    "This can happen if you are on GitLab Free tier (Epics are Ultimate/Premium feature) "
                    f"or if the group '{group_path}' / epic '{epic_iid}' does not exist or is inaccessible. Details: {e.response.text}"
                )
                return {"warning": "Feature not supported or resource not found", "status_code": e.response.status_code}
            logger.error(f"Failed to assign issue ID {issue_id} to Epic #{epic_iid}: HTTP {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Network error while assigning issue to Epic: {e}")
            raise

    async def create_issue_note(self, project_id: int | str, issue_iid: int, body: str) -> Dict[str, Any]:
        """
        Create a new note/comment on an issue.
        POST /projects/:id/issues/:issue_iid/notes
        """
        encoded_project_id = quote_plus(str(project_id))
        url = f"/projects/{encoded_project_id}/issues/{issue_iid}/notes"
        try:
            logger.info(f"Creating note on issue #{issue_iid} in project {project_id}: {body}")
            async with self._get_client() as client:
                response = await client.post(url, json={"body": body})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create note on issue #{issue_iid}: HTTP {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Network error while creating note on issue #{issue_iid}: {e}")
            raise

