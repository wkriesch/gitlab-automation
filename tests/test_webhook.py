import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock configuration settings before importing main application to avoid connecting to real GitLab
mock_settings = MagicMock()
mock_settings.gitlab_api_url = "https://gitlab.com"
mock_settings.gitlab_access_token = "mock_token"
mock_settings.gitlab_webhook_secret = "my_secret"
mock_settings.gitlab_bot_username = "gitlab_bot_user"
mock_settings.rules_file_path = "config/rules.yaml"
mock_settings.log_level = "INFO"
mock_settings.disable_loop_prevention = False

with patch("app.config.get_settings", return_value=mock_settings):
    from app.main import app
    from app.handler import WebhookHandler

def test_health_endpoint():
    """
    Test that the /health endpoint is available and returns ok.
    """
    with patch("app.main.gitlab_client.initialize", new_callable=AsyncMock) as mock_init:
        client = app.test_client()
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok", "app": "gitlab-automation-framework", "initialized": True}
        mock_init.assert_called_once()

def test_webhook_unauthorized():
    """
    Test that /webhook returns 401 Unauthorized when token header is incorrect or missing.
    """
    with patch("app.main.gitlab_client.initialize", new_callable=AsyncMock) as mock_init:
        client = app.test_client()
        
        # Missing X-Gitlab-Token
        response = client.post("/webhook", json={"object_kind": "issue"})
        assert response.status_code == 401

        # Mismatched X-Gitlab-Token
        response = client.post(
            "/webhook", 
            json={"object_kind": "issue"}, 
            headers={"X-Gitlab-Token": "wrong_secret"}
        )
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_webhook_loop_prevention():
    """
    Test that the webhook handler ignores events triggered by the bot itself.
    """
    mock_client = MagicMock()
    mock_client.bot_username = "gitlab_bot_user"
    mock_rules_engine = MagicMock()
    
    handler = WebhookHandler(mock_client, mock_rules_engine)
    
    # Webhook payload where bot is the actor
    payload = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 1,
            "project_id": 101,
            "id": 501
        },
        "user": {
            "username": "gitlab_bot_user"
        }
    }
    
    result = await handler.handle_event(payload)
    assert result["status"] == "ignored"
    assert "loop prevention" in result["reason"]
    mock_rules_engine.evaluate.assert_not_called()

@pytest.mark.asyncio
async def test_webhook_executes_actions():
    """
    Test that the webhook handler evaluates rules and executes matching actions.
    """
    mock_client = MagicMock()
    mock_client.bot_username = "gitlab_bot_user"
    
    # Mock RulesEngine match
    mock_rule = MagicMock()
    mock_rule.name = "test_rule"
    mock_rule.actions = [{"set_start_date": "now"}]
    
    mock_rules_engine = MagicMock()
    mock_rules_engine.evaluate.return_value = [mock_rule]
    
    handler = WebhookHandler(mock_client, mock_rules_engine)
    
    # Webhook payload from regular user
    payload = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 22,
            "project_id": 101,
            "id": 999
        },
        "user": {
            "username": "some_other_user"
        },
        "project": {
            "path_with_namespace": "my-group/my-project"
        }
    }
    
    with patch("app.handler.execute_actions", new_callable=AsyncMock) as mock_execute:
        result = await handler.handle_event(payload)
        
        assert result["status"] == "completed"
        assert result["matched_rules_count"] == 1
        assert "test_rule" in result["executed_rules"]
        
        mock_rules_engine.evaluate.assert_called_once_with(payload)
        mock_execute.assert_called_once_with(
            gitlab_client=mock_client,
            actions=mock_rule.actions,
            event_data=payload
        )

@pytest.mark.asyncio
async def test_execute_actions_label_transitions():
    """
    Test that execute_actions correctly adds and removes labels, creates comments, and sends batch updates.
    """
    from app.actions import execute_actions
    
    mock_client = AsyncMock()
    
    # Issue payload with current labels
    payload = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 42,
            "project_id": 100,
            "id": 999,
            "labels": [{"title": "status::todo"}, {"title": "tipo::projeto"}]
        },
        "project": {
            "path_with_namespace": "my-group/my-project"
        }
    }
    
    actions = [
        {"add_label": "status::doing"},
        {"remove_label": "status::todo"},
        {"add_comment": "Movimentado para status::doing"}
    ]
    
    await execute_actions(mock_client, actions, payload)
    
    # Assert update_issue was called with updated labels string
    # "status::todo" is removed, "status::doing" is added -> new labels should be: "tipo::projeto,status::doing"
    mock_client.update_issue.assert_called_once()
    called_args = mock_client.update_issue.call_args[1]
    assert called_args["project_id"] == 100
    assert called_args["issue_iid"] == 42
    
    updated_labels = called_args["updates"]["labels"].split(",")
    assert "tipo::projeto" in updated_labels
    assert "status::doing" in updated_labels
    assert "status::todo" not in updated_labels

    # Assert create_issue_note was called with correct arguments
    mock_client.create_issue_note.assert_called_once_with(
        project_id=100,
        issue_iid=42,
        body="Movimentado para status::doing"
    )

