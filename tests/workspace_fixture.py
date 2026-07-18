from __future__ import annotations

from pathlib import Path

from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.validation import COLLECTION_FILE_KEYS


def write_current_agent_workspace(destination: Path) -> None:
    """Write the smallest current workspace shared by agent adapter tests."""

    data: dict[str, object] = {
        "schema_version": 2,
        "name": "Current Agent Test Workspace",
    }
    for collection in COLLECTION_FILE_KEYS:
        data[collection] = []
    data["humans"] = [
        {
            "id": "HUMAN-FOUNDER",
            "name": "Test Founder",
            "role": "Product authority",
            "authority_level": "admin",
            "approval_capabilities": ["architecture", "merge", "product"],
            "availability": "active",
        }
    ]
    data["palaris"] = [
        {
            "id": "PALARI-STEWARD",
            "name": "Steward",
            "role": "Repository steward",
            "scope": "Perform bounded repository work.",
            "owner_human": "HUMAN-FOUNDER",
            "linked_goals": ["GOAL-REPO-0001"],
            "memory_sources": ["SOURCE-REPO-FOUNDATION"],
            "forbidden_actions": ["deploy"],
        },
        {
            "id": "PALARI-ARCHITECT",
            "name": "Architect",
            "role": "Independent architecture reviewer",
            "scope": "Review exact bounded proof independently.",
            "owner_human": "HUMAN-FOUNDER",
            "linked_goals": ["GOAL-REPO-0001"],
            "memory_sources": ["SOURCE-REPO-FOUNDATION"],
            "forbidden_actions": ["deploy"],
        },
    ]
    data["goals"] = [
        {
            "id": "GOAL-REPO-0001",
            "title": "Verify current bounded agent work",
            "owner": "HUMAN-FOUNDER",
            "status": "active",
            "priority": "high",
            "success_criteria": ["Current boundary tests pass."],
            "linked_palaris": ["PALARI-ARCHITECT", "PALARI-STEWARD"],
        },
        {
            "id": "GOAL-REPO-0002",
            "title": "Exercise independent review boundaries",
            "owner": "HUMAN-FOUNDER",
            "status": "active",
            "priority": "normal",
            "success_criteria": ["Authority changes fail closed."],
            "linked_palaris": [],
        },
    ]
    data["sources"] = [
        {
            "id": "SOURCE-REPO-FOUNDATION",
            "label": "Temporary repository",
            "kind": "repo",
            "provider": "local",
            "uri": ".",
            "access_mode": "read",
            "selected": True,
            "owner_human": "HUMAN-FOUNDER",
            "allowed_palaris": ["PALARI-ARCHITECT", "PALARI-STEWARD"],
            "data_class": "internal",
            "authority": "company_owned",
            "steward_human": "HUMAN-FOUNDER",
        }
    ]
    data["workbenches"] = [
        {
            "id": "WORKBENCH-REPO-FOUNDATION",
            "label": "Repository",
            "summary": "Temporary bounded repository work.",
            "goal_ids": ["GOAL-REPO-0001"],
            "palari_ids": ["PALARI-ARCHITECT", "PALARI-STEWARD"],
            "human_ids": ["HUMAN-FOUNDER"],
            "source_ids": ["SOURCE-REPO-FOUNDATION"],
            "output_target_ids": ["AGENTS.md", "README.md"],
            "status": "active",
        }
    ]
    write_store(WorkspaceStore(data_path=destination, data=data))
