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
2. **Networking:** LoadBalancer services (mapped by K3d to localhost) instead of MetalLB
3. **Ingress:** Removed custom Traefik, using K3d's built-in Traefik
4. **DNS:** Eliminated need for nip.io or custom DNS

#### Implementation Steps:

##### Phase 1: Cluster Recreation
- Created `scripts/create_cluster.sh`
- K3d configuration:
  - Ports mapped: 80, 443, 8080 (Airflow), 5000 (MLflow), 8501 (Streamlit)
  - 1 server + 1 agent node
  - Traefik enabled (K3d default)

##### Phase 2: Service Exposure
- Changed all services from ClusterIP to LoadBalancer
- K3d automatically maps LoadBalancer IPs to localhost ports
- Eliminated Ingress complexity for local development

##### Phase 3: Complete Application Definitions
- Created `apps/api/k8s/deployment.yaml`
  - FastAPI service with health checks
  - LoadBalancer on port 8000
  - Environment variables for MLflow and S3

- Created `apps/frontend/k8s/deployment.yaml`
  - Streamlit service
  - LoadBalancer on port 8501
  - Environment variables for API and MLflow URLs

- Updated `infra/argocd/applications/core-apps.yaml`
  - Removed custom Traefik app
  - Added `api` and `frontend` Argo CD applications
  - Changed storageClass from "longhorn-single" to "local-path" (K3d default)

##### Phase 4: Unified Deployment Script
- Created `scripts/start_mlops.sh`
  - Single command deployment
  - Automated cluster creation
  - Argo CD bootstrap
  - Application deployment
  - Health checks and wait conditions
  - Display of access URLs and credentials

##### Phase 5: Documentation
#### Phase 6: Helm Compatibility Fixes (2025-11-23 22:30 UTC)
- Applied upstream requirements for Airflow Helm chart when using Argo CD:
  - Disabled Helm hooks for `createUserJob` and `migrateDatabaseJob`
  - Added `argocd.argoproj.io/hook: Sync` annotation so migrations run during every sync
- Updated MLflow Helm values to use structured `artifactRoot.s3` block (instead of plain string) and wired S3 endpoint/credentials according to chart schema
- Cleaned Airflow `env` section to match chart expectations (array of name/value pairs)
- Result: Argo CD can now render both charts without schema errors and complete the sync

#### Phase 7: NodePort Exposure Strategy (2025-11-23 23:25 UTC)
- Chart v1.10.0 no permite fijar `nodePort` dentro de `webserver.service`, lo que impedía el render de Argo CD.
- Se movió la responsabilidad del NodePort a un manifiesto independiente (`infra/manifests/services/airflow-webserver-nodeport.yaml`) aplicado automáticamente desde `scripts/start_mlops.sh`.
- El chart vuelve a crear un Service `ClusterIP` estándar y el Service personalizado reexpone el Webserver en `30443`.

#### Phase 8: Airflow PostgreSQL Image Override (2025-11-23 23:40 UTC)
- El subchart `postgresql` de Airflow intentaba descargar `bitnami/postgresql`, lo que fallaba en la red del entorno (ImagePullBackOff) y dejaba los jobs de migración en CrashLoop.
- Se forzó al subchart a usar `docker.io/library/postgres:13-alpine`, con credenciales/DB específicas para Airflow y persistencia deshabilitada.
- Con esta imagen pública, el Postgres embebido del chart puede arrancar y los jobs `create-user`/`run-airflow-migrations` completan correctamente.

- Completely rewrote `README.md`
  - Quick start guide
  - Architecture overview
  - Service access URLs
  - Troubleshooting section
  - CI/CD pipeline documentation
  - ML pipeline explanation

### Current Status
**All components ready for deployment:**

✅ Cluster creation script (`create_cluster.sh`)
✅ Unified deployment script (`start_mlops.sh`)
✅ Kubernetes manifests for API and Frontend
✅ Updated Argo CD applications (all 8 apps defined)
✅ Comprehensive documentation
✅ LoadBalancer-based networking (no Ingress complexity)

### Access URLs (Post-Deployment)
- Argo CD: https://localhost
- Airflow: http://localhost:8080
- MLflow: http://localhost:5000
- API: http://localhost:8000
- Frontend: http://localhost:8501

### Lessons Learned
1. **Network Restrictions:** Corporate/university networks can severely limit bare-metal K8s deployments
2. **MetalLB Complexity:** For single-node clusters, LoadBalancer via K3d is simpler than MetalLB
3. **Image Availability:** Always verify image accessibility before deployment (MinIO Docker Hub changes)
4. **Local Development:** K3d provides excellent local K8s experience with minimal overhead
5. **GitOps Challenges:** Argo CD sync requires proper repo access and can cache aggressively

### Next Steps (User Actions Required)
1. Execute `./scripts/start_mlops.sh` in WSL
2. Verify all services are accessible
3. Test ML pipeline end-to-end
4. Validate SHAP explanations in Frontend

### Technical Debt / Future Improvements
- [ ] Add proper TLS certificates (currently using Traefik default)
- [ ] Implement proper secrets management (currently hardcoded)
- [ ] Add resource limits/requests to all deployments
- [ ] Implement proper backup strategy for Postgres and SeaweedFS
- [ ] Add Prometheus/Grafana for observability
- [ ] Implement proper authentication for Airflow/MLflow
