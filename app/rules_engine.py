import os
import yaml
import logging
from typing import List, Dict, Any
from app.config import get_settings

logger = logging.getLogger("rules_engine")

class MatchCondition:
    def __init__(self, labels: List[str] = None, on_change: bool = False):
        self.labels = labels or []
        self.on_change = bool(on_change)

class Rule:
    def __init__(self, name: str, match: Dict[str, Any], actions: List[Dict[str, Any]]):
        self.name = name
        
        # Robust validation and normalization of YAML matches
        match_dict = match if isinstance(match, dict) else {}
        labels = match_dict.get("labels", [])
        
        # User-friendly normalization: convert single string label to list automatically
        if isinstance(labels, str):
            labels = [labels]
        elif not isinstance(labels, list):
            labels = []
            
        on_change = match_dict.get("on_change", False)
        
        self.match = MatchCondition(
            labels=labels,
            on_change=on_change
        )
        
        # Normalize actions list
        self.actions = actions if isinstance(actions, list) else []

class RulesEngine:
    def __init__(self, rules_file_path: str | None = None):
        settings = get_settings()
        self.rules_file_path = rules_file_path or settings.rules_file_path
        self.rules: List[Rule] = []
        self.load_rules()

    def load_rules(self):
        """
        Reads and parses the YAML rules file.
        Uses safe_load for security to prevent arbitrary code execution from YAML.
        """
        if not os.path.exists(self.rules_file_path):
            logger.warning(f"Rules file not found at {self.rules_file_path}. Initializing with empty rules.")
            self.rules = []
            return
        
        try:
            with open(self.rules_file_path, "r", encoding="utf-8") as f:
                # Secure: Using safe_load instead of load
                data = yaml.safe_load(f) or {}
                
            rules_list = data.get("rules", [])
            parsed_rules = []
            for r in rules_list:
                try:
                    if not isinstance(r, dict) or "name" not in r or "match" not in r or "actions" not in r:
                        logger.error(f"Invalid rule structure in YAML: {r}")
                        continue
                    parsed_rules.append(Rule(
                        name=r["name"],
                        match=r["match"],
                        actions=r["actions"]
                    ))
                except Exception as ve:
                    logger.error(f"Validation error in rule YAML formatting: {ve}")
            self.rules = parsed_rules
            logger.info(f"Loaded {len(self.rules)} automation rules from {self.rules_file_path}")
        except Exception as e:
            logger.error(f"Failed to read/parse rules file at {self.rules_file_path}: {e}")
            self.rules = []

    def evaluate(self, event_data: Dict[str, Any]) -> List[Rule]:
        """
        Evaluate a GitLab Issue hook event payload against loaded rules.
        Returns the list of matching Rules to execute.
        """
        matched_rules = []
        object_attributes = event_data.get("object_attributes", {})
        action = object_attributes.get("action")
        issue_iid = object_attributes.get("iid")
        
        # 1. Determine if it is a new issue creation
        # action is 'open' when issue is newly created
        is_new_issue = (action == "open")

        # 2. Extract current labels
        # GitLab issue webhooks provide the list of labels in the 'labels' key (list of dicts with title)
        # or inside object_attributes.labels. Let's support both.
        labels_payload = event_data.get("labels") or object_attributes.get("labels") or []
        current_labels = [label["title"] for label in labels_payload if isinstance(label, dict) and "title" in label]
        
        # 3. Extract changes and check if labels changed
        changes = event_data.get("changes", {})
        labels_changed = "labels" in changes
        
        # 4. Extract previous labels
        previous_labels = []
        if labels_changed:
            previous_labels_payload = changes.get("labels", {}).get("previous") or []
            previous_labels = [
                label["title"] for label in previous_labels_payload 
                if isinstance(label, dict) and "title" in label
            ]

        logger.debug(
            f"Evaluating rules for Issue #{issue_iid}. Action: {action}. "
            f"Current labels: {current_labels}. Previous labels: {previous_labels}. "
            f"Labels changed: {labels_changed}. Is new issue: {is_new_issue}"
        )

        for rule in self.rules:
            if self._is_match(rule.match, current_labels, previous_labels, labels_changed, is_new_issue):
                logger.info(f"Rule '{rule.name}' matched for Issue #{issue_iid}")
                matched_rules.append(rule)
                
        return matched_rules

    def _is_match(
        self, 
        match: MatchCondition, 
        current_labels: List[str], 
        previous_labels: List[str], 
        labels_changed: bool,
        is_new_issue: bool
    ) -> bool:
        if not match.labels:
            return False
            
        for target_label in match.labels:
            # The target label must be present on the issue currently
            if target_label not in current_labels:
                return False
                
            # If the rule is configured to only fire on label change (addition)
            if match.on_change:
                # If it's a brand new issue, the label is considered "newly added"
                if is_new_issue:
                    continue
                
                # If it's an update, the labels must have actually changed in this event
                if not labels_changed:
                    return False
                
                # The label must NOT have been in the previous labels list
                if target_label in previous_labels:
                    return False
                    
        return True
