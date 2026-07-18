from omega.models import EntityType
from omega.understanding import CommandParser


def test_application_file_folder_extension_location_and_content_entities() -> None:
    parser = CommandParser()
    app = parser.parse("Open Google Chrome").command
    assert app.entities[0].value == "chrome"
    folder = parser.parse("Create a folder named College Work on Desktop").command
    assert any(entity.value == "College Work" for entity in folder.entities)
    assert any(entity.value == "desktop" for entity in folder.entities)
    file = parser.parse("Create a text file named author").command
    assert any(
        entity.entity_type is EntityType.FILE_EXTENSION and entity.value == ".txt"
        for entity in file.entities
    )
    write = parser.parse('Write "Hello World" into notes.txt').command
    assert any(
        entity.entity_type is EntityType.TEXT_CONTENT and entity.value == "Hello World"
        for entity in write.entities
    )


def test_source_destination_and_rename_entities() -> None:
    parser = CommandParser()
    moved = parser.parse("Move notes.txt to Downloads").command
    names = {entity.name for entity in moved.entities}
    assert {"source_file", "destination"}.issubset(names)
    renamed = parser.parse("Rename author.txt to writer.txt").command
    assert {entity.name for entity in renamed.entities} == {"source_file", "new_name"}
