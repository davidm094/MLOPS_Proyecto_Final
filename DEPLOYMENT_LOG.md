# Deployment Log - MLOps Platform

## Session: 2025-11-23

### Initial Setup (VM Rocky Linux)
**Timestamp:** 13:10 PM

#### Actions Taken:
1. Executed `setup_host.sh` on Rocky Linux VM (10.43.100.94)
   - Disabled firewalld
   - Set SELinux to permissive
   - Installed iSCSI and NFS utilities
   - Installed K3s v1.33.5+k3s1 with custom CIDRs:
     - Pod CIDR: 10.44.0.0/16
     - Service CIDR: 10.45.0.0/16
     - DNS IP: 10.45.0.10
   - Disabled servicelb and traefik

2. Attempted Argo CD bootstrap
   - **Issue:** Network connectivity blocked access to `raw.githubusercontent.com`
   - **Solution:** Downloaded `install.yaml` locally to `infra/argocd/install/install.yaml`

#### Challenges Encountered:
- **Image Pull Failures:** MinIO and PostgreSQL images failed to pull
  - MinIO: Changed Docker Hub policy
  - **Solution:** Replaced MinIO with SeaweedFS (S3-compatible alternative)
  - PostgreSQL: Forced use of `postgres:13-alpine` image

- **MetalLB Issues:**
  - v0.13.x: Missing `memberlist` secret, webhook certificate errors
  - **Solution:** Downgraded to v0.12.1 (ConfigMap-based)
  - Removed deprecated `PodSecurityPolicy` definitions
  - Added `metallb-system` namespace to manifest

- **NodePort Access Issues:**
  - Argo CD service patched to NodePort (30443)
  - Port not accessible externally despite firewalld being stopped
  - `ss -tulpn` showed no listener on NodePort
  - **Root Cause:** kube-proxy not binding NodePort to external interface

### Migration to WSL (Local Development)
**Timestamp:** 20:30 PM

#### Decision Rationale:
- VM network restrictions too limiting (no control over firewall/routing)
- Local deployment provides full control
- Faster iteration and debugging

#### Architecture Changes:
1. **Cluster:** K3d (K3s in Docker) instead of bare-metal K3s
2. **Networking:** NodePort services mapped by K3d to localhost
3. **Ingress:** Removed custom Traefik, using K3d's built-in Traefik
4. **DNS:** Eliminated need for nip.io or custom DNS

### Session: 2025-11-24

#### Phase 6: Helm Compatibility Fixes
- Applied upstream requirements for Airflow Helm chart when using Argo CD:
  - Disabled Helm hooks for `createUserJob` and `migrateDatabaseJob`
  - Added `argocd.argoproj.io/hook: Sync` annotation so migrations run during every sync
- Updated MLflow Helm values to use structured `artifactRoot.s3` block
- Cleaned Airflow `env` section to match chart expectations (array of name/value pairs)

#### Phase 7: NodePort Exposure Strategy
- Chart v1.10.0 no permite fijar `nodePort` dentro de `webserver.service`
- Se movió la responsabilidad del NodePort a un manifiesto independiente
- El chart vuelve a crear un Service `ClusterIP` estándar

#### Phase 8: Airflow PostgreSQL Image Override
- El subchart `postgresql` de Airflow intentaba descargar `bitnami/postgresql` (ImagePullBackOff)
- Se forzó al subchart a usar `docker.io/library/postgres:13-alpine`

#### Phase 9: Service Selector Fixes
- El servicio NodePort de Airflow no encontraba endpoints
- Causa: Selectors incorrectos vs Labels reales del chart legacy
- Solución: Se corrigió el manifiesto del servicio para usar los labels correctos

#### Phase 10: Image Update & Sync Policy
- **Issue:** Airflow pods stuck on `apache/airflow:2.6.2` despite manual updates
- **Cause:** Argo CD "Self-Heal" reverted manual changes
- **Fix:** Updated `core-apps.yaml` to explicitly define custom image with `pullPolicy: Always`

---

## Session: 2025-11-25

### Phase 11: DAG Execution & Data Pipeline Testing
**Timestamp:** 03:00 UTC

#### Issue: DAG Tasks Failing Silently
- Worker pods created by KubernetesExecutor were deleted immediately after completion
- Logs not accessible via Airflow UI ("Could not read served logs")
- **Root Cause:** Ephemeral pods + no remote logging configured

#### Fixes Applied:
1. Added `AIRFLOW__KUBERNETES__DELETE_WORKER_PODS: "False"` to keep pods for debugging
2. Added `time.sleep(600)` in task code to keep failing pods alive
3. Added error logging to `/tmp/*.log` files for inspection via `kubectl exec`

### Phase 12: S3 Data Exchange Between Tasks
**Timestamp:** 03:15 UTC

#### Issue: `FileNotFoundError` in `check_drift` Task
- `ingest_data` saved file locally, but `check_drift` ran in different pod
- Local filesystem not shared between task pods

#### Solution:
- Refactored `data_loader.py` to use S3 (SeaweedFS) for all data storage
- Added `save_raw_data()` and `load_raw_data()` functions using `boto3`
- Modified DAG to pass S3 keys via XCom instead of file paths

### Phase 13: API Integration Fix
**Timestamp:** 03:20 UTC

#### Issue: `400 Bad Request` from External Data API
- API expected query parameters (`?group_number=5&day=Tuesday`)
- Code was using path parameters or incorrect format

#### Solution:
- Updated `fetch_data()` to use `requests.get(url, params={...})`
- Added proper parameter extraction from Airflow context

### Phase 14: Corrupted Reference Data
**Timestamp:** 03:25 UTC

#### Issue: `KeyError: ['price']` in `clean_data()`
- `reference.csv` in S3 had old nested format (columns: `group_number`, `day`, `batch_number`, `data`)
- Was saved before the API response parsing fix

#### Solution:
- Deleted corrupted `reference.csv` from S3
- Re-ran DAG to regenerate with correct format

### Phase 15: MLflow Version Incompatibility ⭐
**Timestamp:** 03:45 UTC

#### Issue: `MlflowException: API request to /api/2.0/mlflow/logged-models failed with 404`
- Training completed but model logging failed
- Scheduler marked tasks as "zombie"

#### Root Cause:
| Component | Version |
|-----------|---------|
| MLflow Client (Airflow) | **3.6.0** |
| MLflow Server | **1.28.0** |

MLflow 3.x client uses new APIs not available in 1.28.0 server.

#### Solution:
1. Pinned `mlflow==2.9.2` in `apps/airflow/requirements.txt`
2. Built new Docker image `davidm094/mlops-airflow:v2`
3. Updated `core-apps.yaml` to use `v2` tag
4. Recreated `airflow-fernet-key` secret (lost during pod restart)
5. Force-deleted and re-created Airflow Argo CD application

#### Verification:
```bash
kubectl exec -n mlops $SCHEDULER_POD -c scheduler -- python3 -c "import mlflow; print(mlflow.__version__)"
# Output: 2.9.2
```

### Phase 16: Full Pipeline Test ✅
**Timestamp:** 03:59 UTC

#### Successful End-to-End Test:
```
1. Loading data...     ✅ 361,457 rows from S3
2. Cleaning...         ✅ Features prepared
3. Training...         ✅ RandomForest (n=50, depth=10)
   RMSE: 1,448,040
4. SHAP...             ✅ TreeExplainer generated
5. MLflow...           ✅ Run ID: d5da15bba06041fcab761bb3335e96bc
```

#### Artifacts Saved to S3:
- `mlflow-artifacts/2/{run_id}/artifacts/model/model.pkl` (4.2 MB)
- `mlflow-artifacts/2/{run_id}/artifacts/explainer.pkl` (5.8 MB)

### Phase 17: API & Frontend SHAP Integration
**Timestamp:** 04:00 UTC

#### Changes Made:
1. **API (`apps/api/src/main.py`):**
   - Loads model and SHAP explainer directly from S3/MLflow artifacts
   - `/predict` endpoint returns price prediction
   - `/explain` endpoint returns SHAP values, base value, feature names
   - `/reload` endpoint to refresh model without restart
   - `/health` endpoint for monitoring

2. **Frontend (`apps/frontend/src/app.py`):**
   - Three tabs: Predict, SHAP Explanation, Model Info
   - Interactive SHAP waterfall chart using matplotlib
   - Feature contribution breakdown table
   - Quick insights (price per sqft, per bedroom, per acre)
   - System status sidebar with reload button

3. **Dependencies:**
   - Pinned `mlflow==2.9.2` in both API and Frontend requirements
   - Added `joblib` to API requirements

---

## Current Status

### ✅ Completed Components:

| Component | Status | Notes |
|-----------|--------|-------|
| K3d Cluster | ✅ Running | 1 server + 1 agent |
| Argo CD | ✅ Deployed | GitOps management |
| PostgreSQL | ✅ Running | Metadata for Airflow & MLflow |
| SeaweedFS | ✅ Running | S3-compatible storage |
| Airflow | ✅ Running | v2 image with mlflow==2.9.2 |
| MLflow | ✅ Running | Experiment tracking |
| API (FastAPI) | ✅ Deployed | Prediction & SHAP endpoints |
| Frontend (Streamlit) | ✅ Deployed | Interactive UI |

### ✅ ML Pipeline Status:

| Step | Status | Details |
|------|--------|---------|
| Data Ingestion | ✅ | API → S3 (361k rows) |
| Data Cleaning | ✅ | Handles missing values |
| Drift Detection | ✅ | KS-test on numerical features |
| Model Training | ✅ | RandomForest, logged to MLflow |
| SHAP Explainer | ✅ | TreeExplainer saved as artifact |
| Model Serving | ✅ | FastAPI loads from S3 |
| Interpretability | ✅ | SHAP waterfall in Streamlit |

### Access URLs:
| Service | URL | Credentials |
|---------|-----|-------------|
| Argo CD | http://localhost:30443 | admin / (from secret) |
| Airflow | http://localhost:30080 | admin / admin |
| MLflow | http://localhost:30500 | - |
| API | http://localhost:30800 | - |
| Frontend | http://localhost:30501 | - |

---

## Lessons Learned

1. **MLflow Version Compatibility:** Always match client and server versions. Major version differences (3.x vs 1.x) cause API incompatibilities.

2. **KubernetesExecutor Debugging:** Worker pods are ephemeral. Use `DELETE_WORKER_PODS=False` and `time.sleep()` for debugging.

3. **S3 for Inter-Task Data:** In KubernetesExecutor, tasks run in separate pods. Use S3/external storage for data exchange, not local files.

4. **Argo CD Self-Heal:** Don't mix manual `kubectl` changes with GitOps. Always update Git and let Argo CD sync.

5. **Helm Chart Quirks:** Older charts (Airflow 1.10) have non-standard configurations. Read the chart source code when docs are unclear.

6. **External API Limits:** The data source API has usage limits. Cache data in S3 for repeated experiments.

---

## Technical Debt / Future Improvements

- [ ] Add proper TLS certificates
- [ ] Implement secrets management (Vault/Sealed Secrets)
- [ ] Add resource limits/requests to all deployments
- [ ] Implement backup strategy for Postgres and SeaweedFS
- [ ] Add Prometheus/Grafana for observability
- [ ] Implement proper authentication for all services
- [ ] Upgrade MLflow server to 2.x for better compatibility
- [ ] Add model versioning and A/B testing support
- [ ] Implement automated retraining triggers
