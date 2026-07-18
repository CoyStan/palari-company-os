from __future__ import annotations

from pathlib import Path
from typing import Any

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


def current_recommendation_data() -> dict[str, Any]:
    """Return a minimal current workspace for parked recommendation adapters."""

    data: dict[str, Any] = {
        "schema_version": 2,
        "name": "Current Recommendation Contract",
    }
    for collection in COLLECTION_FILE_KEYS:
        data[collection] = []
    data["humans"] = [
        {
            "id": "HUMAN-1",
            "name": "Product Owner",
            "role": "Product authority",
            "approval_capabilities": ["product"],
        }
    ]
    data["palaris"] = [
        {
            "id": "PALARI-1",
            "name": "Worker",
            "role": "Bounded worker",
            "owner_human": "HUMAN-1",
            "linked_goals": ["GOAL-1"],
        }
    ]
    data["goals"] = [
        {
            "id": "GOAL-1",
            "title": "Keep optional guidance bounded",
            "owner": "HUMAN-1",
            "status": "active",
        }
    ]
    data["sources"] = [
        {
            "id": "SOURCE-1",
            "label": "Selected local note",
            "kind": "note",
            "provider": "local",
            "uri": "notes/source.md",
            "access_mode": "read",
            "selected": True,
            "owner_human": "HUMAN-1",
            "allowed_palaris": ["PALARI-1"],
            "data_class": "internal",
            "authority": "company_owned",
            "steward_human": "HUMAN-1",
        }
    ]
    data["work_items"] = [
        {
            "id": "WORK-1",
            "title": "Summarize a selected note",
            "goal": "GOAL-1",
            "palari": "PALARI-1",
            "risk": "R2",
            "intensity": "standard",
            "status": "active",
            "scope": "Use only the selected source.",
            "allowed_resources": ["notes/source.md"],
            "allowed_sources": ["SOURCE-1"],
            "output_targets": ["notes/result.md"],
            "forbidden_actions": ["external_write"],
            "required_approval_count": 0,
            "recommended_playbooks": [
                "superpowers:verification-before-completion",
                "superpowers:requesting-code-review",
            ],
        }
    ]
    data["playbook_sources"] = [
        {
            "id": "superpowers",
            "label": "Superpowers skills",
            "provider": "github",
            "uri": "https://github.com/obra/Superpowers",
            "ref": "main",
            "license": "MIT",
            "enabled": True,
            "included_playbooks": [
                "brainstorming",
                "writing-plans",
                "executing-plans",
                "verification-before-completion",
                "requesting-code-review",
                "systematic-debugging",
                "subagent-driven-development",
            ],
        }
    ]
    return data
