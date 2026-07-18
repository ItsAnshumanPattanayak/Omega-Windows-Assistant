"""Safe response formatting from parsed command data only."""

from omega.models import IntentType
from omega.understanding.result import CommandParseResult


def format_parse_response(result: CommandParseResult) -> str:
    if result.requires_clarification:
        return result.clarification_message or "Please clarify that command."
    if not result.matched:
        return "I don't understand that command yet."
    command = result.command
    values = {
        entity.name: entity.raw_value or str(entity.value)
        for entity in command.entities
    }
    descriptions = {
        IntentType.OPEN_APPLICATION: (
            f"open {values.get('application_name', 'that application')}"
        ),
        IntentType.CLOSE_APPLICATION: (
            f"close {values.get('application_name', 'that application')}"
        ),
        IntentType.CREATE_FOLDER: (
            f"create a folder named {values.get('folder_name', '')}"
        ),
        IntentType.CREATE_FILE: f"create {values.get('file_name', 'that file')}",
    }
    description = descriptions.get(
        command.intent, command.intent.value.replace("_", " ")
    )
    location = values.get("location")
    if location:
        description += f" on {location}"
    return (
        f"I understood that you want to {description}. "
        "Command execution is not available yet."
    )
