from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_COMMAND: ContextVar[str] = ContextVar("palari_mutation_command", default="workspace write")
_ACTOR: ContextVar[str] = ContextVar("palari_mutation_actor", default="local-operator")
_ACTION: ContextVar[str] = ContextVar("palari_mutation_action", default="updated-workspace")


@contextmanager
def mutation_context(command: str, actor: str, action: str = "updated-workspace") -> Iterator[None]:
    command_token = _COMMAND.set(command or "workspace write")
    actor_token = _ACTOR.set(actor or "local-operator")
    action_token = _ACTION.set(action or "updated-workspace")
    try:
        yield
    finally:
        _ACTION.reset(action_token)
        _ACTOR.reset(actor_token)
        _COMMAND.reset(command_token)


def current_mutation_identity() -> tuple[str, str, str]:
    return _COMMAND.get(), _ACTOR.get(), _ACTION.get()
