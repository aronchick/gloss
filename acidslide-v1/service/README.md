# Gloss hosted service

This directory contains the hosted Gloss v1 submission API, controlled grading worker,
persistent leaderboard, and public website specified in §25 of the OpenSpec.

The trust boundary is explicit:

- the exact public label is `grading-verified artifact score; generation-attested` and its scope is
  artifact conformance only;
- generation method, human intervention, post-processing, and external-resource use remain
  submitter attestations in v1;
- the development test runner never starts in production;
- a deployment must not call scores verified until the worker, image digest, provenance hashes,
  DNS/TLS, and an end-to-end canary have all been checked live.

## Architecture

```text
Internet → Caddy/TLS → API → PostgreSQL ← quarantine dispatcher → disposable Stage 0/0.5
                           ↘ immutable objects       (no egress, signed verdict)
                              PostgreSQL ← grading worker → disposable resolved-package grader
```

The API performs only bounded opaque streaming, timeout, extension/magic-byte, digest, and immutable
object-storage checks. It never imports or calls ZIP/XML parsing code. A separate dispatcher claims
the reserved submission and launches a fresh Stage 0/0.5 container. That container performs the
quarantine checks, deterministic MCE preprocessing, XSD/root-map validation, writes the immutable
resolved package, and emits an RFC 8785 Ed25519-signed verdict binding both objects, all profile
hashes, submission/campaign/slot, key status, and a short-lived verdict ID whose database lifecycle
is `issued → leased(generation, worker, deadline) → consumed`.

Before parsing, the grading worker verifies signature, key validity/revocation, expiry, exact binding,
database CAS lease generation and replay status, resolved object path/version, digest, and size. It
receives only the resolved package and launches the canonical grader with:

- `--network none`, read-only root filesystem, non-root UID;
- all capabilities dropped and `no-new-privileges`;
- default Docker seccomp plus CPU, 2 GB memory, and PID limits;
- a 10-minute kill threshold;
- no shared job state and unconditional volume/container cleanup.

The worker records an append-only run containing the exact verification constants, server-issued
identity and campaign keys, reserved slot, three cohort component hashes, recomputed cohort ID,
environment data, UTC timestamps, complete private JSON report, and public report digest.
Ineligible reports occupy their slot at `0.0`; a failure before a report releases its reservation.

## API surface

- `POST /v1/models` and `POST /v1/models/{key}/revisions` — issue immutable identity keys
- `POST /v1/generation-profiles` — validate, JCS-hash, and register immutable generation settings
- `POST /v1/campaigns` and `GET /v1/campaigns/{id}` — precommit/read one three-slot variant
- `POST /v1/robustness-groups` and `GET /v1/robustness-groups/{id}` — atomic variant groups
- `POST /v1/submissions` — authenticated multipart submission, quarantine, and queueing
- `GET /v1/submissions/{id}` — authenticated status and result polling
- `GET /v1/submissions/{id}/report` — private JSON/HTML report unless permanently published
- `POST /v1/submissions/{id}/publish-report` — one-way public-report toggle
- `GET /v1/leaderboard?view=summary|detail` — public standard and human-assisted boards
- `GET /v1/leaderboard/runs` — append-only public completed-run ledger without aggregation loss
- `GET /v1/leaderboard/history` — public immutable snapshots
- `GET /v1/versions` — active and frozen benchmark versions
- `/v1/admin/*` — admin-key-protected organization/API-key and job controls
- `/health/live`, `/health/ready`, `/metrics` — operations endpoints

Interactive documentation is served at `/v1/docs`; the reviewed contract is
[`api-spec.yaml`](api-spec.yaml).

## Local development

Python 3.12–3.14 and `uv` are supported.

```bash
cd acidslide-v1/service
uv sync --extra dev
uv run alembic upgrade head
uv run acidslide-admin create-org "Local lab"
uv run uvicorn acidslide_service.main:app --reload
```

Set the returned key as `ACIDSLIDE_API_KEY`, register a model/revision and generation profile, then
precommit a campaign with its assistance class and profile digest. Create `submission.json` from the
returned campaign key:

```json
{
  "campaign_id": "server-issued-uuid",
  "generation_seed": null,
  "efficiency_metrics": {"generation_strategy": "direct"},
  "attestation": {
    "method": "Single API generation pass",
    "human_intervention": false,
    "post_processing": false,
    "external_resources_used": false
  }
}
```

Then submit a 5-slide Level 1 deck:

```bash
curl http://localhost:8000/v1/submissions \
  -H "Authorization: Bearer $ACIDSLIDE_API_KEY" \
  -F 'metadata=<submission.json;type=application/json' \
  -F 'file=@model-output.pptx;type=application/vnd.openxmlformats-officedocument.presentationml.presentation'
```

The normal workers require the canonical grader and quarantine images plus Docker. Deterministic
in-process/subprocess runners exist only for service integration tests and must be enabled with
`ACIDSLIDE_ALLOW_INSECURE_TEST_RUNNER=true` or
`ACIDSLIDE_ALLOW_INSECURE_QUARANTINE_RUNNER=true`; production settings reject either flag.

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy acidslide_service tests
uv run pytest --cov=acidslide_service --cov-report=term-missing --cov-fail-under=85
uv run pip-audit
docker compose config --quiet
docker build --build-context schemas=../schemas --target api -t acidslide/service-api:test .
docker build --build-context schemas=../schemas --target worker -t acidslide/service-worker:test .
docker build --platform linux/amd64 --provenance=false \
  --build-context schemas=../schemas --target quarantine-job \
  -t acidslide/quarantine:test .
```

The test suite covers authentication, immutable identity issuance, campaign/window/cohort binding,
slot reservation and release, zeroed ineligible reports, atomic robustness groups, append-only public
run rows, report access, webhook signing/SSRF, queue lifecycle, and worker isolation commands.

## Production deployment

The included Compose stack is intended for a dedicated Linux Docker host. The worker has Docker
socket access in order to create hardened sibling grading containers; treat that host as a
dedicated trust boundary, restrict SSH/operator access, and do not co-locate unrelated workloads.

1. Point `acidslide.dev` and `api.acidslide.dev` A/AAAA records at the host.
2. Build the canonical image from `acidslide-v1/Dockerfile` and tag it
   `acidslide/grader:1.0.0` and record its linux/amd64 manifest RepoDigest (not its config ID).
3. Build the disposable parser image with
   `docker build --platform linux/amd64 --provenance=false \
   --build-context schemas=acidslide-v1/schemas --target quarantine-job \
   -t acidslide/quarantine:1.0.0 acidslide-v1/service`, then
   push/record both exact manifest RepoDigests with `docker image inspect`.
4. Generate distinct Ed25519 quarantine and maintainer-control keys. Put the quarantine private key
   only in the quarantine-dispatcher environment, publish the purpose-scoped maintainer public key
   in `CONTROL_VERIFICATION_KEYS_JSON`, and never reuse either keyring for the other purpose. Pin
   every grader/prompt/assertion/checklist/quarantine/MCE/schema/canonical-package hash, all three
   gold-package digests, and the exact JCS-hashed environment-attestation payload.
5. Copy `.env.example` to `.env`, fill every secret/hash/build field, set mode `0600`, and set
   `DOCKER_GID` to the host Docker socket group ID.
6. Run `docker compose config --quiet`, then `docker compose up -d --build`. Readiness remains `503`
   until both grading and quarantine worker heartbeats are current and a current passing drift
   canary exists for the active scoring cohort. The quarantine worker refuses to start if its
   digest-pinned image or signing configuration is unavailable.
7. Create the first organization through the admin endpoint and store the returned API key once.
8. Run the three single-use, maintainer-signed gold controls with
   `docker compose exec api acidslide-admin run-drift-canary --authorization /run/control-tier-1.json --authorization /run/control-tier-2.json --authorization /run/control-tier-3.json`.
   Verify the command reports `status: pass`, readiness becomes healthy, and drift-canary metrics
   expose an unblocked current result. Schedule this same operator job weekly only after deployment.
9. Test quarantine, rate-limit, private-report, webhook signature, worker timeout, restart recovery,
   database backup/restore, and TLS/HSTS from outside the host.

Required backup targets are the PostgreSQL volume and private upload/artifact volume. Raw decks
and diff artifacts are private; operate a daily deletion job for artifacts older than 90 days.
Metrics are bearer-protected on the API and exposed only to the private network on the worker.

## Operational policy

- 10 submissions/hour/API key; one three-slot campaign per immutable revision/cohort/tier/variant
  in a server-issued seven-day window.
- 30 submissions/month on the default free quota; administrators may raise paid quotas.
- At most 5 active grading jobs per organization.
- Full reports are submitter-only; publication is one-way.
- Human-assisted submissions are always shown in a separate section.
- Suspended organizations receive `403`; appeals go to `appeals@acidslide.dev`.
- Score disputes go to `disputes@acidslide.dev` and target a 10-business-day response.
- Frozen benchmark versions remain queryable but reject new submissions.

## Current hosting status

The repository includes the isolated signed quarantine handoff, but no hosted deployment has been
verified. DNS, production credentials, digest-pinned canonical/quarantine images, release provenance,
current dispatcher/worker heartbeats, backup/restore evidence, and a live end-to-end canary remain
mandatory before this can be called a hosted verified leaderboard.
