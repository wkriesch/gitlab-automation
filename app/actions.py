import datetime
import logging
from typing import Dict, Any, List
from app.gitlab_client import GitLabClient

logger = logging.getLogger("actions_executor")

def get_group_path(path_with_namespace: str) -> str:
    """
    Extracts the group/subgroup path from a project path with namespace.
    e.g. 'my-org/subgroup/project-name' -> 'my-org/subgroup'
    """
    parts = path_with_namespace.split("/")
    if len(parts) > 1:
        return "/".join(parts[:-1])
    return path_with_namespace

async def execute_actions(
    gitlab_client: GitLabClient,
    actions: List[Dict[str, Any]],
    event_data: Dict[str, Any]
):
    """
    Executes a list of actions matching a matched rule.
    Updates are batched together where possible to minimize API calls.
    """
    object_attributes = event_data.get("object_attributes", {})
    issue_iid = object_attributes.get("iid")
    issue_id = object_attributes.get("id")  # Global database ID of the issue
    project_id = object_attributes.get("project_id")
    
    project_info = event_data.get("project", {})
    path_with_namespace = project_info.get("path_with_namespace", "")
    group_path = get_group_path(path_with_namespace)

    # Extract current labels list to support add/remove operations
    labels_payload = event_data.get("labels") or object_attributes.get("labels") or []
    current_labels = [label["title"] for label in labels_payload if isinstance(label, dict) and "title" in label]
    labels_modified = False

    issue_updates = {}

    for action_dict in actions:
        if not isinstance(action_dict, dict):
            logger.warning(f"Invalid action format (expected dict): {action_dict}")
            continue

        for action_name, action_value in action_dict.items():
            logger.info(f"Processing action '{action_name}' on Issue #{issue_iid}...")
            
            try:
                if action_name == "set_epic":
                    try:
                        epic_iid = int(action_value)
                    except ValueError:
                        logger.error(f"Invalid epic IID value: '{action_value}'. Must be an integer.")
                        continue
                    
                    if not group_path:
                        logger.error(
                            f"Cannot associate Epic: Project has no group namespace "
                            f"(path_with_namespace: '{path_with_namespace}')"
                        )
                        continue
                    
                    # Epics assignment is a separate API call on group level
                    await gitlab_client.assign_issue_to_epic(
                        group_path=group_path,
                        epic_iid=epic_iid,
                        issue_id=issue_id
                    )
                    
                elif action_name == "set_start_date":
                    if action_value == "now":
                        date_str = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
                    else:
                        date_str = str(action_value)
                    issue_updates["start_date"] = date_str
                    
                elif action_name == "set_due_date":
                    if action_value == "now":
                        date_str = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
                    else:
                        date_str = str(action_value)
                    issue_updates["due_date"] = date_str

                elif action_name == "set_weight":
                    try:
                        issue_updates["weight"] = int(action_value)
                    except ValueError:
                        logger.error(f"Invalid weight value: '{action_value}'. Must be an integer.")
                        continue
                    
                elif action_name == "add_label":
                    label_to_add = str(action_value)
                    if label_to_add not in current_labels:
                        current_labels.append(label_to_add)
                        labels_modified = True
                        
                elif action_name == "remove_label":
                    label_to_remove = str(action_value)
                    if label_to_remove in current_labels:
                        current_labels.remove(label_to_remove)
                        labels_modified = True
                        
                elif action_name == "add_comment":
                    comment_body = str(action_value)
                    await gitlab_client.create_issue_note(
                        project_id=project_id,
                        issue_iid=issue_iid,
                        body=comment_body
                    )

                        
                else:
                    logger.warning(f"Unsupported action type: '{action_name}'")
                    
            except Exception as e:
                logger.error(f"Error handling action '{action_name}' for Issue #{issue_iid}: {e}", exc_info=True)

    # Batch labels if modified
    if labels_modified:
        issue_updates["labels"] = ",".join(current_labels)

    # Batch updates to the issue (dates, weight etc.) into a single API call to reduce latency and API consumption
    if issue_updates:
        try:
            logger.info(f"Sending batch issue updates to GitLab for #{issue_iid}: {issue_updates}")
            await gitlab_client.update_issue(
                project_id=project_id,
                issue_iid=issue_iid,
                updates=issue_updates
            )
            logger.info(f"Successfully performed batch update of fields {list(issue_updates.keys())} for Issue #{issue_iid}")
        except Exception as e:
            logger.error(f"Failed to perform batch update of issue fields for Issue #{issue_iid}: {e}")
