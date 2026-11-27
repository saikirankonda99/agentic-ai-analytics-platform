# Google Cloud private pilot

This is a reviewed-command proposal, not evidence of a deployed service. Confirm the target project, available credits, region, and full cost estimate before running creation commands. Preserve the existing Render service and its SQLite data. The first pilot is operator-only through an encrypted IAP SSH tunnel; public HTTPS and customer access remain separate release gates.

## Proposed resources

| Resource | Initial choice |
|---|---|
| Region / zone | `us-central1` / `us-central1-a`, subject to confirmation |
| VM | Ubuntu 24.04 LTS, `e2-medium`, 4 GB RAM, shared CPU |
| Boot/application disk | 50 GB `pd-balanced`, retained on VM deletion |
| Network | Dedicated VPC/subnet; SSH ingress only from Google's IAP range |
| External address | Reserved regional IPv4, attached to the VM for outbound internet access |
| Credentials | Three Secret Manager secrets; VM service account reads only those secrets |
| Backup destination | Private regional Cloud Storage bucket; operator-managed uploads initially |

Four GB is a sizing hypothesis. Measure memory, CPU, disk growth, and latency before accepting traffic. PostgreSQL shares the VM's failure risk. The named Docker volume survives a container restart but is not an off-server backup. The public IPv4 does not make application ports public: Compose binds 8000/8501 to loopback, and no web ingress rule is created.

The [cost proposal](google-cloud-costs.md) estimates **$33.11/month** for the VM, 50 GiB disk, and in-use IPv4 at 730 hours in Iowa, before variable usage and OpenAI charges. Credits and account eligibility remain unconfirmed. Review the itemized estimate and the project's current quote before creating resources.

## 1. Confirm the account and source

Use Google Cloud Shell for the following Bash commands. Review the signed-in account, project billing association, credit balance/expiration, and budget before proceeding. An alerts-only budget does not automatically cap spending. These commands use a dedicated project and assume an authorized operator can create the listed resources; do not apply them to an unrelated existing production project.

```bash
read -r -p 'Reviewed Google Cloud project ID: ' ANALYTICS_PROJECT
[[ "$ANALYTICS_PROJECT" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || exit 1
export ANALYTICS_PROJECT
export ANALYTICS_REGION=us-central1 ANALYTICS_ZONE=us-central1-a
export ANALYTICS_VM=analytics-pilot
export ANALYTICS_SA="analytics-pilot@${ANALYTICS_PROJECT}.iam.gserviceaccount.com"
export ANALYTICS_BACKUP_BUCKET="${ANALYTICS_PROJECT}-analytics-backups"
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud projects describe "$ANALYTICS_PROJECT" --format='table(projectId,name)'
gcloud billing projects describe "$ANALYTICS_PROJECT"
```

Select the exact reviewed 40-character Git commit containing this runbook and `scripts/gcp_runtime_env.py`. Use that same revision for all services; the old checkpoint SHA predates these Google Cloud files. Record the selected revision and approved resource estimate in the deployment record.

## 2. Create the isolated infrastructure after review

Commands create resources and can incur charges. Stop on any error; inspect an existing resource instead of deleting it to rerun this sequence.

```bash
set -euo pipefail
gcloud services enable compute.googleapis.com iap.googleapis.com oslogin.googleapis.com iam.googleapis.com secretmanager.googleapis.com storage.googleapis.com --project="$ANALYTICS_PROJECT"
gcloud iam service-accounts create analytics-pilot --display-name='Analytics pilot runtime' --project="$ANALYTICS_PROJECT"
gcloud compute networks create analytics-pilot --subnet-mode=custom --project="$ANALYTICS_PROJECT"
gcloud compute networks subnets create analytics-pilot --network=analytics-pilot --range=10.42.0.0/24 --region="$ANALYTICS_REGION" --project="$ANALYTICS_PROJECT"
gcloud compute firewall-rules create analytics-pilot-iap-ssh --network=analytics-pilot --direction=INGRESS --action=ALLOW --rules=tcp:22 --source-ranges=35.235.240.0/20 --target-service-accounts="$ANALYTICS_SA" --project="$ANALYTICS_PROJECT"
gcloud compute addresses create analytics-pilot --region="$ANALYTICS_REGION" --project="$ANALYTICS_PROJECT"
ANALYTICS_IP=$(gcloud compute addresses describe analytics-pilot --region="$ANALYTICS_REGION" --project="$ANALYTICS_PROJECT" --format='value(address)')
gcloud compute instances create "$ANALYTICS_VM" --project="$ANALYTICS_PROJECT" --zone="$ANALYTICS_ZONE" --machine-type=e2-medium --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud --boot-disk-size=50GB --boot-disk-type=pd-balanced --no-boot-disk-auto-delete --deletion-protection --network=analytics-pilot --subnet=analytics-pilot --address="$ANALYTICS_IP" --service-account="$ANALYTICS_SA" --scopes=cloud-platform --metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring
for ANALYTICS_SECRET in analytics-openai-key analytics-auth-users analytics-postgres-password; do
  gcloud secrets create "$ANALYTICS_SECRET" --replication-policy=user-managed --locations="$ANALYTICS_REGION" --project="$ANALYTICS_PROJECT"
  gcloud secrets add-iam-policy-binding "$ANALYTICS_SECRET" --member="serviceAccount:${ANALYTICS_SA}" --role=roles/secretmanager.secretAccessor --project="$ANALYTICS_PROJECT"
done
gcloud storage buckets create "gs://${ANALYTICS_BACKUP_BUCKET}" --location="$ANALYTICS_REGION" --uniform-bucket-level-access --public-access-prevention --project="$ANALYTICS_PROJECT"
```

No service-account key is created. The runtime has no project-wide Editor role and no backup-bucket permissions. An authorized operator handles initial backups. Do not add public SSH/web rules to work around authentication errors. Grant the named operator the required IAP tunnel and OS Login permissions, plus permission to act as the attached service account, using the [IAP](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding) and [OS Login](https://docs.cloud.google.com/compute/docs/oslogin/set-up-oslogin) guides; scope grants to the pilot resources wherever supported.

## 3. Add private secret versions

In the authenticated Google Cloud Console, open Secret Manager and add values privately to the three empty secrets. Do not put values in Git, command arguments, chat, screenshots, or VM metadata.

| Secret ID | Value |
|---|---|
| `analytics-openai-key` | The existing OpenAI project API key; do not create another merely for hosting |
| `analytics-auth-users` | JSON production accounts with password hashes, as described in [Accounts](deployment.md#accounts); use separate owner/admin and analyst passwords |
| `analytics-postgres-password` | A newly generated, strong URL-safe password for this new PostgreSQL instance |

Record the numeric version of each secret, not its value. Secret values must be a single line. The runtime helper requires explicit numeric versions so a new secret version cannot silently change the database password. Changing PostgreSQL's initialized password requires coordinated database and application rotation; replacing only its secret is insufficient.

## 4. Prepare the VM and pinned application

From Cloud Shell, connect with IAP:

```bash
gcloud compute ssh "$ANALYTICS_VM" --project="$ANALYTICS_PROJECT" --zone="$ANALYTICS_ZONE" --tunnel-through-iap
```

Inside the VM, install Git and Python 3 and install Docker Engine plus the Compose plugin using [Docker's Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository). Keep Docker administration restricted to trusted operators. Then:

```bash
sudo systemctl enable --now docker
sudo docker compose version
git clone --no-checkout https://github.com/saikirankonda99/agentic-ai-analytics-platform.git analytics-pilot
cd analytics-pilot
read -r -p 'Reviewed 40-character release commit: ' ANALYTICS_RELEASE_SHA
[[ "$ANALYTICS_RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit 1
git checkout --detach "$ANALYTICS_RELEASE_SHA"
git rev-parse HEAD
read -r -p 'Confirmed Google Cloud project ID: ' ANALYTICS_PROJECT
read -r -p 'OpenAI secret version number: ' ANALYTICS_OPENAI_VERSION
read -r -p 'Accounts secret version number: ' ANALYTICS_USERS_VERSION
read -r -p 'PostgreSQL secret version number: ' ANALYTICS_POSTGRES_VERSION
sudo python3 scripts/gcp_runtime_env.py --project "$ANALYTICS_PROJECT" --output .env --openai-version "$ANALYTICS_OPENAI_VERSION" --users-version "$ANALYTICS_USERS_VERSION" --postgres-version "$ANALYTICS_POSTGRES_VERSION"
sudo docker compose up --build --wait
sudo docker compose ps
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:8501/_stcore/health
```

The helper authenticates using the attached VM service account, validates all three values, and writes an owner-only `.env` excluded from Git and Docker build contexts. An existing file is refused unless an operator explicitly supplies `--replace`. The Docker daemon and trusted root administrators can access container environment values; Secret Manager does not hide values from the runtime that uses them. Do not print the file or run configuration-inspection commands that expand secrets. Failure to retrieve or validate secrets is a deployment failure, not a reason to enable development accounts.

Keep the same checkout and Compose project directory across restarts so Docker reuses its PostgreSQL volume. Application containers already have restart policies. After a VM reboot, confirm Docker, PostgreSQL, the API, worker, frontend, and maintenance process have recovered. Pin the tested revision in the deployment record before updating code.

## 5. Open the operator-only pilot

Exit the VM shell. From a trusted computer with gcloud installed and the authorized Google account, run this command after setting `ANALYTICS_PROJECT` and `ANALYTICS_ZONE`:

```bash
gcloud compute ssh analytics-pilot --project="$ANALYTICS_PROJECT" --zone="$ANALYTICS_ZONE" --tunnel-through-iap -- -N -L 127.0.0.1:8501:127.0.0.1:8501 -L 127.0.0.1:8000:127.0.0.1:8000
```

Open `http://127.0.0.1:8501` on that computer. The tunnel must stay open; closing it ends access. If the command runs in Cloud Shell, these loopback ports belong to Cloud Shell, not your laptop. Use Cloud Shell's authenticated Web Preview for port 8501 for operator testing, or run the tunnel locally. A blocked preview does not justify exposing 8501 publicly.

Verify non-admin login, CSV mapping, known totals, charts, exports, an explicit live AI review, and a real queued API query with observed usage. The dashboard's current analysis runs in its own process; API verification is a separate journey. Confirm logout and cross-workspace isolation. These checks can invoke paid OpenAI calls, billed separately from Google hosting.

## 6. Backups and public release gates

Before customer data is accepted, configure scheduled verified PostgreSQL backups and upload archives plus manifests into the private bucket, then restore into a separate empty database. The ordinary backend image does not contain PostgreSQL operator clients. Follow [operations and recovery](operations.md#create-and-verify-a-backup) using PostgreSQL 16 `pg_dump`/`pg_restore` in a trusted maintenance environment. This proposal creates a bucket; it does not install backup automation or establish a recovery drill. Apply an explicit object lifecycle/backup retention policy and account for Cloud Storage soft-delete retention.

If later adding an automated uploader, give its identity only the required bucket-level permissions, using unique archive names. Preserve recovery access for an authorized operator. The VM's attached identity currently reads secrets only.

Public release still needs a confirmed domain, HTTPS reverse proxy, reviewed web firewall rules, backup scheduling, resource/availability alerts, and hosted restart/recovery evidence. Keep application/database ports private behind the proxy. Reconcile one representative business export, then complete the [release-readiness checklist](release-readiness.md). No public domain or new cloud resource has been created by adding this runbook.

## Reference commands and assumptions

- [Compute Engine VM creation](https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create), including persistent boot disks, service accounts, and Shielded VM flags.
- [Google public Ubuntu image families](https://docs.cloud.google.com/compute/docs/images/os-details).
- [IAP tunnel access](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding) and [gcloud SSH forwarding](https://docs.cloud.google.com/sdk/gcloud/reference/compute/ssh).
- [Empty Secret Manager resources](https://docs.cloud.google.com/sdk/gcloud/reference/secrets/create).
- [Private Cloud Storage bucket creation](https://docs.cloud.google.com/sdk/gcloud/reference/storage/buckets/create).

Review current provider terms, account policies, regional availability, and the final monthly estimate at provisioning time. This plan has not been executed against a Google Cloud account.
