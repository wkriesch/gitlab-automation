import pytest
from app.rules_engine import RulesEngine

def test_rule_matching(tmp_path):
    yaml_content = """
rules:
  - name: test_rule_label_present
    match:
      labels: ["status::in-progress"]
    actions:
      - set_start_date: now
  - name: test_rule_on_change
    match:
      labels: ["status::done"]
      on_change: true
    actions:
      - set_due_date: now
"""
    rules_file = tmp_path / "test_rules.yaml"
    rules_file.write_text(yaml_content)
    
    # Initialize engine with the temporary test file path
    engine = RulesEngine(rules_file_path=str(rules_file))
    assert len(engine.rules) == 2
    assert engine.rules[0].name == "test_rule_label_present"
    assert engine.rules[1].name == "test_rule_on_change"
    
    # Case 1: Label present (on_change=False)
    payload_present = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 1,
            "labels": [{"title": "status::in-progress"}]
        },
        "changes": {}
    }
    
    matches = engine.evaluate(payload_present)
    assert len(matches) == 1
    assert matches[0].name == "test_rule_label_present"
    
    # Case 2: Label in-progress present, but also done.
    # Done has on_change=True, but 'labels' is not in changes (i.e., it did not change)
    payload_no_change = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 1,
            "labels": [{"title": "status::in-progress"}, {"title": "status::done"}]
        },
        "changes": {}
    }
    matches = engine.evaluate(payload_no_change)
    assert len(matches) == 1
    assert matches[0].name == "test_rule_label_present"  # Done doesn't match because it didn't change
    
    # Case 3: Done label changed (added)
    payload_changed = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 1,
            "labels": [{"title": "status::done"}]
        },
        "changes": {
            "labels": {
                "previous": [],
                "current": [{"title": "status::done"}]
            }
        }
    }
    matches = engine.evaluate(payload_changed)
    assert len(matches) == 1
    assert matches[0].name == "test_rule_on_change"
    
    # Case 4: Done label changed but it was already present previously (no addition)
    payload_already_present = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "update",
            "iid": 1,
            "labels": [{"title": "status::done"}]
        },
        "changes": {
            "labels": {
                "previous": [{"title": "status::done"}],
                "current": [{"title": "status::done"}]
            }
        }
    }
    matches = engine.evaluate(payload_already_present)
    assert len(matches) == 0  # Should not match because it was already present
    
    # Case 5: New issue creation with done label (should match on_change as a transition from nothing to present)
    payload_new_issue = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "open",
            "iid": 1,
            "labels": [{"title": "status::done"}]
        },
        "changes": {}
    }
    matches = engine.evaluate(payload_new_issue)
    assert len(matches) == 1
    assert matches[0].name == "test_rule_on_change"
