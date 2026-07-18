"""Stable user-safe messages for centralized policy decisions."""

DEFAULT_DENIAL = "Omega does not have permission to perform that operation."
SHELL_DENIAL = "Omega does not execute arbitrary shell commands."
PROTECTED_PATH_DENIAL = "Omega cannot modify or inspect protected Windows locations."
FILE_DELETE_DENIAL = (
    "Permanent file deletion is disabled. Safe Recycle Bin deletion will be added "
    "in Phase 8."
)
FOLDER_DELETE_DENIAL = (
    "Permanent folder deletion is disabled. Safe Recycle Bin deletion will be "
    "added in Phase 8."
)
UNSAFE_EXTENSION_DENIAL = (
    "Omega does not create, modify, open, or execute command-script files."
)
EXPIRED_CONFIRMATION = (
    "That confirmation request has expired. Please give the original command again."
)
RESOURCE_CHANGED = (
    "The target changed while waiting for confirmation. I cancelled the operation "
    "for safety."
)
