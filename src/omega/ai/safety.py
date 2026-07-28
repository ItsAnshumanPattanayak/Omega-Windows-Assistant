"""Static policy facts for the local-AI boundary."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AiSafetyPolicy:
    """Non-overridable local-AI rules; prompt text is never authorization."""

    allow_tool_execution: bool = False
    allow_shell_execution: bool = False
    allow_remote_endpoints: bool = False
    allow_model_downloads: bool = False
    allow_generated_action_dispatch: bool = False
    require_generated_content_label: bool = True

    def validate(self) -> None:
        if any(
            (
                self.allow_tool_execution,
                self.allow_shell_execution,
                self.allow_remote_endpoints,
                self.allow_model_downloads,
                self.allow_generated_action_dispatch,
            )
        ):
            raise ValueError("Omega's local-AI safety boundary cannot be weakened.")
