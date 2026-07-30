"""Public Omega V2 GUI foundation exports."""

from omega.gui_v2.assets import GuiAssetError, resolve_gui_asset
from omega.gui_v2.configuration import V2GuiConfiguration
from omega.gui_v2.state import (
    STATE_METADATA,
    GuiState,
    GuiStateManager,
    GuiStateMetadata,
    GuiStateTransitionError,
)
from omega.gui_v2.view_model import OmegaV2ViewModel, V2ViewSnapshot

__all__ = [
    "STATE_METADATA",
    "GuiAssetError",
    "GuiState",
    "GuiStateManager",
    "GuiStateMetadata",
    "GuiStateTransitionError",
    "OmegaV2ViewModel",
    "V2GuiConfiguration",
    "V2ViewSnapshot",
    "resolve_gui_asset",
]
