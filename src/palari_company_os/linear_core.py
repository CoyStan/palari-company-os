from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from .errors import WorkspaceError


LINEAR_ENDPOINT = "https://api.linear.app/graphql"
LINEAR_SECRET_REF = "env:LINEAR_API_KEY"
LINEAR_INTEGRATION_ID = "INT-LINEAR"

LINEAR_ISSUE_QUERY = """
query PalariLinearIssue($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    url
    updatedAt
    state { id name type }
    team { id key name }
    labels { nodes { id name } }
    assignee { id name email }
  }
}
"""

LINEAR_COMMENT_MUTATION = """
mutation PalariLinearComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
    comment { id url body createdAt }
  }
}
"""


class LinearIssueClient(Protocol):
    def issue(self, identifier: str) -> dict[str, Any]:
        ...

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        ...


class LinearAdapterError(WorkspaceError):
    def __init__(self, message: str, *, code: str, next_action: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action


class LinearClient:
    def __init__(self, api_key: str, *, endpoint: str = LINEAR_ENDPOINT, timeout: int = 20) -> None:
        if not api_key:
            raise LinearAdapterError(
                "LINEAR_API_KEY is required for Linear provider calls",
                code="LINEAR_API_KEY_MISSING",
                next_action="Set LINEAR_API_KEY or run a local-only command such as `palari linear doctor --json`.",
            )
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "LinearClient":
        return cls(os.environ.get("LINEAR_API_KEY", ""))

    def issue(self, identifier: str) -> dict[str, Any]:
        payload = self.request(LINEAR_ISSUE_QUERY, {"id": identifier})
        issue = payload.get("issue")
        if not isinstance(issue, dict):
            raise LinearAdapterError(
                f"Linear issue not found: {identifier}",
                code="LINEAR_ISSUE_NOT_FOUND",
                next_action="Check the Linear issue key/id and that the API key can read the workspace.",
            )
        return normalize_issue(issue, fallback_identifier=identifier)

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        payload = self.request(
            LINEAR_COMMENT_MUTATION,
            {"issueId": issue_id, "body": body},
        )
        result = payload.get("commentCreate")
        if not isinstance(result, dict) or not result.get("success"):
            raise LinearAdapterError(
                "Linear commentCreate did not return success",
                code="LINEAR_COMMENT_CREATE_FAILED",
                next_action="Inspect the queued outbox item and retry after confirming Linear access.",
            )
        comment = result.get("comment")
        if not isinstance(comment, dict):
            raise LinearAdapterError(
                "Linear commentCreate did not return a comment",
                code="LINEAR_UNSUPPORTED_RESPONSE",
                next_action="Do not retry blindly; inspect the provider response shape against Linear's API.",
            )
        return dict(comment)

    def request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            code = "LINEAR_AUTH_FAILED" if exc.code in {401, 403} else "LINEAR_HTTP_ERROR"
            raise LinearAdapterError(
                f"Linear GraphQL HTTP {exc.code}",
                code=code,
                next_action="Check LINEAR_API_KEY permissions and retry after provider access is healthy.",
            ) from exc
        except urllib.error.URLError as exc:
            raise LinearAdapterError(
                f"Linear GraphQL request failed: {_short_error(str(exc.reason))}",
                code="LINEAR_NETWORK_ERROR",
                next_action="Check network access to https://api.linear.app/graphql and retry.",
            ) from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LinearAdapterError(
                "Linear GraphQL response was not valid JSON",
                code="LINEAR_INVALID_JSON",
                next_action="Retry later or inspect Linear API availability; Palari did not store the raw response.",
            ) from exc
        if not isinstance(decoded, dict):
            raise LinearAdapterError(
                "Linear GraphQL response was not an object",
                code="LINEAR_UNSUPPORTED_RESPONSE",
                next_action="Inspect Linear API compatibility before retrying.",
            )
        errors = decoded.get("errors")
        if isinstance(errors, list) and errors:
            messages = [
                _short_error(str(error.get("message", "GraphQL error")))
                for error in errors
                if isinstance(error, dict)
            ]
            raise LinearAdapterError(
                "Linear GraphQL error: " + "; ".join(messages),
                code="LINEAR_GRAPHQL_ERROR",
                next_action="Resolve the Linear GraphQL error before retrying this command.",
            )
        data = decoded.get("data")
        if not isinstance(data, dict):
            raise LinearAdapterError(
                "Linear GraphQL response did not include data",
                code="LINEAR_UNSUPPORTED_RESPONSE",
                next_action="Inspect Linear API compatibility before retrying.",
            )
        return data


def normalize_issue(issue: dict[str, Any], *, fallback_identifier: str = "") -> dict[str, Any]:
    labels = issue.get("labels")
    label_nodes = labels.get("nodes", []) if isinstance(labels, dict) else []
    assignee = issue.get("assignee")
    state = issue.get("state")
    team = issue.get("team")
    identifier = _string(issue.get("identifier")) or fallback_identifier
    return {
        "id": _string(issue.get("id")),
        "identifier": identifier,
        "key": identifier,
        "title": _string(issue.get("title")) or identifier,
        "description": _string(issue.get("description")),
        "url": _string(issue.get("url")),
        "updated_at": _string(issue.get("updatedAt")),
        "state": _plain_mapping(state, ["id", "name", "type"]),
        "team": _plain_mapping(team, ["id", "key", "name"]),
        "labels": [
            _plain_mapping(label, ["id", "name"])
            for label in label_nodes
            if isinstance(label, dict)
        ],
        "assignee": _plain_mapping(assignee, ["id", "name", "email"]),
    }


def _plain_mapping(value: object, keys: list[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {key: _string(value.get(key)) for key in keys if _string(value.get(key))}


def _short_error(value: str) -> str:
    cleaned = " ".join(str(value).split())
    return cleaned[:300]


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""
