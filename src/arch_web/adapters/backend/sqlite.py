"""Bounded disposable application SQLite support for W07 evidence."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from arch_web.domain.backend import ApplicationMigrationPlan, AuthorizationRule

T = TypeVar("T")


class ApplicationSQLiteHarness:
    """Application-only store; never accepts the ARCH Runtime database path."""

    def __init__(self, application_path: Path, runtime_path: Path) -> None:
        if application_path.resolve() == runtime_path.resolve():
            raise ValueError("Application database must be separate from Runtime database")
        self.path = application_path
        self._connection = sqlite3.connect(application_path)
        self._connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> ApplicationSQLiteHarness:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def migrate(self, plan: ApplicationMigrationPlan) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS app_schema_migrations "
            "(migration_id TEXT PRIMARY KEY, checksum TEXT NOT NULL)"
        )
        applied = dict(
            self._connection.execute("SELECT migration_id, checksum FROM app_schema_migrations")
        )
        ordered, remaining, predecessor = [], {item.migration_id: item for item in plan.steps}, None
        while remaining:
            candidates = [item for item in remaining.values() if item.predecessor == predecessor]
            if len(candidates) != 1:
                raise ValueError("Migration chain is ambiguous or disconnected")
            step = candidates[0]
            ordered.append(step)
            predecessor = step.migration_id
            del remaining[step.migration_id]
        try:
            with self._connection:
                for step in ordered:
                    expected = "sha256:" + hashlib.sha256(step.statement.encode()).hexdigest()
                    if expected != step.checksum:
                        raise ValueError("Migration checksum mismatch")
                    if step.migration_id in applied:
                        if applied[step.migration_id] != step.checksum:
                            raise ValueError("Applied migration checksum mismatch")
                        continue
                    if step.destructive:
                        raise ValueError(
                            "Disposable evidence does not execute destructive migrations"
                        )
                    self._connection.execute(step.statement)
                    self._connection.execute(
                        "INSERT INTO app_schema_migrations VALUES (?, ?)",
                        (step.migration_id, step.checksum),
                    )
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise ValueError("Application migration failed") from exc

    def transaction(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        try:
            with self._connection:
                return operation(self._connection)
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise ValueError("Application transaction failed") from exc

    def insert_owned_item(self, item_id: str, owner_id: str, title: str) -> None:
        if not item_id or not owner_id or not title:
            raise ValueError("Server validation rejected the item")
        self.transaction(
            lambda connection: connection.execute(
                "INSERT INTO app_items (item_id, owner_id, title) VALUES (?, ?, ?)",
                (item_id, owner_id, title),
            )
        )

    def item_for_actor(
        self, item_id: str, actor_id: str, rule: AuthorizationRule
    ) -> tuple[str, str, str]:
        if not actor_id or not rule.default_deny:
            raise PermissionError("unauthorized")
        row = self._connection.execute(
            "SELECT item_id, owner_id, title FROM app_items WHERE item_id = ? AND owner_id = ?",
            (item_id, actor_id),
        ).fetchone()
        if row is None:
            raise PermissionError("unauthorized")
        return str(row[0]), str(row[1]), str(row[2])


class LocalIntegrationDouble:
    """No-network integration double with exact idempotency semantics."""

    def __init__(self) -> None:
        self._results: dict[str, tuple[str, str]] = {}

    def execute(self, key: str, request_fingerprint: str, action: Callable[[], str]) -> str:
        prior = self._results.get(key)
        if prior is not None:
            if prior[0] != request_fingerprint:
                raise ValueError("idempotency key conflict")
            return prior[1]
        result = action()
        self._results[key] = (request_fingerprint, result)
        return result


__all__ = ("ApplicationSQLiteHarness", "LocalIntegrationDouble")
