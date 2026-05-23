# Collaboration Workflows

The collaboration layer is intentionally lightweight. It models personal and team workspaces without adding a heavy RBAC system.

## Workspace Scopes

Each signed-in user can work in two scopes:

| Scope | Workspace ID | Use |
|---|---|---|
| Personal | `{team_id}.{user_id}` | private analysis, drafts, personal bookmarks |
| Shared team | `{team_id}.shared` | team-visible reports, investigations, bookmarks, dashboard views |

The Streamlit sidebar exposes a workspace scope switch. Switching scope loads a separate persisted workspace document while keeping the same authenticated user and role.

## Shared Resources

Saved resources can carry visibility and ownership metadata:

- saved reports
- saved investigations
- query bookmarks
- pinned investigations
- dashboard/report views

Shared resource metadata includes:

- `visibility`: `private` or `team`
- `owner_id`
- `owner_name`
- `created_by`
- `created_by_name`
- `created_at`
- `updated_at`
- `workspace_scope`

## Activity History

Workspace memory stores two activity streams:

- `recent_activity`: general workspace actions such as saved SQL, completed workflows, exports, preferences, and onboarding updates.
- `collaboration_events`: team-sharing events such as shared reports, shared investigations, shared bookmarks, and shared dashboard views.

The History workspace renders both recent activity and recent collaboration so team-visible changes are easy to review.

## Permissions

The permissions model stays small:

| Role | Share | Edit Shared |
|---|---:|---:|
| admin | yes | yes |
| analyst | yes | no |
| viewer | no | no |

Owners can edit their own resources. Admins can edit shared resources. Viewers receive graceful warnings for share actions.

## Persistence

Collaboration data is stored inside the existing workspace memory document. This preserves compatibility with both SQLite and PostgreSQL because no new persistence tables are required.

## Demo Path

1. Start in the personal workspace and run a query.
2. Save a report view.
3. Share the report.
4. Switch to the shared team workspace.
5. Open History and show shared report metadata plus collaboration activity.
