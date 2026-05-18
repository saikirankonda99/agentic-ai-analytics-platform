from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Protocol

from backend.config import settings
from backend.models import (
    DEFAULT_ORGANIZATION_ID,
    DEFAULT_USER_ID,
    DEFAULT_WORKSPACE_ID,
    AgentCoordinationTrace,
    AgentExecution,
    Organization,
    OrchestrationExecution,
    TokenUsage,
    UsageRecord,
    Workspace,
    WorkspaceMembership,
    WorkflowEvent,
    WorkflowStageProgress,
    WorkflowTelemetry,
)


DEFAULT_WORKFLOW_DB_PATH = Path(settings.sqlite_workflow_path)


class WorkflowStorage(Protocol):
    def save(self, workflow: OrchestrationExecution) -> None:
        """Persist workflow state."""

    def get(self, workflow_id: str) -> OrchestrationExecution | None:
        """Load workflow state by id."""


class AccountStorage(Protocol):
    def save_organization(self, organization: Organization) -> None:
        """Persist organization account metadata."""

    def save_workspace(self, workspace: Workspace) -> None:
        """Persist workspace account metadata."""

    def save_membership(self, membership: WorkspaceMembership) -> None:
        """Persist a user workspace membership."""

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        """Load workspace account metadata."""


class EventStorage(Protocol):
    def append(
        self,
        workflow_id: str,
        event: WorkflowEvent,
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        """Append an event to a workflow event stream."""

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[WorkflowEvent, ...]:
        """List events for a workflow."""


class TelemetryStorage(Protocol):
    def save(
        self,
        workflow_id: str,
        telemetry: WorkflowTelemetry,
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        """Persist workflow telemetry."""

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        """Load workflow telemetry by workflow id."""


class AgentExecutionStorage(Protocol):
    def save_all(
        self,
        workflow_id: str,
        agents: tuple[AgentExecution, ...],
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        """Persist agent execution metadata for a workflow."""

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[AgentExecution, ...]:
        """List agent execution metadata for a workflow."""


class AgentTraceStorage(Protocol):
    def save_all(
        self,
        workflow_id: str,
        traces: tuple[AgentCoordinationTrace, ...],
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        """Persist inter-agent coordination traces for a workflow."""

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[AgentCoordinationTrace, ...]:
        """List inter-agent coordination traces for a workflow."""


class UsageStorage(Protocol):
    def append(self, usage: UsageRecord) -> None:
        """Append a usage accounting event."""

    def list(
        self,
        *,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> tuple[UsageRecord, ...]:
        """List usage accounting events."""


class InMemoryAccountStorage:
    def __init__(self) -> None:
        self._organizations: dict[str, Organization] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._memberships: dict[tuple[str, str], WorkspaceMembership] = {}
        self._lock = RLock()

    def save_organization(self, organization: Organization) -> None:
        with self._lock:
            self._organizations[organization.organization_id] = organization

    def save_workspace(self, workspace: Workspace) -> None:
        with self._lock:
            self._workspaces[workspace.workspace_id] = workspace

    def save_membership(self, membership: WorkspaceMembership) -> None:
        with self._lock:
            self._memberships[(membership.user_id, membership.workspace_id)] = membership

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self._lock:
            return self._workspaces.get(workspace_id)


class InMemoryUsageStorage:
    def __init__(self) -> None:
        self._usage: list[UsageRecord] = []
        self._lock = RLock()

    def append(self, usage: UsageRecord) -> None:
        with self._lock:
            self._usage.append(usage)

    def list(
        self,
        *,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> tuple[UsageRecord, ...]:
        with self._lock:
            return tuple(
                usage
                for usage in self._usage
                if (organization_id is None or usage.organization_id == organization_id)
                and (workspace_id is None or usage.workspace_id == workspace_id)
            )


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

    def append(
        self,
        workflow_id: str,
        event: WorkflowEvent,
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock:
            self._events[workflow_id] = (*self._events.get(workflow_id, ()), event)

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[WorkflowEvent, ...]:
        with self._lock:
            return self._events.get(workflow_id, ())


class InMemoryTelemetryStorage:
    def __init__(self) -> None:
        self._telemetry: dict[str, WorkflowTelemetry] = {}
        self._lock = RLock()

    def save(
        self,
        workflow_id: str,
        telemetry: WorkflowTelemetry,
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock:
            self._telemetry[workflow_id] = telemetry

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        with self._lock:
            return self._telemetry.get(workflow_id)


class InMemoryAgentExecutionStorage:
    def __init__(self) -> None:
        self._agents: dict[str, tuple[AgentExecution, ...]] = {}
        self._lock = RLock()

    def save_all(
        self,
        workflow_id: str,
        agents: tuple[AgentExecution, ...],
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock:
            self._agents[workflow_id] = agents

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[AgentExecution, ...]:
        with self._lock:
            return self._agents.get(workflow_id, ())


class InMemoryAgentTraceStorage:
    def __init__(self) -> None:
        self._traces: dict[str, tuple[AgentCoordinationTrace, ...]] = {}
        self._lock = RLock()

    def save_all(
        self,
        workflow_id: str,
        traces: tuple[AgentCoordinationTrace, ...],
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock:
            self._traces[workflow_id] = traces

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[AgentCoordinationTrace, ...]:
        with self._lock:
            return self._traces.get(workflow_id, ())


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
                    organization_id TEXT NOT NULL DEFAULT 'organization:default',
                    workspace_id TEXT NOT NULL DEFAULT 'workspace:default',
                    user_id TEXT NOT NULL DEFAULT 'user:anonymous',
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
                    organization_id TEXT NOT NULL DEFAULT 'organization:default',
                    workspace_id TEXT NOT NULL DEFAULT 'workspace:default',
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_events_workflow_id
                    ON workflow_events(workflow_id, id);

                CREATE TABLE IF NOT EXISTS workflow_telemetry (
                    workflow_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT 'organization:default',
                    workspace_id TEXT NOT NULL DEFAULT 'workspace:default',
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
                    organization_id TEXT NOT NULL DEFAULT 'organization:default',
                    workspace_id TEXT NOT NULL DEFAULT 'workspace:default',
                    agent_name TEXT NOT NULL,
                    agent_role TEXT NOT NULL,
                    assigned_stage TEXT NOT NULL,
                    agent_status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_agents_workflow_id
                    ON workflow_agents(workflow_id, id);

                CREATE TABLE IF NOT EXISTS workflow_agent_traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL DEFAULT 'organization:default',
                    workspace_id TEXT NOT NULL DEFAULT 'workspace:default',
                    timestamp TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    handoff_reason TEXT NOT NULL,
                    context_summary TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_agent_traces_workflow_id
                    ON workflow_agent_traces(workflow_id, id);

                CREATE TABLE IF NOT EXISTS organizations (
                    organization_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    plan TEXT NOT NULL DEFAULT 'free',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workspace_memberships (
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    roles_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, workspace_id)
                );

                CREATE TABLE IF NOT EXISTS usage_records (
                    usage_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_usage_records_tenant
                    ON usage_records(organization_id, workspace_id, timestamp);
                """
            )
            self._ensure_column(
                connection,
                "workflows",
                "organization_id",
                "TEXT NOT NULL DEFAULT 'organization:default'",
            )
            self._ensure_column(connection, "workflows", "workspace_id", "TEXT NOT NULL DEFAULT 'workspace:default'")
            self._ensure_column(connection, "workflows", "user_id", "TEXT NOT NULL DEFAULT 'user:anonymous'")
            for table_name in (
                "workflow_events",
                "workflow_telemetry",
                "workflow_agents",
                "workflow_agent_traces",
            ):
                self._ensure_column(
                    connection,
                    table_name,
                    "organization_id",
                    "TEXT NOT NULL DEFAULT 'organization:default'",
                )
                self._ensure_column(
                    connection,
                    table_name,
                    "workspace_id",
                    "TEXT NOT NULL DEFAULT 'workspace:default'",
                )

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


class SQLiteWorkflowStorage(SQLiteStore):
    def save(self, workflow: OrchestrationExecution) -> None:
        stage_progression = json.dumps([asdict(stage) for stage in workflow.stage_progression])
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflows (
                    workflow_id, organization_id, workspace_id, user_id, question, status, created_at,
                    current_stage, stage_progression_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    organization_id = excluded.organization_id,
                    workspace_id = excluded.workspace_id,
                    user_id = excluded.user_id,
                    question = excluded.question,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    current_stage = excluded.current_stage,
                    stage_progression_json = excluded.stage_progression_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    workflow.workflow_id,
                    workflow.organization_id,
                    workflow.workspace_id,
                    workflow.user_id,
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
            organization_id=row["organization_id"] or DEFAULT_ORGANIZATION_ID,
            workspace_id=row["workspace_id"] or DEFAULT_WORKSPACE_ID,
            user_id=row["user_id"] or DEFAULT_USER_ID,
            question=row["question"],
            status=row["status"],
            created_at=row["created_at"],
            current_stage=row["current_stage"],
            stage_progression=stage_progression,
            telemetry=WorkflowTelemetry(),
            agent_executions=(),
        )


class SQLiteEventStorage(SQLiteStore):
    def append(
        self,
        workflow_id: str,
        event: WorkflowEvent,
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_events (
                    workflow_id, organization_id, workspace_id, timestamp, event_type, message
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (workflow_id, organization_id, workspace_id, event.timestamp, event.event_type, event.message),
            )

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[WorkflowEvent, ...]:
        query = """
            SELECT timestamp, event_type, message
            FROM workflow_events
            WHERE workflow_id = ?
        """
        params: tuple[str, ...] = (workflow_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params = (workflow_id, workspace_id)
        query += " ORDER BY id ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(WorkflowEvent(**dict(row)) for row in rows)


class SQLiteTelemetryStorage(SQLiteStore):
    def save(
        self,
        workflow_id: str,
        telemetry: WorkflowTelemetry,
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_telemetry (
                    workflow_id, organization_id, workspace_id, started_at, completed_at, latency_ms, estimated_cost_usd,
                    prompt_tokens, completion_tokens, total_tokens
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    organization_id = excluded.organization_id,
                    workspace_id = excluded.workspace_id,
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
                    organization_id,
                    workspace_id,
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
    def save_all(
        self,
        workflow_id: str,
        agents: tuple[AgentExecution, ...],
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM workflow_agents WHERE workflow_id = ?", (workflow_id,))
            connection.executemany(
                """
                INSERT INTO workflow_agents (
                    workflow_id, organization_id, workspace_id, agent_name, agent_role, assigned_stage, agent_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        workflow_id,
                        organization_id,
                        workspace_id,
                        agent.agent_name,
                        agent.agent_role,
                        agent.assigned_stage,
                        agent.agent_status,
                    )
                    for agent in agents
                ],
            )

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[AgentExecution, ...]:
        query = """
            SELECT agent_name, agent_role, assigned_stage, agent_status
            FROM workflow_agents
            WHERE workflow_id = ?
        """
        params: tuple[str, ...] = (workflow_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params = (workflow_id, workspace_id)
        query += " ORDER BY id ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(AgentExecution(**dict(row)) for row in rows)


class SQLiteAgentTraceStorage(SQLiteStore):
    def save_all(
        self,
        workflow_id: str,
        traces: tuple[AgentCoordinationTrace, ...],
        *,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM workflow_agent_traces WHERE workflow_id = ?", (workflow_id,))
            connection.executemany(
                """
                INSERT INTO workflow_agent_traces (
                    workflow_id, organization_id, workspace_id, timestamp, source_agent, target_agent,
                    handoff_reason, context_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        workflow_id,
                        organization_id,
                        workspace_id,
                        trace.timestamp,
                        trace.source_agent,
                        trace.target_agent,
                        trace.handoff_reason,
                        trace.context_summary,
                    )
                    for trace in traces
                ],
            )

    def list(self, workflow_id: str, *, workspace_id: str | None = None) -> tuple[AgentCoordinationTrace, ...]:
        query = """
            SELECT timestamp, source_agent, target_agent, handoff_reason, context_summary
            FROM workflow_agent_traces
            WHERE workflow_id = ?
        """
        params: tuple[str, ...] = (workflow_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params = (workflow_id, workspace_id)
        query += " ORDER BY id ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(AgentCoordinationTrace(**dict(row)) for row in rows)


class SQLiteAccountStorage(SQLiteStore):
    def save_organization(self, organization: Organization) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO organizations (organization_id, name, plan)
                VALUES (?, ?, ?)
                ON CONFLICT(organization_id) DO UPDATE SET
                    name = excluded.name,
                    plan = excluded.plan,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (organization.organization_id, organization.name, organization.plan),
            )

    def save_workspace(self, workspace: Workspace) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (workspace_id, organization_id, name)
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    organization_id = excluded.organization_id,
                    name = excluded.name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (workspace.workspace_id, workspace.organization_id, workspace.name),
            )

    def save_membership(self, membership: WorkspaceMembership) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_memberships (user_id, workspace_id, organization_id, roles_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, workspace_id) DO UPDATE SET
                    organization_id = excluded.organization_id,
                    roles_json = excluded.roles_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    membership.user_id,
                    membership.workspace_id,
                    membership.organization_id,
                    json.dumps(list(membership.roles)),
                ),
            )

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT workspace_id, organization_id, name FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return Workspace(
            workspace_id=row["workspace_id"],
            organization_id=row["organization_id"],
            name=row["name"],
        )


class SQLiteUsageStorage(SQLiteStore):
    def append(self, usage: UsageRecord) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_records (
                    usage_id, organization_id, workspace_id, user_id, event_type, quantity,
                    estimated_cost_usd, timestamp, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage.usage_id,
                    usage.organization_id,
                    usage.workspace_id,
                    usage.user_id,
                    usage.event_type,
                    usage.quantity,
                    usage.estimated_cost_usd,
                    usage.timestamp,
                    json.dumps(usage.metadata),
                ),
            )

    def list(
        self,
        *,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> tuple[UsageRecord, ...]:
        query = "SELECT * FROM usage_records WHERE 1 = 1"
        params: list[str] = []
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        query += " ORDER BY timestamp ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(
            UsageRecord(
                usage_id=row["usage_id"],
                organization_id=row["organization_id"],
                workspace_id=row["workspace_id"],
                user_id=row["user_id"],
                event_type=row["event_type"],
                quantity=row["quantity"],
                estimated_cost_usd=row["estimated_cost_usd"],
                timestamp=row["timestamp"],
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in rows
        )


__all__ = [
    "AccountStorage",
    "AgentTraceStorage",
    "AgentExecutionStorage",
    "DEFAULT_WORKFLOW_DB_PATH",
    "EventStorage",
    "InMemoryAccountStorage",
    "InMemoryAgentExecutionStorage",
    "InMemoryAgentTraceStorage",
    "InMemoryEventStorage",
    "InMemoryTelemetryStorage",
    "InMemoryUsageStorage",
    "InMemoryWorkflowStorage",
    "SQLiteAccountStorage",
    "SQLiteAgentExecutionStorage",
    "SQLiteAgentTraceStorage",
    "SQLiteEventStorage",
    "SQLiteTelemetryStorage",
    "SQLiteUsageStorage",
    "SQLiteWorkflowStorage",
    "TelemetryStorage",
    "UsageStorage",
    "WorkflowStorage",
]
