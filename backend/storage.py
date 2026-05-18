from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Protocol

from backend.models import (
    AgentExecution,
    OrchestrationExecution,
    TokenUsage,
    WorkflowEvent,
    WorkflowStageProgress,
    WorkflowTelemetry,
)


DEFAULT_WORKFLOW_DB_PATH = Path("data") / "workflow_runtime.db"


class WorkflowStorage(Protocol):
    def save(self, workflow: OrchestrationExecution) -> None:
        """Persist workflow state."""

    def get(self, workflow_id: str) -> OrchestrationExecution | None:
        """Load workflow state by id."""


class EventStorage(Protocol):
    def append(self, workflow_id: str, event: WorkflowEvent) -> None:
        """Append an event to a workflow event stream."""

    def list(self, workflow_id: str) -> tuple[WorkflowEvent, ...]:
        """List events for a workflow."""


class TelemetryStorage(Protocol):
    def save(self, workflow_id: str, telemetry: WorkflowTelemetry) -> None:
        """Persist workflow telemetry."""

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        """Load workflow telemetry by workflow id."""


class AgentExecutionStorage(Protocol):
    def save_all(self, workflow_id: str, agents: tuple[AgentExecution, ...]) -> None:
        """Persist agent execution metadata for a workflow."""

    def list(self, workflow_id: str) -> tuple[AgentExecution, ...]:
        """List agent execution metadata for a workflow."""


class InMemoryWorkflowStorage:
    def __init__(self) -> None:
        self._workflows: dict[str, OrchestrationExecution] = {}
        self._latest_workflow_id: str | None = None
        self._lock = RLock()

    def save(self, workflow: OrchestrationExecution) -> None:
        with self._lock:
            self._workflows[workflow.workflow_id] = workflow
            self._latest_workflow_id = workflow.workflow_id

    def get(self, workflow_id: str) -> OrchestrationExecution | None:
        with self._lock:
            if workflow_id == "workflow:latest" and self._latest_workflow_id is not None:
                return self._workflows.get(self._latest_workflow_id)
            return self._workflows.get(workflow_id)


class InMemoryEventStorage:
    def __init__(self) -> None:
        self._events: dict[str, tuple[WorkflowEvent, ...]] = {}
        self._lock = RLock()

    def append(self, workflow_id: str, event: WorkflowEvent) -> None:
        with self._lock:
            self._events[workflow_id] = (*self._events.get(workflow_id, ()), event)

    def list(self, workflow_id: str) -> tuple[WorkflowEvent, ...]:
        with self._lock:
            return self._events.get(workflow_id, ())


class InMemoryTelemetryStorage:
    def __init__(self) -> None:
        self._telemetry: dict[str, WorkflowTelemetry] = {}
        self._lock = RLock()

    def save(self, workflow_id: str, telemetry: WorkflowTelemetry) -> None:
        with self._lock:
            self._telemetry[workflow_id] = telemetry

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        with self._lock:
            return self._telemetry.get(workflow_id)


class InMemoryAgentExecutionStorage:
    def __init__(self) -> None:
        self._agents: dict[str, tuple[AgentExecution, ...]] = {}
        self._lock = RLock()

    def save_all(self, workflow_id: str, agents: tuple[AgentExecution, ...]) -> None:
        with self._lock:
            self._agents[workflow_id] = agents

    def list(self, workflow_id: str) -> tuple[AgentExecution, ...]:
        with self._lock:
            return self._agents.get(workflow_id, ())


class SQLiteStore:
    def __init__(self, db_path: str | Path = DEFAULT_WORKFLOW_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    current_stage TEXT,
                    stage_progression_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflow_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_events_workflow_id
                    ON workflow_events(workflow_id, id);

                CREATE TABLE IF NOT EXISTS workflow_telemetry (
                    workflow_id TEXT PRIMARY KEY,
                    started_at TEXT,
                    completed_at TEXT,
                    latency_ms INTEGER,
                    estimated_cost_usd REAL NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    agent_role TEXT NOT NULL,
                    assigned_stage TEXT NOT NULL,
                    agent_status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_agents_workflow_id
                    ON workflow_agents(workflow_id, id);
                """
            )


class SQLiteWorkflowStorage(SQLiteStore):
    def save(self, workflow: OrchestrationExecution) -> None:
        stage_progression = json.dumps([asdict(stage) for stage in workflow.stage_progression])
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflows (
                    workflow_id, question, status, created_at, current_stage, stage_progression_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    question = excluded.question,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    current_stage = excluded.current_stage,
                    stage_progression_json = excluded.stage_progression_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    workflow.workflow_id,
                    workflow.question,
                    workflow.status,
                    workflow.created_at,
                    workflow.current_stage,
                    stage_progression,
                ),
            )

    def get(self, workflow_id: str) -> OrchestrationExecution | None:
        query = "SELECT * FROM workflows WHERE workflow_id = ?"
        params = (workflow_id,)
        if workflow_id == "workflow:latest":
            query = "SELECT * FROM workflows ORDER BY updated_at DESC LIMIT 1"
            params = ()

        with self._lock, self._connect() as connection:
            row = connection.execute(query, params).fetchone()

        if row is None:
            return None

        stage_progression = tuple(
            WorkflowStageProgress(**stage)
            for stage in json.loads(row["stage_progression_json"] or "[]")
        )
        return OrchestrationExecution(
            workflow_id=row["workflow_id"],
            question=row["question"],
            status=row["status"],
            created_at=row["created_at"],
            current_stage=row["current_stage"],
            stage_progression=stage_progression,
            telemetry=WorkflowTelemetry(),
            agent_executions=(),
        )


class SQLiteEventStorage(SQLiteStore):
    def append(self, workflow_id: str, event: WorkflowEvent) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_events (workflow_id, timestamp, event_type, message)
                VALUES (?, ?, ?, ?)
                """,
                (workflow_id, event.timestamp, event.event_type, event.message),
            )

    def list(self, workflow_id: str) -> tuple[WorkflowEvent, ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, event_type, message
                FROM workflow_events
                WHERE workflow_id = ?
                ORDER BY id ASC
                """,
                (workflow_id,),
            ).fetchall()
        return tuple(WorkflowEvent(**dict(row)) for row in rows)


class SQLiteTelemetryStorage(SQLiteStore):
    def save(self, workflow_id: str, telemetry: WorkflowTelemetry) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_telemetry (
                    workflow_id, started_at, completed_at, latency_ms, estimated_cost_usd,
                    prompt_tokens, completion_tokens, total_tokens
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    latency_ms = excluded.latency_ms,
                    estimated_cost_usd = excluded.estimated_cost_usd,
                    prompt_tokens = excluded.prompt_tokens,
                    completion_tokens = excluded.completion_tokens,
                    total_tokens = excluded.total_tokens
                """,
                (
                    workflow_id,
                    telemetry.started_at,
                    telemetry.completed_at,
                    telemetry.latency_ms,
                    telemetry.estimated_cost_usd,
                    telemetry.token_usage.prompt_tokens,
                    telemetry.token_usage.completion_tokens,
                    telemetry.token_usage.total_tokens,
                ),
            )

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_telemetry WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowTelemetry(
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            latency_ms=row["latency_ms"],
            estimated_cost_usd=row["estimated_cost_usd"],
            token_usage=TokenUsage(
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
            ),
        )


class SQLiteAgentExecutionStorage(SQLiteStore):
    def save_all(self, workflow_id: str, agents: tuple[AgentExecution, ...]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM workflow_agents WHERE workflow_id = ?", (workflow_id,))
            connection.executemany(
                """
                INSERT INTO workflow_agents (
                    workflow_id, agent_name, agent_role, assigned_stage, agent_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        workflow_id,
                        agent.agent_name,
                        agent.agent_role,
                        agent.assigned_stage,
                        agent.agent_status,
                    )
                    for agent in agents
                ],
            )

    def list(self, workflow_id: str) -> tuple[AgentExecution, ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT agent_name, agent_role, assigned_stage, agent_status
                FROM workflow_agents
                WHERE workflow_id = ?
                ORDER BY id ASC
                """,
                (workflow_id,),
            ).fetchall()
        return tuple(AgentExecution(**dict(row)) for row in rows)


__all__ = [
    "AgentExecutionStorage",
    "DEFAULT_WORKFLOW_DB_PATH",
    "EventStorage",
    "InMemoryAgentExecutionStorage",
    "InMemoryEventStorage",
    "InMemoryTelemetryStorage",
    "InMemoryWorkflowStorage",
    "SQLiteAgentExecutionStorage",
    "SQLiteEventStorage",
    "SQLiteTelemetryStorage",
    "SQLiteWorkflowStorage",
    "TelemetryStorage",
    "WorkflowStorage",
]
