# Project checkpoint — November 27, 2026

This checkpoint records the saved release work and the next steps when development resumes. The application is a release candidate; live AI and final hosted acceptance remain outstanding.

## Saved source

- Working branch: `release/end-to-end-readiness`.
- [Pull request #4](https://github.com/saikirankonda99/agentic-ai-analytics-platform/pull/4) is open and ready for review. It has not been merged into `main` as of this checkpoint.
- Last fully verified release revision: `c27eca6929f3fdcc2c011a79ff67b401c1218540`.
- Main branch at this checkpoint: `7a8145e6326077df1f71359601dbef5cbf36a516`.
- The later interactive secret initializer has separate focused verification; a new helper commit does not itself establish hosted acceptance.

## Completed implementation

- Customer sales CSV mapping, exact totals, charts, downloads, and a separate administrator interface.
- Authenticated analytics API with authorized connectors, validated read-only SQL, durable queued jobs, persisted results, and real usage reporting when available.
- Workspace isolation, configuration-bound sessions, retention and deletion controls, retries, worker recovery, and backup/restore tooling.
- Production Docker Compose stack for the dashboard, API, continuous worker, maintenance process, and PostgreSQL.
- Automated application, browser, database, startup, container, and deployment checks.

See the [README](../README.md), [release-readiness checklist](release-readiness.md), and [actual API documentation](actual-api.md) for the implemented scope and its limits.

## Last completed verification

The latest full [GitHub Actions run 46056242516](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/runs/46056242516) completed successfully for `c27eca6929f3fdcc2c011a79ff67b401c1218540`. All seven jobs passed, including Docker stack smoke, PostgreSQL/pgvector, and Playwright. The interactive secret initializer adds 17 offline tests; all 40 GCP helper tests and the focused Ruff checks passed. No real credential or live model was used by these tests.

The earlier detailed application baseline remains useful evidence:

[GitHub Actions run 46020683709](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/runs/46020683709) completed successfully for revision `2e141da8a6ce368fce02be23535d9e20ee7caec1`. All seven jobs passed:

| Check | Result |
|---|---|
| Application tests | 378 passed, 22 skipped in this job |
| Lint | Passed |
| PostgreSQL and pgvector | 7 passed, zero skips |
| Startup validation | Passed |
| Playwright E2E | 14 passed; 1 live-provider test skipped |
| Docker build and stack smoke | Both images and the full stack passed |
| Deployment safety | Passed |

The general application job's 22 skips are browser and service tests handled in dedicated jobs. The live-provider browser case still requires a private API key. This CI evidence does not establish live model accuracy, hosted capacity, or customer impact.

The subsequent documentation checkpoint `1216f2df288e7a4889873effc5362a961b5b94e0` also passed [Platform CI run 46035073168](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/runs/46035073168). Google Cloud preparation adds 23 local tests for the runtime secret loader; these use synthetic responses and do not access a cloud account. Its focused tests, Ruff checks, documentation links, and Bash syntax checks passed. Check the pull request for CI evidence on any newer revision.

## Hosting checkpoint

- The Google Cloud pilot project is now linked to the verified billing account. Account-specific credit details were checked privately in the console and are not recorded in this repository.
- Initial infrastructure is provisioned in `us-central1-a`: an Ubuntu 24.04 `e2-medium` VM with a retained 50 GB balanced disk, a dedicated private network, an IAP-only SSH ingress rule, a reserved outbound IPv4 address, three empty Secret Manager resources with a dedicated runtime identity, and a private backup bucket. A project-scoped $40 monthly gross-cost budget alerts at 50%, 80%, and 100%; it is not a spending cap.
- The VM was observed running, but the application has not yet been started there. Private SSH login verification, private secret initialization, container installation, and hosted acceptance remain outstanding. The [runbook](google-cloud-pilot.md) and [cost proposal](google-cloud-costs.md) describe the intended setup; inspect existing resources before running creation commands again.
- The [Render proposal](render-release.md) and `render.yaml` remain available. Provider planning was blocked by a payment-information requirement; the proposed paid stack was not deployed.
- The existing Render demo was last observed running the older main revision with local SQLite. Preserve any required data before a future migration or retirement.
- Cloud-provider credits and the existing direct OpenAI API billing relationship must be budgeted separately. Startup-program eligibility is not established by this repository; verify current program requirements before applying.

## Resume in this order

1. Check out or update `release/end-to-end-readiness`, then inspect PR #4 and any newer CI results before editing.
2. Inspect the existing Google Cloud pilot resources and finish private SSH access and VM software installation. Reuse the provisioned resources instead of creating duplicates. Public HTTPS, monitoring, and off-server recovery still need acceptance evidence.
3. Privately initialize the three empty secrets with the existing OpenAI key and production account configuration. The interactive `scripts/gcp_seed_secrets.py` helper uses hidden terminal input and prints numeric version IDs only. No key was available to the coding runtime during this release work, and no live OpenAI evaluation was performed. Keep credential values out of source, chat, screenshots, and logs.
4. Deploy the reviewed revision and verify HTTPS, customer/admin login and logout, CSV analysis and exports, a real queued API result, and observed provider usage.
5. Verify a hosted restart, worker recovery, retention maintenance, and a backup/restore drill. Follow [operations and recovery](operations.md).
6. Reconcile a representative business sales export against its trusted report, then document actual pilot feedback and remaining issues.
7. Review the acceptance evidence before promoting the release and finalizing the ongoing hosting arrangement.

## Product boundaries to retain

- Raw CSV uploads are session-local; saved records and API results have separate durable storage.
- The dashboard performs its analysis in its own server process. It does not currently proxy its workflow through `BACKEND_HTTP_URL` or `BACKEND_WS_URL`.
- Durable API results are polled. The legacy simulation WebSocket is separate from real cross-process analytics.
- Automated accounting ingestion, automatic customer business actions, and self-service billing are outside this release.

Use [release readiness](release-readiness.md) as the acceptance checklist and [deployment](deployment.md) for runtime setup.
