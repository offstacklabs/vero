# Commercial Open-Source (COSS) Architecture & Repository Management

This document defines the architectural strategy for splitting and maintaining **Vero Open-Source (OSS)** and **Vero Enterprise Edition (EE)** using **Pattern 2: The Extension Package Model** (as adopted by Supabase, HashiCorp, Airbyte, and Temporal).

---

## 1. Architectural Strategy: The Extension Package Model

In this model, the **public repository is the standalone, unpolluted foundation**, and the **private commercial repository is an extension package** that imports the open-source core as a dependency.

```
┌────────────────────────────────────────────────────────┐
│      PUBLIC OSS REPO: github.com/offstacklabs/vero     │
│          (Apache 2.0 / Free Community Edition)         │
│                                                        │
│  • Published to PyPI as: `pip install vero`           │
│  • Published to NPM as: `npm install @verodata/react`  │
│  • Published to Docker as: `docker pull verodata/vero` │
│                                                        │
│  Core Capabilities (Free Forever):                    │
│  • Natural Language to SQL Agent with Reflexion Loop   │
│  • Multi-Warehouse Connectors (BigQuery, Snowflake,    │
│    PostgreSQL, DuckDB, SQLite)                         │
│  • AST Read-Only Sandbox & Pre-Execution Safety Checks │
│  • Native BigQuery Dry-Run ($0 Cost Estimation)        │
│  • Semantic AST Cache Engine (0ms, $0 Compute)         │
│  • Universal Semantic Importer (LookML, dbt, Cube,     │
│    Apache Ossie)                                       │
│  • React Studio Web Workspace                          │
│  • Embedded React SDK (`<VeroChat />`)                 │
└───────────────────────────┬────────────────────────────┘
                            │
              pip install vero (Dependency)
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ PRIVATE COMMERCIAL REPO:                               │
│ github.com/offstacklabs/vero-enterprise                │
│       (Proprietary / Paid Commercial Edition)          │
│                                                        │
│  • Published to Private PyPI: `pip install vero-ee`    │
│  • Published to Private Docker: `verodata/vero-ee`     │
│                                                        │
│  Enterprise-Only Extensions (Paid License):            │
│  • Corporate OIDC SSO (Okta, Azure AD, OneLogin)       │
│  • Dynamic IdP Group Mapping to Roles & Domains        │
│  • Multi-Tenant Business Domain Partitioning           │
│  • Column-Level Automated PII Redaction & Governance   │
│  • Automated Root Cause Analysis (RCA) Deviation Engine│
│  • Enterprise Audit Logs & Signed Telemetry Export     │
└────────────────────────────────────────────────────────┘
```

---

## 2. Code Extension Points (How EE Extends OSS)

The open-source core exposes clean extension hooks so the enterprise package never needs to fork or monkey-patch the codebase:

### 1. Application Wrapping (`vero.server.app`)
The enterprise repository wraps the FastAPI instance and mounts its proprietary routers:

```python
# In private repo: vero_ee/server.py
from vero.server import app as base_app
from vero_ee.oidc import oidc_router
from vero_ee.diagnostics import rca_router

# Mount enterprise endpoints directly onto the open-source base
base_app.include_router(oidc_router, prefix="/api/auth/oidc", tags=["Enterprise SSO"])
base_app.include_router(rca_router, prefix="/api/diagnostics", tags=["Enterprise RCA"])

app = base_app
```

### 2. Authentication Provider Hook
In OSS mode, `AuthManager` operates with zero-friction local developer access. In Enterprise mode, `vero_ee.auth.EnterpriseAuthManager` intercepts session creation and validates tokens against Okta or Azure Active Directory.

### 3. Data Governance Sanitizer Hook
The OSS `DatabaseManager` allows registering an optional post-execution sanitizer callback. In Enterprise mode, `vero_ee.governance.DataGovernanceEngine` registers its regex pattern-matching engine to sanitize sensitive rows before results leave the warehouse.

---

## 3. How to Keep Repositories in Sync

### The Version Pinning Rule
The private enterprise repository pins the core OSS version in its `pyproject.toml`:

```toml
# In vero-ee/pyproject.toml
[project]
name = "vero-ee"
version = "0.1.0"
dependencies = [
    "vero>=0.1.0,<0.2.0",
]

[project.scripts]
vero-ee = "vero_ee.cli:app"
```

### Automated Dependabot & Integration CI
1. When a new release of `vero` is published to PyPI (e.g. `v0.1.1`), GitHub's Dependabot automatically opens a PR in the private `vero-ee` repository:
   `chore(deps): bump vero from 0.1.0 to 0.1.1`
2. The private CI runs the full enterprise test suite against the new core release.
3. Once tests pass, the private package is released as `vero-ee v0.1.1`.

### Local Development Workflow
When engineering features that cross both boundaries, developers use editable pip installs:
```bash
# In local development:
git clone https://github.com/offstacklabs/vero.git
git clone https://github.com/offstacklabs/vero-enterprise.git

cd vero-enterprise
pip install -e ../vero/vero-cli
pip install -e .
```
Any edit made to the OSS core reflects instantly inside the enterprise runtime without publishing intermediate packages.

---

## 4. Release & Distribution Pipeline

| Artifact | Public OSS Pipeline | Private Enterprise Pipeline |
| :--- | :--- | :--- |
| **Python Package** | Public PyPI (`vero`) | Private PyPI (`vero-ee`) |
| **Docker Image** | Docker Hub (`verodata/vero:latest`) | AWS ECR / Private GHCR (`verodata/vero-ee:latest`) |
| **React Studio** | Bundled in `vero` Python package | Bundled with enterprise plugins |
| **React SDK** | Public NPM (`@verodata/react`) | Public NPM (SDK connects to either backend) |
| **License** | Apache 2.0 / MIT | Proprietary Commercial License |

---

## 5. Summary of Advantages

1. **Zero Contamination**: The public open-source repository contains 0% proprietary enterprise code, maximizing community adoption, trust, and stars.
2. **No "Paywall Nagware"**: OSS users never see disabled features or paywall nags, preserving a pure open-source experience.
3. **Decoupled Release Cadence**: You can patch an enterprise customer's Okta issue in `vero-ee` without triggering a public open-source release.
4. **Clean Enterprise Distribution**: Enterprise customers simply run `docker pull ghcr.io/verodata/vero-ee:latest` with their customer license key.
