from __future__ import annotations

from typing import Any

from .cli_output_utils import print_json, yes_no as _yes_no


def print_integrations(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    print(f"Integrations: {payload['workspace']}")
    if not payload["integrations"]:
        print("No integrations configured.")
        return
    for integration in payload["integrations"]:
        status = "enabled" if integration["enabled"] else "disabled"
        print(
            f"{integration['id']}: {integration['label']} "
            f"[{integration['provider']} / {status}]"
        )
        print(f"  mode: {integration['mode']} | risk: {integration['risk_level']}")
        print(f"  events: {', '.join(integration['allowed_events']) or 'none'}")
        print(f"  actions: {', '.join(integration['allowed_actions']) or 'none'}")


def print_integration_check(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    integration = payload["integration"]
    status = "enabled" if payload["enabled"] else "disabled"
    print(f"Integration check: {integration['id']} ({integration['provider']})")
    print(f"Status: {status} | Dry-run only: {_yes_no(payload['dry_run_only'])}")
    print(f"Plannable actions: {', '.join(payload['plannable_actions']) or 'none'}")
    if payload["blocked_actions"]:
        print(f"Blocked actions: {', '.join(payload['blocked_actions'])}")
    print("Secret: reference present" if payload["secret_ref_present"] else "Secret: none")
    for note in payload["notes"]:
        print(f"- {note}")


def print_integration_plan(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    integration = payload["integration"]
    work = payload["work_item"]
    print(f"Integration dry run: {integration['id']} -> {work['id']}")
    print(f"Event: {payload['event']} | Action: {payload['action']}")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Payload operation: {payload['payload_preview']['operation']}")
    if payload.get("recorded"):
        plan = payload.get("integration_plan") or {}
        print(f"Recorded plan: {plan.get('id', 'unknown')} ({plan.get('status', 'unknown')})")
        print("External write: planned only; no provider call was made.")
    else:
        print("Recorded plan: no (preview only)")
    print(f"Next: {payload['next_action']}")


def print_integration_plan_decision(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    plan = payload["integration_plan"]
    human = payload["human"]
    print(f"Integration plan {payload['decision']}: {plan['id']} -> {payload['status']}")
    print(f"By: {human['id']} ({human['name']})")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    if plan.get("decision_reason"):
        print(f"Reason: {plan['decision_reason']}")
    print(f"Next: {payload['next_action']}")


def print_integration_enqueue(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    item = payload["integration_outbox_item"]
    human = payload["human"]
    print(f"Integration outbox queued: {item['id']}")
    print(f"Plan: {item['plan_id']} | Work: {item['work_item_id']}")
    print(f"By: {human['id']} ({human['name']})")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Next: {payload['next_action']}")


def print_integration_outbox_check(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    item = payload["integration_outbox_item"]
    integration = payload["integration"]
    print(f"Integration outbox preflight: {item['id']} -> {payload['status']}")
    print(f"Integration: {integration['id']} ({integration['provider']})")
    print(f"Plan: {item['plan_id']} | Work: {item['work_item_id']}")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Execution enabled: {_yes_no(payload['execution_enabled'])}")
    failed = [check for check in payload["checks"] if check["status"] != "pass"]
    if failed:
        print("Failed checks:")
        for check in failed:
            print(f"- {check['code']}: {check['message']}")
    else:
        print("Checks: pass")
    print(f"Next: {payload['next_action']}")


def print_integration_outbox_cancel(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print_json(payload)
        return
    item = payload["integration_outbox_item"]
    human = payload["human"]
    print(f"Integration outbox canceled: {item['id']}")
    print(f"Plan: {item['plan_id']} | Work: {item['work_item_id']}")
    print(f"By: {human['id']} ({human['name']})")
    print(f"Reason: {item['cancel_reason']}")
    print(f"Provider call: {_yes_no(payload['would_call_provider'])}")
    print(f"Next: {payload['next_action']}")


