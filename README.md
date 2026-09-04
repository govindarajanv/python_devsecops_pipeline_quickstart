# Python DevSecOps Pipeline Quickstart

A fullstack Python CRUD application for **appointment booking with a physician**,
hardened and shipped through a complete **DevSecOps CI/CD pipeline** using
**GitHub Actions**, with GitOps deployment to **Minikube** via **Argo CD**.

The application is a FastAPI + vanilla JS frontend backed by **Redis**
(containerized) for persistence — intentionally simple, so the security pipeline
is the star of the show.

---

## Table of Contents

- [Architecture](#architecture)
- [Application](#application)
- [DevSecOps Pipeline](#devsecops-pipeline)
- [Getting Started](#getting-started)
- [GitOps Deployment (Argo CD + Minikube)](#gitops-deployment-argo-cd--minikube)
- [Pipeline Secrets & Variables](#pipeline-secrets--variables)
- [Project Layout](#project-layout)
- [Security Best Practices Applied](#security-best-practices-applied)
- [Future Hardening](#future-hardening)

---

## Architecture

```
┌──────────────┐    ┌────────────────────┐    ┌──────────────┐
│   GitHub     │    │   GitHub Actions   │    │  GitHub      │
│   Repo       │──▶│   DevSecOps CI/CD   │──▶│  Container   │
│ (source of   │    │                    │    │  Registry    │
│  truth)      │    └────────────────────┘    │  (GHCR)      │
└──────┬───────┘                               └──────┬───────┘
       │ GitOps (Argo CD Application)                 │ image pull
       ▼                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Minikube Cluster                         │
│  ┌──────────────┐  ArgoCD (pull)  ┌──────────────────────────┐  │
│  │    Argo CD   │◀───────────────│ appointment-service Helm  │  │
│  └──────────────┘                 │  Chart                    │  │
│                                   │  ├── FastAPI Deployment   │  │
│                                   │  ├── Redis Deployment     │  │
│                                   │  ├── Service / Ingress    │  │
│                                   │  └── NetworkPolicy, HPA   │  │
│                                   └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

The **application image** is produced by the pipeline and pushed to GHCR; the
**Helm chart** (in the same repo) is the GitOps source of truth that Argo CD
continuously reconciles against the cluster.

---

## Application

A fullstack CRUD app that books physician appointments:

| Method | Endpoint                     | Description                    |
|--------|------------------------------|--------------------------------|
| GET    | `/`                          | HTML frontend                  |
| GET    | `/health`                    | Liveness probe                 |
| GET    | `/ready`                     | Readiness probe (Redis ping)   |
| GET    | `/api/appointments`          | List appointments              |
| POST   | `/api/appointments`          | Create appointment             |
| GET    | `/api/appointments/{id}`     | Get appointment                |
| PUT    | `/api/appointments/{id}`     | Update appointment             |
| DELETE | `/api/appointments/{id}`     | Delete appointment             |

Appointment fields: `patient_name`, `physician`, `appointment_date`,
`time_slot`, `reason`, `status` (`scheduled|completed|cancelled`).

Run it locally:

```bash
# Docker compose (app + Redis)
docker compose up --build
# -> http://localhost:8000

# Or with Python directly
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# start Redis first, then:
uvicorn app.main:app --reload
```

---

## DevSecOps Pipeline

GitHub Actions workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

| Stage | Tool(s) | What it does |
|-------|---------|--------------|
| **Secret Scan** | Gitleaks | Detects secrets in the commit history; custom rules for this app |
| **Pre-commit** | pre-commit-hooks, ruff, bandit, gitleaks, pip-audit | Lint, format, YAML/JSON validation, private-key detection |
| **Unit Tests** | pytest + pytest-cov | 12 tests, coverage.xml artifact |
| **SAST** | SonarCloud | Static code analysis + quality gate (coverage consumed from tests job) |
| **SCA** | pip-audit (GitHub Action + pre-commit hook) | Known-vulnerability scan of Python dependencies |
| **SBOM** | Syft (anchore/sbom-action) | CycloneDX SBOM generated & uploaded as artifact |
| **License Check** | pip-licenses + policy script | Enforces an approved-license allowlist |
| **IaC Scan** | Helm lint + Trivy `config` | Validates & renders the chart; Trivy misconfiguration scan (SARIF to code scanning) |
| **Image Build + Scan** | Docker Buildx + Trivy `image` | Multi-stage non-root image; Trivy vuln scan (fails on CRITICAL/HIGH) |
| **Security Gate** | aggregated job | Blocks merge unless every security check is green |

Continuous SCA is also automated via **Dependabot** (pip, GitHub Actions, Docker).

The pipeline runs on every **push to `main`** and every **pull request**;
`main` should be configured as a protected branch with the individual jobs and
`security-gate` as required status checks.

---

## Getting Started

### 1. Configure the repository

1. Push this project to a GitHub repository.
2. Configure the secrets/variables listed in [Pipeline Secrets & Variables](#pipeline-secrets--variables).
3. On **SonarCloud**, create a project and set the values in
   [`sonar-project.properties`](sonar-project.properties)
   (`sonar.organization` / `sonar.projectKey`).
4. Replace `YOUR_GITHUB_USERNAME` in:
   - `helm/appointment-service/values.yaml`
   - `helm/appointment-service/values-dev.yaml`
   - `gitops/argo-application.yaml`
5. Protect `main` and require the `security-gate` status check.

### 2. Local development workflow

```bash
make setup          # create venv + install dev deps
make test           # run unit tests
make lint           # ruff lint + format check
make security       # bandit + pip-audit
make sbom           # generate CycloneDX SBOM
make licenses       # license report + policy
make secrets        # gitleaks scan
make helm-lint      # helm lint + template
make precommit      # install pre-commit hooks
```

---

## GitOps Deployment (Argo CD + Minikube)

The GitOps manifests live in [`gitops/`](gitops/) and the Helm chart in
[`helm/appointment-service/`](helm/appointment-service/).

### Argo CD side (pull-based, the canonical model)

```bash
# 1. Start Minikube
minikube start --cpus 4 --memory 8192

# 2. Install Argo CD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 3. Get the admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 4. Add this GitHub repo as an Argo CD Repository (Settings -> Repositories)

# 5. Register the Application (GitOps source of truth)
kubectl apply -f gitops/argo-application.yaml

# 6. Watch it reconcile the helm chart into the 'appointment' namespace
kubectl get app -n argocd
argocd app list
```

### GitHub Actions side (continuous delivery)

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml):

1. **promote-image** — bumps the image tag in
   `helm/appointment-service/values-dev.yaml` (GitOps source of truth) and
   commits it back to `main`.
2. **argocd-sync** — logs into Argo CD and triggers `app sync` + health wait so
   the rollout to Minikube happens immediately (enabled via
   `ARGOCD_SYNC_ENABLED` repository variable).

> Argo CD's `automated` sync policy (`prune`, `selfHeal`) means it would also
> converge on the new tag by itself — the workflow just makes it immediate.

---

## Pipeline Secrets & Variables

Configure these in **Settings → Secrets and variables → Actions**:

| Name | Required | Description |
|------|----------|-------------|
| `SONAR_TOKEN` | Yes (SAST) | SonarCloud token |
| `GITLEAKS_LICENSE` | Optional | Gitleaks enterprise license (free tier doesn't need it) |
| `ARGOCD_SERVER` | Deploy | e.g. `https://argocd.example.com` (or Minikube NodePort URL) |
| `ARGOCD_USERNAME` | Deploy | Argo CD user (e.g. `admin`) |
| `ARGOCD_PASSWORD` | Deploy | Argo CD password |

| Name | Type | Description |
|------|------|-------------|
| `ARGOCD_SYNC_ENABLED` | Variable | set to `true` to enable the `argocd-sync` job |

---

## Project Layout

```
.
├── app/                        # FastAPI application
│   ├── main.py                 # API + frontend mount
│   ├── database.py             # Redis persistence layer
│   └── schemas.py              # Pydantic models
├── frontend/                   # Vanilla JS single-page CRUD UI
├── tests/                      # pytest integration tests
├── scripts/
│   └── license_check.py        # License policy enforcer
├── helm/
│   └── appointment-service/    # Helm chart (app + redis)
├── gitops/
│   └── argo-application.yaml   # Argo CD Application (GitOps)
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # DevSecOps pipeline
│   │   └── deploy.yml          # GitOps CD to Argo CD / Minikube
│   └── dependabot.yml          # Continuous SCA automation
├── Dockerfile                  # Multi-stage, non-root, distroless-ish slim
├── docker-compose.yml          # Local dev (app + redis)
├── .pre-commit-config.yaml     # Pre-commit hooks
├── .gitleaks.toml              # Gitleaks config + custom rules
├── sonar-project.properties    # SonarCloud config
├── pyproject.toml              # ruff / bandit / pytest config
└── Makefile                    # Local dev shortcuts
```

---

## Security Best Practices Applied

- **Multi-stage Docker build** — build deps stripped from the runtime image.
- **Non-root runtime** (`appuser`), read-only root FS, all capabilities dropped.
- **Kubernetes hardening** — `securityContext` (runAsNonRoot, seccomp
  `RuntimeDefault`, drop ALL), `NetworkPolicy`, `automountServiceAccountToken:
  false`, resource limits, liveness/readiness probes, HPA.
- **Secrets never committed** — Redis password injected via Kubernetes `Secret`;
  Gitleaks scans commit history; `.env` ignored.
- **Shift-left gates** — pre-commit, SCA and license checks run locally too
  (`make security`, `make licenses`).
- **SBOM + SARIF artifacts** uploaded to the Actions run; SARIF surfaces in
  GitHub code scanning.
- **Protected main** — `security-gate` aggregates all checks as a single
  merge-blocking status check.
- **Pin everything** — exact dependency versions, action tags, and Helm chart
  references for reproducible, auditable builds.
- **Dependabot** keeps dependencies and actions patched continuously.

---

## Future Hardening

- Wire the SBOM upload to **Dependency-Track** or **DefectDojo** for drift-aware
  vulnerability tracking.
- Replace the Helm-generated Redis secret with **External Secrets / SOPS +
  Age** or **Vault**.
- Add **cosign signing + verification** of container images and the SBOM.
- Add **KICS / checkov** alongside Trivy for IaC scanning.
- Enforce **Pod Security Standards (baseline/restricted)** via namespace labels.
- Add **SAST for the JS frontend** (e.g. Semgrep) and `npm audit` if the
  frontend gains a build step.
- Add runtime security (Falco) and continuous cluster scanning (Trivy Operator).
