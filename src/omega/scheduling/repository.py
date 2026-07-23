"""SQLite persistence and atomic schedule-occurrence delivery claims."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID, uuid4

from omega.core.exceptions import DatabaseError, ModelValidationError
from omega.database.connection import DatabaseConnectionFactory
from omega.scheduling.models import (
    ClaimedOccurrence,
    DeliveryStatus,
    RecurrenceRule,
    ScheduledItem,
    ScheduleStatus,
    ScheduleType,
)
from omega.scheduling.recurrence import next_future_occurrence

_ACTIVE_STATUSES = (
    ScheduleStatus.PENDING,
    ScheduleStatus.SNOOZED,
    ScheduleStatus.PAUSED,
)


class ScheduleRepository:
    """Open short-lived connections and never initialize schema implicitly."""

    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    @staticmethod
    def _text(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ModelValidationError("Persisted schedule timestamps must be aware.")
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _recurrence(item: ScheduledItem) -> str | None:
        return json.dumps(item.recurrence.to_dict()) if item.recurrence else None

    def add(self, item: ScheduledItem) -> ScheduledItem:
        connection = self.factory.connect()
        try:
            connection.execute(
                "INSERT INTO scheduled_items VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                self._values(item),
            )
            connection.commit()
            return item
        except sqlite3.Error as error:
            connection.rollback()
            raise DatabaseError("Schedule could not be stored.") from error
        finally:
            connection.close()

    def get(self, schedule_id: UUID) -> ScheduledItem | None:
        connection = self.factory.connect()
        try:
            row = connection.execute(
                "SELECT * FROM scheduled_items WHERE schedule_id=?",
                (str(schedule_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError("Schedule could not be read.") from error
        finally:
            connection.close()
        return self._item(row) if row else None

    def list_items(
        self,
        *,
        schedule_type: ScheduleType | None = None,
        include_terminal: bool = False,
        limit: int = 50,
    ) -> tuple[ScheduledItem, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")
        clauses: list[str] = []
        parameters: list[object] = []
        if not include_terminal:
            clauses.append("status IN ('pending','snoozed','paused')")
        if schedule_type is not None:
            clauses.append("schedule_type=?")
            parameters.append(schedule_type.value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        parameters.append(limit)
        connection = self.factory.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM scheduled_items"
                + where
                + " ORDER BY due_at_utc,schedule_id LIMIT ?",
                tuple(parameters),
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError("Schedules could not be listed.") from error
        finally:
            connection.close()
        return tuple(self._item(row) for row in rows)

    def list_upcoming(self, limit: int = 50) -> tuple[ScheduledItem, ...]:
        """Compatibility wrapper for bounded active-item listing."""

        return self.list_items(limit=limit)

    def active_count(self) -> int:
        connection = self.factory.connect()
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM scheduled_items "
                "WHERE status IN ('pending','snoozed','paused')"
            ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error as error:
            raise DatabaseError("Active schedules could not be counted.") from error
        finally:
            connection.close()

    def update(self, item: ScheduledItem, expected_revision: int) -> ScheduledItem:
        connection = self.factory.connect()
        try:
            changed = self._update_row(connection, item, expected_revision)
            if changed != 1:
                raise DatabaseError("Schedule revision conflict.")
            connection.commit()
            return item
        except sqlite3.Error as error:
            connection.rollback()
            raise DatabaseError("Schedule update failed.") from error
        finally:
            connection.close()

    def claim_due(
        self,
        now: datetime,
        limit: int = 50,
    ) -> tuple[ClaimedOccurrence, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("claim limit must be between 1 and 200.")
        stamp = self._text(now)
        connection = self.factory.connect()
        claimed: list[ClaimedOccurrence] = []
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM scheduled_items "
                "WHERE status IN ('pending','snoozed') AND due_at_utc<=? "
                "ORDER BY due_at_utc,schedule_id LIMIT ?",
                (stamp, limit),
            ).fetchall()
            for row in rows:
                delivery_id = uuid4()
                try:
                    connection.execute(
                        "INSERT INTO schedule_deliveries VALUES "
                        "(?,?,?,?,NULL,'claimed',1,NULL,?,?)",
                        (
                            str(delivery_id),
                            row["schedule_id"],
                            row["due_at_utc"],
                            stamp,
                            stamp,
                            stamp,
                        ),
                    )
                except sqlite3.IntegrityError:
                    continue
                item = self._item(row)
                claimed.append(ClaimedOccurrence(delivery_id, item, item.due_at_utc))
            connection.commit()
            return tuple(claimed)
        except sqlite3.Error as error:
            connection.rollback()
            raise DatabaseError("Due schedules could not be claimed.") from error
        finally:
            connection.close()

    def finalize_claim(
        self,
        claim: ClaimedOccurrence,
        now: datetime,
        delivery_status: DeliveryStatus,
        *,
        next_due: datetime | None,
        occurrence_count: int,
        error_code: str | None = None,
    ) -> bool:
        """Finalize one exact occurrence and its schedule in one transaction."""

        if delivery_status is DeliveryStatus.CLAIMED:
            raise ValueError("A claim requires a terminal delivery status.")
        stamp = self._text(now)
        item = claim.item
        old_revision = item.revision
        item.updated_at = now.astimezone(UTC)
        item.occurrence_count = occurrence_count
        item.revision += 1
        item.snoozed_until_utc = None
        item.remaining_seconds = None
        if next_due is not None:
            item.due_at_utc = next_due.astimezone(UTC)
            item.status = ScheduleStatus.PENDING
            item.completed_at = None
        else:
            item.completed_at = now.astimezone(UTC)
            item.status = (
                ScheduleStatus.COMPLETED
                if delivery_status is DeliveryStatus.DELIVERED
                else ScheduleStatus.MISSED
            )
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            delivery_changed = connection.execute(
                "UPDATE schedule_deliveries SET delivery_status=?,"
                "delivered_at=?,error_code=?,updated_at=? "
                "WHERE delivery_id=? AND delivery_status='claimed'",
                (
                    delivery_status.value,
                    stamp if delivery_status is DeliveryStatus.DELIVERED else None,
                    error_code,
                    stamp,
                    str(claim.delivery_id),
                ),
            ).rowcount
            if delivery_changed != 1:
                connection.rollback()
                return False
            if self._update_row(connection, item, old_revision) != 1:
                raise DatabaseError("Schedule changed while delivery was pending.")
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover_stale_claims(
        self,
        now: datetime,
        *,
        timeout_seconds: int,
        limit: int,
    ) -> int:
        """Mark abandoned claims missed without ever replaying their notification."""

        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive.")
        cutoff = now.astimezone(UTC).timestamp() - timeout_seconds
        cutoff_text = datetime.fromtimestamp(cutoff, UTC).isoformat()
        connection = self.factory.connect()
        recovered = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT d.*,s.* FROM schedule_deliveries d "
                "JOIN scheduled_items s ON s.schedule_id=d.schedule_id "
                "WHERE d.delivery_status='claimed' AND d.claimed_at<=? "
                "ORDER BY d.claimed_at,d.delivery_id LIMIT ?",
                (cutoff_text, limit),
            ).fetchall()
            stamp = self._text(now)
            for row in rows:
                item = self._item(row)
                occurrence = datetime.fromisoformat(row["occurrence_at_utc"])
                next_due, count = (
                    next_future_occurrence(
                        occurrence,
                        item.recurrence,
                        item.occurrence_count,
                        now,
                        item.timezone_name,
                    )
                    if item.recurrence
                    else (None, item.occurrence_count + 1)
                )
                item.updated_at = now.astimezone(UTC)
                item.occurrence_count = count
                item.revision += 1
                item.snoozed_until_utc = None
                if next_due is None:
                    item.status = ScheduleStatus.MISSED
                    item.completed_at = now.astimezone(UTC)
                else:
                    item.status = ScheduleStatus.PENDING
                    item.due_at_utc = next_due
                changed = connection.execute(
                    "UPDATE schedule_deliveries SET delivery_status='missed',"
                    "error_code='STALE_CLAIM',updated_at=? "
                    "WHERE delivery_id=? AND delivery_status='claimed'",
                    (stamp, row["delivery_id"]),
                ).rowcount
                if changed and self._update_row(connection, item, item.revision - 1):
                    recovered += 1
            connection.commit()
            return recovered
        except Exception as error:
            connection.rollback()
            if isinstance(error, DatabaseError):
                raise
            raise DatabaseError(
                "Stale schedule claims could not be recovered."
            ) from error
        finally:
            connection.close()

    def delivery_status(
        self,
        schedule_id: UUID,
        occurrence_at_utc: datetime,
    ) -> DeliveryStatus | None:
        connection = self.factory.connect()
        try:
            row = connection.execute(
                "SELECT delivery_status FROM schedule_deliveries "
                "WHERE schedule_id=? AND occurrence_at_utc=?",
                (str(schedule_id), self._text(occurrence_at_utc)),
            ).fetchone()
            return DeliveryStatus(row[0]) if row else None
        finally:
            connection.close()

    @classmethod
    def _update_row(
        cls,
        connection: sqlite3.Connection,
        item: ScheduledItem,
        expected_revision: int,
    ) -> int:
        return connection.execute(
            """UPDATE scheduled_items SET
               title=?,message=?,status=?,due_at_utc=?,recurrence_json=?,
               updated_at=?,completed_at=?,cancelled_at=?,snoozed_until_utc=?,
               remaining_seconds=?,occurrence_count=?,revision=?,metadata_json=?
               WHERE schedule_id=? AND revision=?""",
            (
                item.title,
                item.message,
                item.status.value,
                cls._text(item.due_at_utc),
                cls._recurrence(item),
                cls._text(item.updated_at),
                cls._text(item.completed_at),
                cls._text(item.cancelled_at),
                cls._text(item.snoozed_until_utc),
                item.remaining_seconds,
                item.occurrence_count,
                item.revision,
                json.dumps(item.metadata),
                str(item.schedule_id),
                expected_revision,
            ),
        ).rowcount

    @classmethod
    def _values(cls, item: ScheduledItem) -> tuple[object, ...]:
        return (
            str(item.schedule_id),
            item.schedule_type.value,
            item.title,
            item.message,
            item.status.value,
            cls._text(item.due_at_utc),
            item.timezone_name,
            cls._recurrence(item),
            cls._text(item.created_at),
            cls._text(item.updated_at),
            cls._text(item.completed_at),
            cls._text(item.cancelled_at),
            cls._text(item.snoozed_until_utc),
            item.remaining_seconds,
            item.occurrence_count,
            item.revision,
            json.dumps(item.metadata),
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> ScheduledItem:
        recurrence_data = (
            json.loads(row["recurrence_json"]) if row["recurrence_json"] else None
        )

        def parse(value: str | None) -> datetime | None:
            if value is None:
                return None
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise DatabaseError(
                    "Stored schedule timestamps are not timezone-aware."
                )
            return parsed.astimezone(UTC)

        due = parse(row["due_at_utc"])
        created = parse(row["created_at"])
        updated = parse(row["updated_at"])
        if due is None or created is None or updated is None:
            raise DatabaseError("Stored schedule timestamps are malformed.")
        try:
            metadata = json.loads(row["metadata_json"])
            return ScheduledItem(
                ScheduleType(row["schedule_type"]),
                row["title"],
                row["message"],
                due,
                row["timezone_name"],
                UUID(row["schedule_id"]),
                ScheduleStatus(row["status"]),
                RecurrenceRule.from_dict(recurrence_data) if recurrence_data else None,
                created,
                updated,
                parse(row["completed_at"]),
                parse(row["cancelled_at"]),
                parse(row["snoozed_until_utc"]),
                row["remaining_seconds"],
                row["occurrence_count"],
                row["revision"],
                metadata,
            )
        except (KeyError, TypeError, ValueError, ModelValidationError) as error:
            raise DatabaseError("Stored schedule data is malformed.") from error
