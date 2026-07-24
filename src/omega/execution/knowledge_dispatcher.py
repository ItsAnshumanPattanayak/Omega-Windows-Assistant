"""Knowledge proposals routed exclusively through Omega's central gateway."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from omega.knowledge.enums import KnowledgeExportFormat
from omega.knowledge.export_service import KnowledgeExportService
from omega.knowledge.models import (
    KnowledgeAnswer,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
)
from omega.knowledge.service import KnowledgeService
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.safety.models import ResourceFingerprint
from omega.understanding.result import CommandParseResult

_COLLECTION_INTENTS = frozenset(
    {
        IntentType.CREATE_KNOWLEDGE_COLLECTION,
        IntentType.LIST_KNOWLEDGE_COLLECTIONS,
        IntentType.SHOW_KNOWLEDGE_COLLECTION,
        IntentType.UPDATE_KNOWLEDGE_COLLECTION,
        IntentType.ARCHIVE_KNOWLEDGE_COLLECTION,
        IntentType.RESTORE_KNOWLEDGE_COLLECTION,
        IntentType.DELETE_KNOWLEDGE_COLLECTION,
    }
)
_DOCUMENT_INTENTS = frozenset(
    {
        IntentType.IMPORT_KNOWLEDGE_DOCUMENT,
        IntentType.LIST_KNOWLEDGE_DOCUMENTS,
        IntentType.SHOW_KNOWLEDGE_DOCUMENT,
        IntentType.MOVE_KNOWLEDGE_DOCUMENT,
        IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
        IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
    }
)
_QUERY_INTENTS = frozenset(
    {
        IntentType.SEARCH_KNOWLEDGE,
        IntentType.ASK_KNOWLEDGE,
        IntentType.SHOW_KNOWLEDGE_SOURCES,
        IntentType.EXPORT_KNOWLEDGE_RESULTS,
    }
)
_HANDLED = _COLLECTION_INTENTS | _DOCUMENT_INTENTS | _QUERY_INTENTS
_DESTRUCTIVE = frozenset(
    {
        IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
        IntentType.DELETE_KNOWLEDGE_COLLECTION,
    }
)
_READ_ONLY = frozenset(
    {
        IntentType.LIST_KNOWLEDGE_COLLECTIONS,
        IntentType.SHOW_KNOWLEDGE_COLLECTION,
        IntentType.LIST_KNOWLEDGE_DOCUMENTS,
        IntentType.SHOW_KNOWLEDGE_DOCUMENT,
        IntentType.SEARCH_KNOWLEDGE,
        IntentType.ASK_KNOWLEDGE,
        IntentType.SHOW_KNOWLEDGE_SOURCES,
    }
)


@dataclass(frozen=True)
class KnowledgeDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> KnowledgeDispatchResult:
        return cls(value.command, value.action, value.result)


class KnowledgeActionDispatcher:
    """Build typed knowledge actions and execute each approved callback once."""

    def __init__(
        self,
        service: KnowledgeService,
        gateway: SafeExecutionGateway,
        export_service: KnowledgeExportService,
    ) -> None:
        self.service = service
        self.gateway = gateway
        self.export_service = export_service
        self.last_search: KnowledgeSearchResult | None = None
        self.last_answer: KnowledgeAnswer | None = None

    def dispatch(self, parsed: CommandParseResult) -> KnowledgeDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _HANDLED
        ):
            return None
        target = self._target(command)
        reference = self._reference(command) or command.intent.value
        revision = getattr(target, "revision", None)
        risk = (
            RiskLevel.HIGH
            if command.intent in _DESTRUCTIVE
            else RiskLevel.LOW if command.intent in _READ_ONLY else RiskLevel.MEDIUM
        )
        action = Action(
            command.command_id,
            command.intent,
            parameters={
                "reference": reference,
                "revision": revision,
                "content_is_untrusted_data": True,
                "local_only": True,
            },
            risk_level=risk,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        raw_path = self._text(command, "document_path")
        context = SafetyContext(
            command,
            action,
            command.session_id or UUID(int=0),
            logical_source=Path(raw_path).name if raw_path else reference,
            target_type=(
                "knowledge_document"
                if command.intent in _DOCUMENT_INTENTS
                else "knowledge_collection"
            ),
            target_exists=target is not None,
            additional_context={
                "revision": revision,
                "document_content_is_untrusted_data": True,
                "cloud_upload": False,
                "shell_like": False,
                "source_fingerprint": getattr(target, "content_fingerprint", None),
                "path_validation_deferred_until_approval": bool(raw_path),
            },
        )
        confirmation = self._confirmation(command, target, reference)
        fingerprint = self._fingerprint(target)
        dispatched = self.gateway.submit(
            context,
            lambda: self._execute(command, action, target),
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=lambda: self._fingerprint(self._target(command)),
        )
        return KnowledgeDispatchResult.from_gateway(dispatched)

    def _execute(
        self, command: UserCommand, action: Action, target: object | None
    ) -> ActionResult:
        try:
            return self._execute_validated(command, action, target)
        except Exception as error:
            details = OmegaErrorDetails(
                "KNOWLEDGE_OPERATION_FAILED",
                ErrorCategory.VALIDATION,
                type(error).__name__,
                str(error) or "The local knowledge request failed safely.",
                True,
                action_id=action.action_id,
                command_id=command.command_id,
            )
            return ActionResult.failure_result(
                action.action_id,
                type(error).__name__,
                str(error) or "The local knowledge request failed safely.",
                details,
            )

    def _execute_validated(
        self, command: UserCommand, action: Action, target: object | None
    ) -> ActionResult:
        intent = command.intent
        if intent is IntentType.CREATE_KNOWLEDGE_COLLECTION:
            item = self.service.create_collection(
                self._required(command, "collection_name")
            )
            return self._success(
                action,
                "Knowledge collection created.",
                f'Created knowledge collection "{item.name}".',
                item.to_dict(),
            )
        if intent is IntentType.LIST_KNOWLEDGE_COLLECTIONS:
            collections = self.service.list_collections()
            message = (
                "\n".join(item.name for item in collections)
                or "No knowledge collections found."
            )
            return self._success(
                action,
                "Knowledge collections listed.",
                message,
                {"items": [item.to_dict() for item in collections]},
            )
        if intent in _COLLECTION_INTENTS:
            if not isinstance(target, KnowledgeCollection):
                raise ValueError("Specify one existing knowledge collection.")
            if intent is IntentType.SHOW_KNOWLEDGE_COLLECTION:
                return self._success(
                    action,
                    "Knowledge collection found.",
                    f"{target.name}\n{target.description}".strip(),
                    target.to_dict(),
                )
            if intent is IntentType.DELETE_KNOWLEDGE_COLLECTION:
                count = self.service.delete_collection(
                    target.collection_id,
                    target.revision,
                    include_documents=True,
                )
                return self._success(
                    action,
                    "Knowledge collection removed.",
                    f"Removed the collection and {count} knowledge document(s). "
                    "Original source files were preserved.",
                    {"documents_removed": count, "source_files_preserved": True},
                )
            new_name = self._updated_collection_name(command.original_text)
            updated_collection = self.service.update_collection(
                target.collection_id,
                target.revision,
                name=(
                    new_name
                    if intent is IntentType.UPDATE_KNOWLEDGE_COLLECTION
                    else None
                ),
                archived=(
                    True
                    if intent is IntentType.ARCHIVE_KNOWLEDGE_COLLECTION
                    else (
                        False
                        if intent is IntentType.RESTORE_KNOWLEDGE_COLLECTION
                        else None
                    )
                ),
            )
            return self._success(
                action,
                "Knowledge collection updated.",
                f'Updated knowledge collection "{updated_collection.name}".',
                updated_collection.to_dict(),
            )
        if intent is IntentType.IMPORT_KNOWLEDGE_DOCUMENT:
            collection_name = self._text(command, "collection_name")
            collection = (
                self.service.repository.resolve_collection(collection_name)
                if collection_name
                else self.service.ensure_default_collection()
            )
            import_result = self.service.import_document(
                Path(self._required(command, "document_path")), collection
            )
            message = (
                f'"{import_result.document.title}" was already indexed.'
                if import_result.duplicate
                else (
                    f'Imported "{import_result.document.title}" into '
                    f'"{collection.name}" as {import_result.chunks_created} '
                    "local text chunk(s)."
                )
            )
            return self._success(
                action,
                "Knowledge document imported.",
                message,
                {
                    "document": import_result.document.to_dict(),
                    "chunks_created": import_result.chunks_created,
                    "duplicate": import_result.duplicate,
                    "semantic_available": import_result.semantic_available,
                },
            )
        if intent is IntentType.LIST_KNOWLEDGE_DOCUMENTS:
            collection_ref = self._text(command, "collection_reference")
            collection_id = (
                self.service.repository.resolve_collection(collection_ref).collection_id
                if collection_ref
                else None
            )
            documents = self.service.list_documents(collection_id)
            message = (
                "\n".join(item.title for item in documents) or "No documents found."
            )
            return self._success(
                action,
                "Knowledge documents listed.",
                message,
                {"items": [item.to_dict() for item in documents]},
            )
        if intent in _DOCUMENT_INTENTS:
            if not isinstance(target, KnowledgeDocument):
                raise ValueError("Specify one existing knowledge document.")
            if intent is IntentType.SHOW_KNOWLEDGE_DOCUMENT:
                return self._success(
                    action,
                    "Knowledge document found.",
                    f"{target.title} ({target.source_type.value}, "
                    f"{target.character_count:,} characters)",
                    target.to_dict(),
                )
            if intent is IntentType.REINDEX_KNOWLEDGE_DOCUMENT:
                reindex_result = self.service.reindex_document(
                    target.document_id, target.revision
                )
                return self._success(
                    action,
                    "Knowledge document re-indexed.",
                    (
                        f'Re-indexed "{target.title}" with '
                        f"{reindex_result.chunks_replaced} chunk(s)."
                        if reindex_result.changed
                        else f'"{target.title}" has not changed.'
                    ),
                    {
                        "document": reindex_result.document.to_dict(),
                        "chunks_replaced": reindex_result.chunks_replaced,
                        "changed": reindex_result.changed,
                    },
                )
            if intent is IntentType.REMOVE_KNOWLEDGE_DOCUMENT:
                removal_result = self.service.remove_document(
                    target.document_id, target.revision
                )
                return self._success(
                    action,
                    "Knowledge document removed.",
                    "The document and its local index were removed. "
                    "The original source file was preserved.",
                    {
                        "document_id": str(removal_result.document_id),
                        "chunks_removed": removal_result.chunks_removed,
                        "source_file_preserved": True,
                    },
                )
            if intent is IntentType.MOVE_KNOWLEDGE_DOCUMENT:
                collection = self.service.repository.resolve_collection(
                    self._required(command, "collection_name")
                )
                moved_document = self.service.move_document(
                    target.document_id, target.revision, collection.collection_id
                )
                return self._success(
                    action,
                    "Knowledge document moved.",
                    f'Moved "{moved_document.title}" to "{collection.name}".',
                    moved_document.to_dict(),
                )
        if intent is IntentType.SEARCH_KNOWLEDGE:
            collection_name = self._text(command, "collection_name")
            collection_id = (
                self.service.repository.resolve_collection(
                    collection_name
                ).collection_id
                if collection_name
                else None
            )
            query = KnowledgeSearchQuery(
                self._required(command, "knowledge_query"),
                collection_id=collection_id,
                limit=self.service.configuration.default_search_limit,
            )
            search_result = self.service.search(query)
            self.last_search = search_result
            message = (
                "\n".join(
                    f"{hit.source.label()}: {hit.source.preview}"
                    for hit in search_result.hits
                )
                or "No indexed source matched that query."
            )
            if search_result.semantic_fallback:
                message += (
                    "\nSemantic search is unavailable; keyword results are shown."
                )
            return self._success(
                action,
                "Local knowledge searched.",
                message,
                {
                    "query": query.text,
                    "hit_count": len(search_result.hits),
                    "semantic_fallback": search_result.semantic_fallback,
                },
            )
        if intent is IntentType.ASK_KNOWLEDGE:
            answer = self.service.answer(self._required(command, "knowledge_query"))
            self.last_answer = answer
            return self._success(
                action,
                "Grounded local answer prepared.",
                answer.answer
                + (
                    "\n\nSources:\n"
                    + "\n".join(f"- {source.label()}" for source in answer.sources)
                    if answer.sources
                    else ""
                ),
                {
                    "supported": answer.supported,
                    "source_count": len(answer.sources),
                },
            )
        if intent is IntentType.SHOW_KNOWLEDGE_SOURCES:
            if self.last_answer is None or not self.last_answer.sources:
                raise ValueError(
                    "There is no sourced knowledge answer in this process."
                )
            message = "\n".join(
                f"- {source.label()}: {source.preview}"
                for source in self.last_answer.sources
            )
            return self._success(
                action,
                "Knowledge sources listed.",
                message,
                {"source_count": len(self.last_answer.sources)},
            )
        if intent is IntentType.EXPORT_KNOWLEDGE_RESULTS:
            name = "omega-knowledge-results.json"
            exported = self.export_service.export_metadata(
                name,
                KnowledgeExportFormat.JSON,
                search=self.last_search,
                answer=self.last_answer,
            )
            return self._success(
                action,
                "Knowledge results exported.",
                f"Exported {exported.item_count} document metadata record(s).",
                {
                    "path": exported.path,
                    "format": exported.format.value,
                    "bytes_written": exported.bytes_written,
                },
            )
        raise ValueError("That knowledge operation is not supported.")

    def _target(self, command: UserCommand) -> object | None:
        try:
            if command.intent in _COLLECTION_INTENTS - {
                IntentType.CREATE_KNOWLEDGE_COLLECTION,
                IntentType.LIST_KNOWLEDGE_COLLECTIONS,
            }:
                reference = self._text(command, "collection_reference")
                return (
                    self.service.repository.resolve_collection(
                        reference, include_archived=True
                    )
                    if reference
                    else None
                )
            if command.intent in _DOCUMENT_INTENTS - {
                IntentType.IMPORT_KNOWLEDGE_DOCUMENT,
                IntentType.LIST_KNOWLEDGE_DOCUMENTS,
            }:
                reference = self._text(command, "document_reference")
                return (
                    self.service.repository.resolve_document(reference)
                    if reference
                    else None
                )
        except Exception:
            return None
        return None

    @staticmethod
    def _fingerprint(target: object | None) -> ResourceFingerprint | None:
        if isinstance(target, KnowledgeDocument):
            return ResourceFingerprint(
                "knowledge_document",
                f"{target.document_id}:{target.revision}",
                True,
                digest=target.content_fingerprint,
            )
        if isinstance(target, KnowledgeCollection):
            return ResourceFingerprint(
                "knowledge_collection",
                f"{target.collection_id}:{target.revision}",
                True,
            )
        return None

    @staticmethod
    def _confirmation(
        command: UserCommand, target: object | None, reference: str
    ) -> ConfirmationSpec | None:
        if command.intent not in _DESTRUCTIVE:
            return None
        kind = "document" if isinstance(target, KnowledgeDocument) else "collection"
        phrase = f"confirm remove knowledge {kind} {reference}"
        return ConfirmationSpec(
            reference,
            f'Removing knowledge {kind} "{reference}" requires confirmation. '
            f'Type "{phrase}". Original source files will be preserved.',
            phrase,
            f"cancel remove knowledge {kind} {reference}",
        )

    def _reference(self, command: UserCommand) -> str | None:
        return (
            self._text(command, "document_reference")
            or self._text(command, "collection_reference")
            or self._text(command, "collection_name")
            or (
                Path(self._text(command, "document_path") or "").name
                if self._text(command, "document_path")
                else None
            )
        )

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        for item in command.entities:
            if item.name == name and isinstance(item.value, str):
                return item.value
        return None

    @classmethod
    def _required(cls, command: UserCommand, name: str) -> str:
        value = cls._text(command, name)
        if value is None or not value.strip():
            raise ValueError(f"{name} is required.")
        return value

    @staticmethod
    def _updated_collection_name(text: str) -> str:
        match = re.search(
            r"\bknowledge collection\s+(?:to|with)\s+(.+)$", text, re.IGNORECASE
        )
        if match is None:
            raise ValueError("Specify the updated collection name.")
        return match.group(1).strip()

    @staticmethod
    def _success(
        action: Action, message: str, user_message: str, data: dict[str, JsonValue]
    ) -> ActionResult:
        return ActionResult.success_result(
            action.action_id, message, user_message, data=data
        )
