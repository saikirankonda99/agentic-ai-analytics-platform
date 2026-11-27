# Render release proposal

The root `render.yaml` prepares a **new paid pilot stack**. It does not alter the existing `agentic-ai-analytics-platform` free service. Apply it only after reviewing the planned resources, recurring cost, selected Git revision, and private secret entry. This file's presence in Git does not provision hosting.

## Resources and cost

All resources use Oregon. The Blueprint groups them under a new `analytics-release` project and `pilot` environment. Resource names can receive Render-generated suffixes when the Blueprint is created with `existingResources=create_new`.

| Resource | Configuration | Published monthly baseline |
|---|---|---:|
| Customer/admin dashboard | Docker frontend, 0.5 CPU / 512 MB | $7.00 |
| Authenticated API | Docker backend, 0.5 CPU / 512 MB | $7.00 |
| Analytics worker | Continuous queue consumer, 0.5 CPU / 512 MB | $7.00 |
| PostgreSQL 16 | 0.1 CPU / 256 MB, 100 connections | $6.00 |
| Database storage | Explicit 1 GB | $0.30 |
| Retention job | Hourly at minute 17 UTC, 0.5 CPU / 512 MB | At least $1.00 |
| **Baseline total** | **Low-volume pilot** | **$28.30/month** |

Prices were checked against Render's [pricing](https://render.com/pricing.md), [compute plans](https://render.com/docs/compute-plans.md), and [cron billing](https://render.com/docs/cronjobs.md#compute-plans-and-billing) on November 27, 2026. Cron runtime is $0.00016/minute with a $1 monthly minimum. The estimate excludes OpenAI API usage, workspace-plan charges, taxes, and additional build/bandwidth/storage usage. A Hobby workspace has no base workspace subscription; this Blueprint does not request a workspace upgrade. Confirm the actual account quote before applying.

These are the smallest paid plans, chosen for an initial supervised pilot. They are not a capacity guarantee. Measure peak memory and latency with representative CSVs and concurrent users before accepting customer traffic. Database storage autoscaling is disabled so growth requires a reviewed change; monitor available space. This configuration has one database instance and no high-availability standby.

## Runtime wiring

- `DATABASE_URL` and `WORKFLOW_DATABASE_URL` reference the same private PostgreSQL connection string on all four processes. The database's public IP allow list is empty.
- The platform uses ordinary PostgreSQL for scoped query memory. `VECTOR_DATABASE_URL` is empty; optional pgvector is not enabled by this proposal.
- The dashboard executes its existing UI analysis in its own server process and shares durable storage with the API. The public API handles authenticated queued analytics; the worker consumes those jobs. The current UI does not consume `BACKEND_HTTP_URL` or `BACKEND_WS_URL`, so the Blueprint does not set ineffective host variables or claim cross-process live streaming.
- No customer database is granted automatically. `POSTGRES_URL` is empty, and `ANALYTICS_CONNECTORS_JSON` starts as `[]`. The bundled example database remains available. Add real customer connectors with scoped, read-only credentials after the release checks.
- The maintenance command exits after each sweep. It receives account configuration and database access but no model API key.
- The worker uses the tested durable leases and restart recovery. Abrupt termination can repeat a provider call that had not reached its result checkpoint; this is not exactly-once execution.

## Private credentials

The API service is the single initial source for `AUTH_USERS` and `OPENAI_API_KEY`. Both use `sync: false`. Enter their values privately in Render; do not place them in Git, chat, screenshots, issue bodies, or deployment logs. The dashboard and worker reference the API service's values with `fromService`. Maintenance references only `AUTH_USERS`.

For the user's Windows checkout, this PowerShell command prompts invisibly for two different passwords and prints the JSON account configuration containing hashes. Run it inside the project directory, with the project's installed virtual environment:

```powershell
.\.venv\Scripts\python.exe -c "import json; from getpass import getpass; from backend.auth_sessions import hash_password; print(json.dumps({'owner': {'password_hash': hash_password(getpass('Owner password: ')), 'display_name': 'Business Owner', 'team_id': 'pilot-business', 'role': 'admin'}, 'analyst': {'password_hash': hash_password(getpass('Analyst password: ')), 'display_name': 'Sales Analyst', 'team_id': 'pilot-business', 'role': 'analyst'}}))"
```

Use the resulting JSON as the private `AUTH_USERS` value. Choose the actual business's canonical `team_id` before onboarding its users; keep the passwords in the owner's password manager. The generated hashes are also private configuration. This command does not create OpenAI credentials.

Use the already-created project key for `OPENAI_API_KEY` in Render's private setup. The assistant does not need its plaintext. The current connector's approval arguments are not a private secret-entry surface, so complete secret entry in the Render Dashboard or through a private API process under the owner's control.

Render's `sync: false` prompt applies only during initial creation. If a Dashboard approval skips the values, production authentication intentionally fails until they are supplied. Set the source API service's secrets using **Save only**, then plan and approve a Blueprint sync to refresh the `fromService` references and deploy all consumers. Use the same resync procedure for later key or account rotations; editing the source value alone is not proof that every consumer has received it. See Render's [secret configuration](https://render.com/docs/configure-environment-variables.md) and [Blueprint reference](https://render.com/docs/blueprint-spec.md#prompting-for-secret-values).

## Review and rollout

1. Keep the existing free service running. Its observed deployment uses local SQLite. Do not assume that it contains only disposable demo data, and do not replace or delete that storage as part of this rollout. Preserve any required reports and database snapshots before a separately reviewed migration or retirement.
2. Create a Blueprint plan from the published release branch using `existingResources=create_new` and `autoSync=false`. Confirm the `agentic-ai-lab` workspace and inspect the plan. It should create the four application services, PostgreSQL database, and configuration group, with no changes to the old service.
3. Confirm the cost and authorize that exact plan. Enter the two secrets through the private Dashboard flow, following the propagation procedure above. A plan is a preview; it is not a deployed release.
4. All services have `autoDeployTrigger: off`, and preview environments are disabled. Review the source branch and deployed commit for every service. Initial creation uses the branch selected for the Blueprint. After acceptance and merge, update the service branches to `main` through a reviewed sync before enabling any automatic deployment.
5. Check API `/health` and `/ready`, dashboard `/_stcore/health`, account login/logout, a non-admin CSV/chart/export journey, and a bounded live AI review. Validate a real queued SQL answer and its provider usage. Record results on the tested commit.
6. Restart the application services and verify persisted reports and queued jobs survive. Observe worker and cron logs without exposing credentials. Confirm a successful retention run and the database provider's backup/PITR settings; run the documented restore drill into a fresh target.
7. Reconcile a representative business export against its trusted sales report, then decide whether to promote the new URL or perform a separate migration that preserves the original URL and required data.

No persistent application disk is needed because durable state lives in PostgreSQL. Raw uploads remain session-local. This proposal does not migrate historical SQLite data, perform live model validation, buy resources, or certify production capacity.

## Configuration verification

The Blueprint is validated locally against Render's current [JSON schema](https://render.com/schema/render.yaml.json). Provider-side planning must still verify account availability, secret references, resource names, and the selected branch before approval. Schema validation cannot prove a deployed service is healthy.
