from pathlib import Path
from uuid import uuid4

from omega.execution import KnowledgeActionDispatcher
from omega.knowledge import KnowledgeExportFormat
from omega.knowledge.export_service import KnowledgeExportService
from omega.models import CommandSource, IntentType
from omega.safety import SafeExecutionGateway
from omega.session import OmegaSession
from omega.understanding import CommandParser


def test_reindex_replaces_chunks_and_removal_preserves_source(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, repository, configuration = knowledge
    collection = service.create_collection("Reindex")  # type: ignore[attr-defined]
    source = tmp_path / "changing.txt"
    source.write_text("Old searchable text.", encoding="utf-8")
    imported = service.import_document(source, collection)  # type: ignore[attr-defined]
    source.write_text("New searchable text after update.", encoding="utf-8")
    reindexed = service.reindex_document(  # type: ignore[attr-defined]
        imported.document.document_id, imported.document.revision
    )
    assert reindexed.changed
    assert (
        "New searchable"
        in repository.chunks_for_document(  # type: ignore[attr-defined]
            imported.document.document_id
        )[0].text
    )
    removed = service.remove_document(  # type: ignore[attr-defined]
        reindexed.document.document_id, reindexed.document.revision
    )
    assert removed.source_file_preserved and source.exists()
    assert repository.chunks_for_document(removed.document_id) == ()  # type: ignore[attr-defined]


def test_export_redacts_paths_and_never_overwrites(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, repository, configuration = knowledge
    collection = service.create_collection("Export")  # type: ignore[attr-defined]
    source = tmp_path / "private.txt"
    source.write_text("Bounded local source.", encoding="utf-8")
    service.import_document(source, collection)  # type: ignore[attr-defined]
    exporter = KnowledgeExportService(configuration, repository, tmp_path / "exports")
    result = exporter.export_metadata("metadata.json", KnowledgeExportFormat.JSON)
    content = Path(result.path).read_text(encoding="utf-8")
    assert str(source) not in content
    assert "source_path" in content


def test_dispatcher_uses_gateway_and_scoped_removal_confirmation(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, repository, configuration = knowledge
    collection = service.create_collection("Dispatch")  # type: ignore[attr-defined]
    source = tmp_path / "dispatch.txt"
    source.write_text("Dispatch through the safety gateway.", encoding="utf-8")
    imported = service.import_document(source, collection)  # type: ignore[attr-defined]
    gateway = SafeExecutionGateway()
    dispatcher = KnowledgeActionDispatcher(
        service,  # type: ignore[arg-type]
        gateway,
        KnowledgeExportService(configuration, repository, tmp_path / "exports"),
    )
    session_id = uuid4()
    parsed = CommandParser().parse(
        f"Remove the {imported.document.title} document from my knowledge base",
        session_id,
    )
    result = dispatcher.dispatch(parsed)
    assert result is not None
    assert not result.result.success
    assert "confirm remove knowledge document" in result.user_message
    assert repository.get_document(imported.document.document_id) is not None  # type: ignore[attr-defined]
    confirmed = gateway.handle_confirmation(
        f"confirm remove knowledge document {imported.document.title}",
        session_id,
    )
    assert confirmed is not None and confirmed.result.success
    assert source.exists()
    assert repository.get_document(imported.document.document_id) is None  # type: ignore[attr-defined]


def test_import_action_validates_file_only_inside_gateway_executor(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, repository, configuration = knowledge
    collection = service.create_collection("Imported")  # type: ignore[attr-defined]
    source = tmp_path / "approved.txt"
    source.write_text("Local import through the gateway.", encoding="utf-8")
    gateway = SafeExecutionGateway()
    dispatcher = KnowledgeActionDispatcher(
        service,  # type: ignore[arg-type]
        gateway,
        KnowledgeExportService(configuration, repository, tmp_path / "exports"),
    )
    result = dispatcher.dispatch(
        CommandParser().parse(f"Add the document {source} to {collection.name}")
    )
    assert result is not None and result.result.success
    assert repository.list_documents()  # type: ignore[attr-defined]


def test_terminal_and_voice_use_the_same_knowledge_lifecycle(
    knowledge: tuple[object, object, object], tmp_path: Path
) -> None:
    service, repository, configuration = knowledge
    gateway = SafeExecutionGateway()
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        knowledge_dispatcher=KnowledgeActionDispatcher(
            service,  # type: ignore[arg-type]
            gateway,
            KnowledgeExportService(configuration, repository, tmp_path / "exports"),
        ),
        safety_gateway=gateway,
    )
    session.handle_input("Hello Omega")
    response = session.handle_input(
        "Create a knowledge collection called Voice Notes",
        source=CommandSource.VOICE,
    )
    assert "Created knowledge collection" in response
    assert session.history[-1].intent is IntentType.CREATE_KNOWLEDGE_COLLECTION
    assert session.history[-1].source is CommandSource.VOICE
