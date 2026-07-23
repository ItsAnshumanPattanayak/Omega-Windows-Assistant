"""Persistence boundary for commands, actions, and terminal results."""

from __future__ import annotations

from omega.core.exceptions import DatabaseError
from omega.database.action_repository import ActionRepository
from omega.database.command_repository import CommandRepository
from omega.models import Action, ActionResult, UserCommand


class ExecutionPersistence:
    """Persist each execution lifecycle without triggering execution."""

    def __init__(
        self,
        commands: CommandRepository,
        actions: ActionRepository,
    ) -> None:
        self.commands = commands
        self.actions = actions

    def record_proposal(self, command: UserCommand, action: Action) -> None:
        """Store a command and its proposed action exactly once."""

        if self.commands.get(command.command_id) is None:
            self.commands.add(command)
        if self.actions.get(action.action_id) is None:
            self.actions.add(action)

    def record_command(self, command: UserCommand) -> None:
        if self.commands.get(command.command_id) is None:
            self.commands.add(command)

    def update_action(self, action: Action) -> None:
        self.actions.update(action)

    def record_terminal(self, action: Action, result: ActionResult) -> None:
        """Atomically ordered lifecycle writes after one OS attempt."""

        self.actions.update(action)
        if self.actions.get_result(action.action_id) is not None:
            raise DatabaseError("The action result was already persisted.")
        self.actions.save_result(result)
