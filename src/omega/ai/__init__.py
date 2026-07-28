"""Public controlled local-AI API."""

from omega.ai.cancellation import AiCancellationToken
from omega.ai.configuration import AiConfiguration
from omega.ai.exceptions import (
    AiConfigurationError,
    AiDisabledError,
    AiError,
    AiModelError,
    AiPermissionError,
    AiProviderError,
    AiRequestCancelledError,
    AiResourceError,
    AiValidationError,
)
from omega.ai.integrations import (
    AiDraftProposal,
    AiKnowledgeAssistant,
    AiProposalService,
    PluginAiAccess,
)
from omega.ai.models import (
    AiContextItem,
    AiContextKind,
    AiEmbeddingRequest,
    AiEmbeddingResult,
    AiGenerationRequest,
    AiGenerationResult,
    AiGroundingSource,
    AiModelCapability,
    AiModelDescriptor,
    AiModelStatus,
    AiProviderStatus,
    AiUsageMetrics,
)
from omega.ai.prompt import AiPromptBuilder
from omega.ai.protocols import (
    AiProvider,
    LocalEmbeddingProvider,
    LocalTextGenerationProvider,
)
from omega.ai.providers import FakeAiProvider, LoopbackHttpAiProvider
from omega.ai.registry import AiModelRegistry, AiProviderRegistry
from omega.ai.resource import AiResourceManager
from omega.ai.safety import AiSafetyPolicy
from omega.ai.service import AiService
from omega.ai.validation import AiResponseValidator

__all__ = [
    "AiCancellationToken",
    "AiConfiguration",
    "AiConfigurationError",
    "AiContextItem",
    "AiContextKind",
    "AiDisabledError",
    "AiDraftProposal",
    "AiEmbeddingRequest",
    "AiEmbeddingResult",
    "AiError",
    "AiGenerationRequest",
    "AiGenerationResult",
    "AiGroundingSource",
    "AiKnowledgeAssistant",
    "AiModelCapability",
    "AiModelDescriptor",
    "AiModelError",
    "AiModelRegistry",
    "AiModelStatus",
    "AiPermissionError",
    "AiPromptBuilder",
    "AiProposalService",
    "AiProvider",
    "AiProviderError",
    "AiProviderRegistry",
    "AiProviderStatus",
    "AiRequestCancelledError",
    "AiResourceError",
    "AiResourceManager",
    "AiResponseValidator",
    "AiSafetyPolicy",
    "AiService",
    "AiUsageMetrics",
    "AiValidationError",
    "FakeAiProvider",
    "LocalEmbeddingProvider",
    "LocalTextGenerationProvider",
    "LoopbackHttpAiProvider",
    "PluginAiAccess",
]
