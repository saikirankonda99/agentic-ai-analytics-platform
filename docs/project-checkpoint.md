# Project checkpoint — November 27, 2026

This checkpoint records the saved release work and the next steps when development resumes. The application is a release candidate; live AI and final hosted acceptance remain outstanding.

## Saved source

- Working branch: `release/end-to-end-readiness`.
- [Pull request #4](https://github.com/saikirankonda99/agentic-ai-analytics-platform/pull/4) is open and ready for review. It has not been merged into `main` as of this checkpoint.
- Last fully verified application revision: `2e141da8a6ce368fce02be23535d9e20ee7caec1`.
- Main branch at this checkpoint: `7a8145e6326077df1f71359601dbef5cbf36a516`.
- The checkpoint update changes documentation only; the verification below refers to the application revision above, not to a later documentation commit.

## Completed implementation

- Customer sales CSV mapping, exact totals, charts, downloads, and a separate administrator interface.
- Authenticated analytics API with authorized connectors, validated read-only SQL, durable queued jobs, persisted results, and real usage reporting when available.
- Workspace isolation, configuration-bound sessions, retention and deletion controls, retries, worker recovery, and backup/restore tooling.
- Production Docker Compose stack for the dashboard, API, continuous worker, maintenance process, and PostgreSQL.
- Automated application, browser, database, startup, container, and deployment checks.

See the [README](../README.md), [release-readiness checklist](release-readiness.md), and [actual API documentation](actual-api.md) for the implemented scope and its limits.

## Last completed verification

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

## Hosting checkpoint

- Google Cloud Compute Engine with the existing Docker Compose stack is the next pilot option to evaluate. Account eligibility, available credits, expiration, region, and the complete deployment estimate still need confirmation. No Google Cloud infrastructure has been provisioned in this work.
- The [Render proposal](render-release.md) and `render.yaml` remain available. Provider planning was blocked by a payment-information requirement; the proposed paid stack was not deployed.
- The existing Render demo was last observed running the older main revision with local SQLite. Preserve any required data before a future migration or retirement.
- Cloud-provider credits and the existing direct OpenAI API billing relationship must be budgeted separately. Startup-program eligibility is not established by this repository; verify current program requirements before applying.

## Resume in this order

1. Check out or update `release/end-to-end-readiness`, then inspect PR #4 and any newer CI results before editing.
2. Confirm the hosting account and any credits. Prepare and review the VM, disk, public IP, HTTPS, monitoring, and off-server backup configuration and costs before provisioning.
3. Provide the already-created OpenAI project key through a confirmed private runtime secret destination, along with explicit production account configuration. No key was available to the coding runtime during this release work, and no live OpenAI evaluation was performed. Keep credential values out of source, chat, screenshots, and logs.
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
