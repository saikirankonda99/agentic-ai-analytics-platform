"""Read-only analytics access with authorization before every database operation."""

from backend.connectors import get_connector_registry


def _connector(*, organization_id: str | None, workspace_id: str | None, connector_id: str):
    registry = get_connector_registry()
    if organization_id is None and workspace_id is None:
        return registry.get_public_demo(connector_id)
    if not organization_id or not workspace_id:
        raise PermissionError("Both organization and workspace are required for analytics access.")
    return registry.get_for_workspace(connector_id, organization_id=organization_id, workspace_id=workspace_id)


def run_query(sql, *, organization_id=None, workspace_id=None, connector_id="sqlite"):
    # Do not wrap this boundary in Streamlit's global cache: grants may change,
    # and cached rows must never bypass a current authorization check.
    return _connector(
        organization_id=organization_id, workspace_id=workspace_id, connector_id=connector_id,
    ).execute_read(sql)


def get_schema(*, organization_id=None, workspace_id=None, connector_id="sqlite"):
    return _connector(
        organization_id=organization_id, workspace_id=workspace_id, connector_id=connector_id,
    ).inspect_schema().get("schema_text", "")
