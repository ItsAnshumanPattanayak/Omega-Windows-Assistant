"""Parameterized SQLite repositories for revisioned productivity data."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import cast
from uuid import UUID

from omega.database import DatabaseConnectionFactory
from omega.productivity.enums import ReminderLinkType, TaskPriority, TaskStatus
from omega.productivity.exceptions import (
    ProductivityConflictError,
    ProductivityError,
    StaleProductivityRevisionError,
)
from omega.productivity.models import Note, ReminderLink, Task, TaskList


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value).astimezone(UTC) if value else None


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _like(value: str) -> str:
    return (
        "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )


class ProductivityRepository:
    """Store notes, lists, tasks, tags, and reminder links without creating schema."""

    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    def add_note(self, note: Note) -> Note:
        self._execute(
            """
            INSERT INTO notes (
              note_id,title,body,is_pinned,is_archived,created_at,updated_at,
              archived_at,source_command_id,metadata_json,revision
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            self._note_values(note),
        )
        return note

    def get_note(self, note_id: UUID) -> Note | None:
        row = self._one("SELECT * FROM notes WHERE note_id = ?", (str(note_id),))
        return self._note(row) if row else None

    def resolve_note(self, reference: str, *, include_archived: bool = False) -> Note:
        rows = self._all(
            "SELECT * FROM notes WHERE lower(title)=lower(?) "
            + ("" if include_archived else "AND is_archived=0 ")
            + "ORDER BY updated_at DESC,note_id",
            (reference.strip(),),
        )
        if len(rows) != 1:
            raise ProductivityConflictError(
                "No note matched that title."
                if not rows
                else "More than one note matches; use its exact ID."
            )
        return self._note(rows[0])

    def list_notes(
        self,
        *,
        include_archived: bool = False,
        pinned: bool | None = None,
        query: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> tuple[Note, ...]:
        clauses = ["1=1"]
        values: list[object] = []
        if not include_archived:
            clauses.append("is_archived=0")
        if pinned is not None:
            clauses.append("is_pinned=?")
            values.append(int(pinned))
        if query:
            clauses.append("(title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')")
            value = _like(query)
            values.extend((value, value))
        joins = ""
        if tag:
            joins = (
                " JOIN note_tags nt ON nt.note_id=n.note_id"
                " JOIN tags g ON g.tag_id=nt.tag_id"
            )
            clauses.append("g.normalized_name=?")
            values.append(tag.casefold())
        values.append(limit)
        rows = self._all(
            "SELECT DISTINCT n.* FROM notes n"
            + joins
            + " WHERE "
            + " AND ".join(clauses)
            + " ORDER BY n.is_pinned DESC,n.updated_at DESC,n.note_id LIMIT ?",
            tuple(values),
        )
        return tuple(self._note(row) for row in rows)

    def update_note(self, note: Note, expected_revision: int) -> Note:
        values = self._note_values(note)
        self._revision_update(
            """
            UPDATE notes SET title=?,body=?,is_pinned=?,is_archived=?,created_at=?,
              updated_at=?,archived_at=?,source_command_id=?,metadata_json=?,revision=?
            WHERE note_id=? AND revision=?
            """,
            (*values[1:], values[0], expected_revision),
            "note",
        )
        return note

    def delete_note(self, note_id: UUID, expected_revision: int) -> None:
        self._revision_delete("notes", "note_id", note_id, expected_revision)

    def add_task_list(self, item: TaskList) -> TaskList:
        self._execute(
            """
            INSERT INTO task_lists (
              task_list_id,name,description,is_archived,created_at,updated_at,
              archived_at,metadata_json,revision
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            self._list_values(item),
        )
        return item

    def get_task_list(self, item_id: UUID) -> TaskList | None:
        row = self._one(
            "SELECT * FROM task_lists WHERE task_list_id=?", (str(item_id),)
        )
        return self._task_list(row) if row else None

    def resolve_task_list(self, name: str) -> TaskList:
        rows = self._all(
            "SELECT * FROM task_lists WHERE lower(name)=lower(?) "
            "ORDER BY updated_at DESC",
            (name.strip(),),
        )
        if len(rows) != 1:
            raise ProductivityConflictError(
                "No task list matched that name."
                if not rows
                else "More than one task list matches."
            )
        return self._task_list(rows[0])

    def list_task_lists(
        self, *, include_archived: bool = False
    ) -> tuple[TaskList, ...]:
        rows = self._all(
            "SELECT * FROM task_lists "
            + ("" if include_archived else "WHERE is_archived=0 ")
            + "ORDER BY lower(name),task_list_id"
        )
        return tuple(self._task_list(row) for row in rows)

    def search_task_lists(self, query: str, *, limit: int = 50) -> tuple[TaskList, ...]:
        selected = _like(query)
        rows = self._all(
            "SELECT * FROM task_lists WHERE "
            "(name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') "
            "ORDER BY lower(name),task_list_id LIMIT ?",
            (selected, selected, limit),
        )
        return tuple(self._task_list(row) for row in rows)

    def update_task_list(self, item: TaskList, expected_revision: int) -> TaskList:
        values = self._list_values(item)
        self._revision_update(
            """
            UPDATE task_lists SET name=?,description=?,is_archived=?,created_at=?,
              updated_at=?,archived_at=?,metadata_json=?,revision=?
            WHERE task_list_id=? AND revision=?
            """,
            (*values[1:], values[0], expected_revision),
            "task list",
        )
        return item

    def delete_task_list(
        self, item_id: UUID, expected_revision: int, *, include_tasks: bool = False
    ) -> None:
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM tasks WHERE task_list_id=?", (str(item_id),)
                ).fetchone()[0]
            )
            if count and not include_tasks:
                raise ProductivityConflictError("The task list is not empty.")
            cursor = connection.execute(
                "DELETE FROM task_lists WHERE task_list_id=? AND revision=?",
                (str(item_id), expected_revision),
            )
            if cursor.rowcount != 1:
                raise StaleProductivityRevisionError(
                    "The task list changed before deletion."
                )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def add_task(self, task: Task) -> Task:
        self._execute(
            """
            INSERT INTO tasks (
              task_id,task_list_id,title,description,status,priority,due_at_utc,
              completed_at,cancelled_at,is_archived,archived_at,created_at,updated_at,
              source_command_id,metadata_json,revision
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            self._task_values(task),
        )
        return task

    def get_task(self, task_id: UUID) -> Task | None:
        row = self._one("SELECT * FROM tasks WHERE task_id=?", (str(task_id),))
        return self._task(row) if row else None

    def resolve_task(self, reference: str, *, include_archived: bool = False) -> Task:
        rows = self._all(
            "SELECT * FROM tasks WHERE lower(title)=lower(?) "
            + ("" if include_archived else "AND is_archived=0 ")
            + "ORDER BY updated_at DESC,task_id",
            (reference.strip(),),
        )
        if len(rows) != 1:
            raise ProductivityConflictError(
                "No task matched that title."
                if not rows
                else "More than one task matches; use its exact ID."
            )
        return self._task(rows[0])

    def list_tasks(
        self,
        *,
        task_list_id: UUID | None = None,
        statuses: Sequence[TaskStatus] = (),
        priorities: Sequence[TaskPriority] = (),
        include_archived: bool = False,
        due_from: datetime | None = None,
        due_before: datetime | None = None,
        overdue_at: datetime | None = None,
        query: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> tuple[Task, ...]:
        clauses = ["1=1"]
        values: list[object] = []
        if task_list_id:
            clauses.append("t.task_list_id=?")
            values.append(str(task_list_id))
        if statuses:
            clauses.append("t.status IN (" + ",".join("?" for _ in statuses) + ")")
            values.extend(item.value for item in statuses)
        if priorities:
            clauses.append("t.priority IN (" + ",".join("?" for _ in priorities) + ")")
            values.extend(item.value for item in priorities)
        if not include_archived:
            clauses.append("t.is_archived=0")
        if due_from:
            clauses.append("t.due_at_utc>=?")
            values.append(due_from.astimezone(UTC).isoformat())
        if due_before:
            clauses.append("t.due_at_utc<?")
            values.append(due_before.astimezone(UTC).isoformat())
        if overdue_at:
            clauses.extend(("t.due_at_utc<?", "t.status IN ('pending','in_progress')"))
            values.append(overdue_at.astimezone(UTC).isoformat())
        if query:
            clauses.append(
                "(t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\')"
            )
            selected = _like(query)
            values.extend((selected, selected))
        joins = ""
        if tag:
            joins = (
                " JOIN task_tags tt ON tt.task_id=t.task_id"
                " JOIN tags g ON g.tag_id=tt.tag_id"
            )
            clauses.append("g.normalized_name=?")
            values.append(tag.casefold())
        values.append(limit)
        rows = self._all(
            "SELECT DISTINCT t.* FROM tasks t"
            + joins
            + " WHERE "
            + " AND ".join(clauses)
            + " ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END,"
            "t.due_at_utc IS NULL,t.due_at_utc,t.updated_at DESC,t.task_id LIMIT ?",
            tuple(values),
        )
        return tuple(self._task(row) for row in rows)

    def tasks_due_on(self, day: date, timezone_now: datetime) -> tuple[Task, ...]:
        local_start = datetime.combine(day, datetime.min.time(), timezone_now.tzinfo)
        return self.list_tasks(
            due_from=local_start.astimezone(UTC),
            due_before=(local_start + timedelta(days=1)).astimezone(UTC),
            limit=200,
        )

    def update_task(self, task: Task, expected_revision: int) -> Task:
        values = self._task_values(task)
        self._revision_update(
            """
            UPDATE tasks SET task_list_id=?,title=?,description=?,status=?,priority=?,
              due_at_utc=?,completed_at=?,cancelled_at=?,is_archived=?,archived_at=?,
              created_at=?,updated_at=?,source_command_id=?,metadata_json=?,revision=?
            WHERE task_id=? AND revision=?
            """,
            (*values[1:], values[0], expected_revision),
            "task",
        )
        return task

    def delete_task(self, task_id: UUID, expected_revision: int) -> None:
        self._revision_delete("tasks", "task_id", task_id, expected_revision)

    def set_note_tags(self, note_id: UUID, tags: Sequence[str]) -> None:
        self._set_tags("note_tags", "note_id", note_id, tags)

    def set_task_tags(self, task_id: UUID, tags: Sequence[str]) -> None:
        self._set_tags("task_tags", "task_id", task_id, tags)

    def link_reminder(self, link: ReminderLink) -> ReminderLink:
        self._execute(
            """
            INSERT INTO task_reminder_links(task_id,schedule_id,link_type,created_at)
            VALUES(?,?,?,?)
            """,
            (
                str(link.task_id),
                str(link.schedule_id),
                link.link_type.value,
                link.created_at.isoformat(),
            ),
        )
        return link

    def unlink_reminder(self, task_id: UUID, schedule_id: UUID) -> bool:
        return (
            self._execute(
                "DELETE FROM task_reminder_links WHERE task_id=? AND schedule_id=?",
                (str(task_id), str(schedule_id)),
            )
            == 1
        )

    def reminder_links(self, task_id: UUID) -> tuple[ReminderLink, ...]:
        rows = self._all(
            "SELECT * FROM task_reminder_links WHERE task_id=? "
            "ORDER BY created_at,schedule_id",
            (str(task_id),),
        )
        return tuple(
            ReminderLink(
                UUID(row["task_id"]),
                UUID(row["schedule_id"]),
                ReminderLinkType(row["link_type"]),
                _timestamp(row["created_at"]) or datetime.now(UTC),
            )
            for row in rows
        )

    def import_bundle(
        self,
        notes: Sequence[Note],
        task_lists: Sequence[TaskList],
        tasks: Sequence[Task],
    ) -> None:
        """Insert one fully validated import in a single transaction."""

        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            for list_item in task_lists:
                connection.execute(
                    "INSERT INTO task_lists VALUES(?,?,?,?,?,?,?,?,?)",
                    self._list_values(list_item),
                )
            for note_item in notes:
                connection.execute(
                    "INSERT INTO notes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    self._note_values(note_item),
                )
                self._set_tags_connection(
                    connection,
                    "note_tags",
                    "note_id",
                    note_item.note_id,
                    note_item.tags,
                )
            for task_item in tasks:
                connection.execute(
                    "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    self._task_values(task_item),
                )
                self._set_tags_connection(
                    connection,
                    "task_tags",
                    "task_id",
                    task_item.task_id,
                    task_item.tags,
                )
            connection.commit()
        except Exception as error:
            if connection.in_transaction:
                connection.rollback()
            raise ProductivityConflictError(
                "The productivity import conflicted and was rolled back."
            ) from error
        finally:
            connection.close()

    def _set_tags(
        self, junction: str, column: str, item_id: UUID, tags: Sequence[str]
    ) -> None:
        if junction not in {"note_tags", "task_tags"}:
            raise ProductivityError("Invalid tag association.")
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._set_tags_connection(
                connection, junction, column, item_id, tags, clear=True
            )
            connection.execute(
                "DELETE FROM tags WHERE tag_id NOT IN "
                "(SELECT tag_id FROM note_tags UNION SELECT tag_id FROM task_tags)"
            )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _set_tags_connection(
        connection: sqlite3.Connection,
        junction: str,
        column: str,
        item_id: UUID,
        tags: Sequence[str],
        *,
        clear: bool = False,
    ) -> None:
        if clear:
            connection.execute(
                f"DELETE FROM {junction} WHERE {column}=?", (str(item_id),)
            )
        for display in tags:
            normalized = display.casefold()
            connection.execute(
                """
                INSERT INTO tags(tag_id,normalized_name,display_name,created_at)
                VALUES(lower(hex(randomblob(4)))||'-'||lower(hex(randomblob(2)))||'-4'||
                substr(lower(hex(randomblob(2))),2)||'-a'||
                substr(lower(hex(randomblob(2))),2)||'-'||lower(hex(randomblob(6))),?,?,?)
                ON CONFLICT(normalized_name) DO NOTHING
                """,
                (normalized, display, datetime.now(UTC).isoformat()),
            )
            row = connection.execute(
                "SELECT tag_id FROM tags WHERE normalized_name=?", (normalized,)
            ).fetchone()
            if row is None:
                raise ProductivityError("The tag association could not be created.")
            connection.execute(
                f"INSERT INTO {junction}({column},tag_id) VALUES(?,?)",
                (str(item_id), row["tag_id"]),
            )

    def _tags(self, junction: str, column: str, item_id: str) -> tuple[str, ...]:
        rows = self._all(
            f"SELECT g.display_name FROM tags g JOIN {junction} j ON j.tag_id=g.tag_id "
            f"WHERE j.{column}=? ORDER BY g.normalized_name",
            (item_id,),
        )
        return tuple(str(row["display_name"]) for row in rows)

    def _one(self, sql: str, values: tuple[object, ...]) -> sqlite3.Row | None:
        connection = self.factory.connect()
        try:
            return cast(sqlite3.Row | None, connection.execute(sql, values).fetchone())
        finally:
            connection.close()

    def _all(self, sql: str, values: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        connection = self.factory.connect()
        try:
            return list(connection.execute(sql, values).fetchall())
        finally:
            connection.close()

    def _execute(self, sql: str, values: tuple[object, ...]) -> int:
        connection = self.factory.connect()
        try:
            cursor = connection.execute(sql, values)
            connection.commit()
            return cursor.rowcount
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise ProductivityConflictError(
                "That productivity record conflicts with existing data."
            ) from error
        finally:
            connection.close()

    def _revision_update(
        self, sql: str, values: tuple[object, ...], item_name: str
    ) -> None:
        if self._execute(sql, values) != 1:
            raise StaleProductivityRevisionError(
                f"The {item_name} changed before this update."
            )

    def _revision_delete(
        self, table: str, id_column: str, item_id: UUID, revision: int
    ) -> None:
        if table not in {"notes", "tasks"}:
            raise ProductivityError("Invalid deletion target.")
        count = self._execute(
            f"DELETE FROM {table} WHERE {id_column}=? AND revision=?",
            (str(item_id), revision),
        )
        if count != 1:
            raise StaleProductivityRevisionError(
                "The item changed before this deletion."
            )

    @staticmethod
    def _note_values(item: Note) -> tuple[object, ...]:
        return (
            str(item.note_id),
            item.title,
            item.body,
            int(item.is_pinned),
            int(item.is_archived),
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
            item.archived_at.isoformat() if item.archived_at else None,
            str(item.source_command_id) if item.source_command_id else None,
            _json(item.metadata),
            item.revision,
        )

    @staticmethod
    def _list_values(item: TaskList) -> tuple[object, ...]:
        return (
            str(item.task_list_id),
            item.name,
            item.description,
            int(item.is_archived),
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
            item.archived_at.isoformat() if item.archived_at else None,
            _json(item.metadata),
            item.revision,
        )

    @staticmethod
    def _task_values(item: Task) -> tuple[object, ...]:
        return (
            str(item.task_id),
            str(item.task_list_id),
            item.title,
            item.description,
            item.status.value,
            item.priority.value,
            item.due_at_utc.isoformat() if item.due_at_utc else None,
            item.completed_at.isoformat() if item.completed_at else None,
            item.cancelled_at.isoformat() if item.cancelled_at else None,
            int(item.is_archived),
            item.archived_at.isoformat() if item.archived_at else None,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
            str(item.source_command_id) if item.source_command_id else None,
            _json(item.metadata),
            item.revision,
        )

    def _note(self, row: sqlite3.Row) -> Note:
        return Note(
            row["title"],
            row["body"],
            UUID(row["note_id"]),
            bool(row["is_pinned"]),
            bool(row["is_archived"]),
            _timestamp(row["created_at"]) or datetime.now(UTC),
            _timestamp(row["updated_at"]) or datetime.now(UTC),
            _timestamp(row["archived_at"]),
            UUID(row["source_command_id"]) if row["source_command_id"] else None,
            json.loads(row["metadata_json"]),
            int(row["revision"]),
            self._tags("note_tags", "note_id", row["note_id"]),
        )

    @staticmethod
    def _task_list(row: sqlite3.Row) -> TaskList:
        return TaskList(
            row["name"],
            row["description"],
            UUID(row["task_list_id"]),
            bool(row["is_archived"]),
            _timestamp(row["created_at"]) or datetime.now(UTC),
            _timestamp(row["updated_at"]) or datetime.now(UTC),
            _timestamp(row["archived_at"]),
            json.loads(row["metadata_json"]),
            int(row["revision"]),
        )

    def _task(self, row: sqlite3.Row) -> Task:
        return Task(
            UUID(row["task_list_id"]),
            row["title"],
            row["description"],
            UUID(row["task_id"]),
            TaskStatus(row["status"]),
            TaskPriority(row["priority"]),
            _timestamp(row["due_at_utc"]),
            _timestamp(row["completed_at"]),
            _timestamp(row["cancelled_at"]),
            bool(row["is_archived"]),
            _timestamp(row["archived_at"]),
            _timestamp(row["created_at"]) or datetime.now(UTC),
            _timestamp(row["updated_at"]) or datetime.now(UTC),
            UUID(row["source_command_id"]) if row["source_command_id"] else None,
            json.loads(row["metadata_json"]),
            int(row["revision"]),
            self._tags("task_tags", "task_id", row["task_id"]),
        )


NoteRepository = ProductivityRepository
TaskListRepository = ProductivityRepository
TaskRepository = ProductivityRepository
TagRepository = ProductivityRepository
