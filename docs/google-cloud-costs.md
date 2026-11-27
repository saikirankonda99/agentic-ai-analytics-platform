# Google Cloud pilot cost proposal

Reviewed November 27, 2026. This is a planning estimate for the [private pilot runbook](google-cloud-pilot.md); it does not create cloud resources or confirm account credits.

## Proposed resources

One Ubuntu Compute Engine `e2-medium` VM in `us-central1-a` runs the existing Docker Compose stack. A dedicated VPC admits SSH only through Identity-Aware Proxy (IAP). The dashboard and API retain their loopback-only bindings. A public IPv4 address provides outbound internet access for package downloads and the existing OpenAI integration; it does not make the dashboard publicly accessible.

Use 50 GiB of zonal balanced Persistent Disk for the operating system, images, and PostgreSQL volume. Database records on this disk survive ordinary container and VM restarts, but this single-server arrangement still needs independent backups and a tested recovery procedure. A managed database and a public HTTPS endpoint are separate future design decisions.

## Illustrative base cost

USD list prices for Iowa (`us-central1`), Linux, on demand, assuming 730 running hours. No commitment, promotion, or account-wide free allowance is assumed.

| Resource | Unit price | Calculation | Estimated month |
|---|---|---|---:|
| `e2-medium` | $0.03350571/hour | 730 hours | $24.46 |
| 50 GiB `pd-balanced` | $0.000136986/GiB-hour | 50 x 730 | $5.00 |
| One in-use external IPv4 | $0.005/hour | 730 hours | $3.65 |
| **Base resources** | | | **$33.11** |

Sources: [VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose), [disk pricing](https://cloud.google.com/compute/disks-image-pricing), and [IPv4 pricing](https://cloud.google.com/vpc/network-pricing).

This is not a total-bill cap. It excludes backup storage and operations, transfer, chargeable logging/monitoring, additional services, taxes, and OpenAI API usage. Different regions, machine sizes, usage, or account terms change the estimate. Confirm the selected project's current quote before provisioning.

`e2-medium` has 4 GiB RAM and exposes two vCPUs, with shared CPU time equivalent to one sustained vCPU in total, plus temporary bursting. It is not a two-dedicated-core machine. This size is an initial pilot assumption; measure memory and sustained CPU with representative uploads and concurrent sessions before accepting customer traffic. See [E2 shared-core specifications](https://docs.cloud.google.com/compute/docs/general-purpose-machines#e2_shared-core).

## Other costs and credits

- **Backups:** regional Standard Cloud Storage in Iowa is approximately $0.02/GiB-month. An average 10 GiB retained footprint is about $0.20/month for storage alone. Operations, transfer, retained older versions, and soft-deleted data can add charges. Choose a retention policy and verify an off-server restore before relying on the pilot for business data. [Storage pricing](https://cloud.google.com/storage/pricing).
- **Secrets:** Secret Manager includes six active secret versions and 10,000 access operations per billing account per month in its free allowance. Three single-version secrets could fit, but usage elsewhere in the account is unknown. Above the allowance, current prices include $0.06 per active version/location/month and $0.03 per 10,000 accesses. [Secret Manager pricing](https://cloud.google.com/secret-manager/pricing).
- **Stopped resources:** stopping the VM does not remove disk charges. A static IP remains billable while associated with a stopped VM; a reserved, unattached static IPv4 has a higher $0.01/hour rate. Preserve data and review each resource when ending a pilot.
- **Credit coverage:** record the actual balance, expiry, applicable services, and billing-account/project association. A credit offer is not evidence that it has been activated. Existing direct OpenAI API usage has separate billing.

## Before creating resources

Confirm the project ID, billing/credit status, region, service account, and this resource estimate with the operator. Review the private pilot runbook, keep production credentials in the confirmed secret destination, and retain the existing Render deployment's required data. No account-specific approval or provisioning is recorded by this document.
