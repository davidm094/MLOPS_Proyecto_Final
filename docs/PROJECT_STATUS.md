# Estado Actual del Proyecto MLOps - Contexto Completo

**Fecha:** 25 de Noviembre 2025  
**Repositorio:** https://github.com/davidm094/MLOPS_Proyecto_Final  
**Última Actualización:** Commit `e9e8ad6` - Fix definitivo para endpoint `/ready`

---

## 📋 Tabla de Contenidos

1. [Resumen del Proyecto](#1-resumen-del-proyecto)
2. [Arquitectura Actual](#2-arquitectura-actual)
3. [Estado del Despliegue](#3-estado-del-despliegue)
4. [Problemas Recientes y Soluciones](#4-problemas-recientes-y-soluciones)
5. [Componentes Implementados](#5-componentes-implementados)
6. [Pipeline de ML](#6-pipeline-de-ml)
7. [CI/CD y GitOps](#7-cicd-y-gitops)
8. [Próximos Pasos](#8-próximos-pasos)
9. [Información Técnica Relevante](#9-información-técnica-relevante)

---

## 1. Resumen del Proyecto

### 1.1 Objetivo

Plataforma MLOps End-to-End desplegada sobre Kubernetes (K3d) que automatiza el ciclo completo de Machine Learning:

- **Ingestión de datos** desde API externa
- **Detección de drift** automática
- **Entrenamiento** condicional de modelos
- **Registro y versionado** en MLflow
- **Promoción automática** a producción
- **Serving** de modelos con FastAPI
- **Interpretabilidad** con SHAP
- **Monitoreo** con Prometheus y Grafana
- **GitOps** con Argo CD

### 1.2 Stack Tecnológico

```
┌─────────────────────────────────────────────────────────────────┐
│                    INFRAESTRUCTURA                               │
├─────────────────────────────────────────────────────────────────┤
│ Kubernetes: K3d (K3s en Docker)                                 │
│ GitOps: Argo CD                                                  │
│ Storage: SeaweedFS (S3) + PostgreSQL                            │
│ Networking: NodePort Services                                   │
│ Observabilidad: Prometheus + Grafana                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    COMPONENTES MLOPS                             │
├─────────────────────────────────────────────────────────────────┤
│ Orquestación: Apache Airflow (KubernetesExecutor + Git-Sync)    │
│ Experiment Tracking: MLflow (Postgres + S3)                     │
│ Model Serving: FastAPI (Predicción + SHAP)                      │
│ Frontend: Streamlit (UI Interactiva)                             │
│ CI/CD: GitHub Actions                                            │
│ Monitoring: Prometheus + Grafana                                │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Requerimientos Cumplidos

| Requerimiento | Estado | Detalles |
|--------------|--------|----------|
| Pipeline automatizado | ✅ | DAG de Airflow con ingestión, drift detection, entrenamiento |
| Registro de modelos | ✅ | MLflow con PostgreSQL y S3 (SeaweedFS) |
| API de inferencia | ✅ | FastAPI con `/predict` y `/explain` |
| Interfaz gráfica | ✅ | Streamlit con visualizaciones SHAP |
| CI/CD | ✅ | GitHub Actions para build y push |
| GitOps | ✅ | Argo CD con sync automático |
| Interpretabilidad | ✅ | SHAP TreeExplainer integrado |
| Kubernetes completo | ✅ | Todos los servicios containerizados |
| Helm | ✅ | Airflow, MLflow, PostgreSQL via Helm |
| Airflow Git-Sync | ✅ | DAGs sincronizados desde Git |

---

## 2. Arquitectura Actual

### 2.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           K3d Cluster                                  │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │   Argo CD    │  │   Airflow    │  │   MLflow     │                │
│  │  (GitOps)    │  │ (Pipelines)  │  │ (Tracking)  │                │
│  │  Port: 30443 │  │  Port: 30080 │  │  Port: 30500 │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│         │                  │                  │                        │
│         └──────────────────┴──────────────────┘                        │
│                            │                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │   FastAPI    │  │  Streamlit   │  │  PostgreSQL  │                │
│  │    (API)     │  │  (Frontend)  │  │  (Metadata) │                │
│  │  Port: 30800 │  │  Port: 30501 │  │  Port: 5432   │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│         │                  │                  │                        │
│         └──────────────────┴──────────────────┘                        │
│                            │                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  SeaweedFS   │  │  Prometheus  │  │   Grafana    │                │
│  │     (S3)     │  │  (Metrics)   │  │ (Dashboards) │                │
│  │  Port: 8333  │  │  Port: 30090 │  │  Port: 30300 │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Flujo de Datos

```
1. API Externa → Airflow (Ingestión)
   ↓
2. PostgreSQL (raw_data) → Airflow (Preprocessing)
   ↓
3. PostgreSQL (clean_data) → Airflow (Drift Detection)
   ↓
4. Si drift detectado → Airflow (Training)
   ↓
5. MLflow (Model Registry) → FastAPI (Serving)
   ↓
6. FastAPI → Streamlit (UI)
   ↓
7. Prometheus (Métricas) → Grafana (Visualización)
```

### 2.3 Puertos Expuestos

| Servicio | Puerto | URL Local |
|----------|--------|-----------|
| Argo CD | 30443 | http://localhost:30443 |
| Airflow | 30080 | http://localhost:30080 |
| MLflow | 30500 | http://localhost:30500 |
| FastAPI | 30800 | http://localhost:30800 |
| Streamlit | 30501 | http://localhost:30501 |
| Prometheus | 30090 | http://localhost:30090 |
| Grafana | 30300 | http://localhost:30300 |
| AlertManager | 30903 | http://localhost:30903 |

---

## 3. Estado del Despliegue

### 3.1 Estado Actual de Pods (Última Verificación)

```
NAME                                       READY   STATUS      RESTARTS   AGE
airflow-create-user-g5zlp                  0/1     Completed   0          3m48s
airflow-scheduler-694b5f64c-ckhdq          3/3     Running     4          9h
airflow-statsd-9848cd6f8-l46vk             1/1     Running     0          10h
airflow-triggerer-0                        3/3     Running     3          10h
airflow-webserver-68479c8869-c7k57         1/1     Running     0          7h49m
api-59894449bc-bxn4n                       0/1     Running     0          8h      ⚠️
api-5bb7647b47-2fwxl                       1/1     Running     0          9h      ✅
frontend-545d74565d-5tqj4                  1/1     Running     0          8h      ✅
mlflow-75f79784cc-9gmx2                    1/1     Running     0          34h     ✅
```

### 3.2 Estado en Argo CD

- **Sync Status:** ✅ Synced to HEAD (`e9e8ad6`)
- **App Health:** ⚠️ Degraded (debido a pod API con readiness probe fallando)
- **Last Sync:** Succeeded (hace ~1 minuto)
- **Auto Sync:** ✅ Enabled

### 3.3 Problema Actual

**Pod API `api-59894449bc-bxn4n`:**
- **Estado:** Running pero `0/1` Ready
- **Causa:** Readiness probe fallando (endpoint `/ready` devolviendo 404)
- **Impacto:** Argo CD marca la aplicación como "Degraded"
- **Solución:** Fix implementado en commit `e9e8ad6` (pendiente de despliegue)

---

## 4. Problemas Recientes y Soluciones

### 4.1 Problema: Endpoint `/ready` devolviendo 404

#### Síntomas
- Readiness probe fallando constantemente
- Logs mostrando: `"GET /ready HTTP/1.1" 404 Not Found`
- Pod API no pasa a estado Ready
- Argo CD marca aplicación como "Degraded"

#### Causa Raíz
`prometheus-fastapi-instrumentator` estaba interceptando las rutas **antes** de que FastAPI las procesara, causando conflictos incluso con `excluded_handlers`.

#### Solución Implementada

**Commit:** `e9e8ad6` - "fix: Replace Instrumentator with custom middleware to fix /ready 404"

**Cambios:**
1. ❌ **Removido:** `prometheus-fastapi-instrumentator`
2. ✅ **Agregado:** Middleware personalizado `PrometheusMiddleware`
3. ✅ **Configuración:** Middleware explícitamente omite `/ready`, `/health`, `/metrics`

**Código del Middleware:**
```python
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip instrumentation for health checks and metrics
        if request.url.path in ["/ready", "/health", "/metrics"]:
            return await call_next(request)
        
        # Instrument other routes
        method = request.method
        endpoint = request.url.path
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        HTTP_REQUESTS_TOTAL.labels(...).inc()
        HTTP_REQUEST_DURATION.labels(...).observe(duration)
        
        return response
```

**Ventajas:**
- Control total sobre qué rutas se instrumentan
- No interfiere con el registro de rutas de FastAPI
- Health checks funcionan correctamente
- Métricas de Prometheus siguen funcionando

#### Estado
- ✅ **Código:** Commiteado y pusheado
- ⏳ **Imagen:** Pendiente de build por CI/CD
- ⏳ **Despliegue:** Pendiente de sync por Argo CD

### 4.2 Historial de Fixes Recientes

| Commit | Descripción | Estado |
|--------|-------------|--------|
| `e9e8ad6` | Replace Instrumentator with custom middleware | ✅ Commiteado |
| `200a332` | Add error handling for Instrumentator | ⚠️ Reemplazado |
| `9c22f6c` | Move /ready and /health to top | ⚠️ Reemplazado |
| `263d8a4` | Improve Instrumentator configuration | ⚠️ Reemplazado |
| `ec14b86` | Move Instrumentator to end of file | ⚠️ Reemplazado |

---

## 5. Componentes Implementados

### 5.1 Apache Airflow

**Configuración:**
- **Executor:** KubernetesExecutor
- **Git-Sync:** Habilitado (sincroniza DAGs desde Git)
- **Imagen:** `davidm094/mlops-airflow:v4`
- **DAG Principal:** `mlops_full_pipeline`

**Pipeline:**
1. `ingest_data` - Obtiene datos de API externa, guarda en PostgreSQL
2. `check_drift` - Detecta drift usando KS-test
3. `train_model` - Entrena modelo si hay drift (XGBoost + Optuna)
4. `reload_api` - Notifica a API para cargar nuevo modelo
5. `skip_training` - Si no hay drift, salta entrenamiento

**Almacenamiento:**
- **Metadata:** PostgreSQL (`airflow` database)
- **Logs:** SeaweedFS S3 (`airflow-logs` bucket)
- **Datos:** PostgreSQL (`mlops_data` database)

### 5.2 MLflow

**Configuración:**
- **Backend Store:** PostgreSQL (`mlflow` database)
- **Artifact Store:** SeaweedFS S3 (`mlflow-artifacts` bucket)
- **Model Registry:** Habilitado con stages (Production, Staging, etc.)

**Modelos Registrados:**
- **Nombre:** `real_estate_model`
- **Versión Actual en Producción:** v5
- **Run ID:** `74993ec7c3a945bfb7c0bab944c929ba`
- **Métricas:** R², RMSE, MAE, MAPE

**Artefactos:**
- `model.pkl` - Modelo entrenado (XGBoost)
- `state_means.pkl` - Encoding de estados
- `features.txt` - Lista de features usadas
- `shap_explainer.pkl` - Explainer SHAP (opcional)

### 5.3 FastAPI (API de Inferencia)

**Endpoints:**
- `GET /` - Información del servicio
- `GET /health` - Health check (conexión DB, modelo cargado)
- `GET /ready` - Readiness probe (solo modelo cargado)
- `GET /model` - Información del modelo actual
- `GET /states` - Lista de estados disponibles
- `POST /predict` - Predicción de precio
- `POST /explain` - Explicación SHAP
- `POST /reload` - Recargar modelo desde MLflow
- `POST /batch_predict` - Predicciones en lote
- `GET /predictions/history` - Historial de predicciones
- `GET /metrics/summary` - Resumen de métricas
- `GET /metrics` - Métricas de Prometheus

**Métricas Prometheus:**
- `predictions_total` - Total de predicciones
- `prediction_latency_seconds` - Latencia de predicciones
- `prediction_price_dollars` - Distribución de precios
- `model_loaded` - Estado del modelo
- `explainer_loaded` - Estado del explainer
- `http_requests_total` - Total de requests HTTP
- `http_request_duration_seconds` - Duración de requests

**Modelo Actual:**
- **Versión:** v5
- **Stage:** Production
- **Features:** 11 (bed, bath, acre_lot, house_size, state_price_mean, is_sold, bed_bath_interaction, size_per_bed, size_per_bath, total_rooms, lot_to_house_ratio)
- **Estados:** 53 estados con encoding

### 5.4 Streamlit (Frontend)

**Tabs:**
1. **Predict Price** - Formulario de predicción
2. **SHAP Explanation** - Visualización de impacto de features
3. **Compare Locations** - Comparación de precios por estado
4. **Metrics & Info** - Información del modelo y métricas

**Características:**
- Integración con API FastAPI
- Visualizaciones SHAP interactivas
- Comparación de precios entre estados
- Métricas agregadas de predicciones

### 5.5 PostgreSQL

**Bases de Datos:**
- `airflow` - Metadata de Airflow
- `mlflow` - Metadata de MLflow
- `mlops_data` - Datos del pipeline

**Tablas en `mlops_data`:**
- `raw_data` - Datos crudos de ingestión
- `clean_data` - Datos procesados
- `inference_logs` - Logs de predicciones
- `drift_history` - Historial de detección de drift
- `model_history` - Historial de entrenamientos

### 5.6 SeaweedFS (S3)

**Buckets:**
- `data-raw` - Datos crudos (backup)
- `data-clean` - Datos procesados (backup)
- `mlflow-artifacts` - Artefactos de MLflow
- `airflow-logs` - Logs de Airflow

### 5.7 Prometheus + Grafana

**Prometheus:**
- Scraping automático de pods con anotaciones
- Métricas de API, Airflow, MLflow
- Retención: 7 días

**Grafana:**
- Dashboard pre-configurado para API
- Métricas: requests/sec, latency, error rate
- Alertas configuradas

---

## 6. Pipeline de ML

### 6.1 Flujo Completo

```
┌─────────────────────────────────────────────────────────────┐
│                   1. INGESTIÓN                               │
│  API Externa → Airflow → PostgreSQL (raw_data)               │
│  Backup: SeaweedFS S3                                        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                   2. PREPROCESSING                           │
│  Limpieza, feature engineering, outlier removal             │
│  PostgreSQL (clean_data)                                     │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                   3. DRIFT DETECTION                         │
│  KS-test comparando batch actual vs referencia              │
│  Si drift → continuar, Si no → skip training                │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                   4. TRAINING (si drift)                    │
│  - Feature engineering avanzado                              │
│  - XGBoost con Optuna (hyperparameter tuning)               │
│  - Logging a MLflow (métricas, artefactos)                   │
│  - Auto-promotion si R² >= 0.35 y RMSE <= $700K           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                   5. MODEL PROMOTION                        │
│  Si métricas cumplen thresholds → Production                │
│  Archive existing Production versions                        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                   6. API RELOAD                             │
│  Airflow → POST /reload → FastAPI carga nuevo modelo       │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Modelo Actual

**Algoritmo:** XGBoost Regressor

**Features:**
1. `bed` - Número de habitaciones
2. `bath` - Número de baños
3. `acre_lot` - Tamaño del lote (acres)
4. `house_size` - Tamaño de la casa (sqft)
5. `state_price_mean` - Precio promedio del estado
6. `is_sold` - Si está vendido (0/1)
7. `bed_bath_interaction` - Interacción bed × bath
8. `size_per_bed` - Tamaño por habitación
9. `size_per_bath` - Tamaño por baño
10. `total_rooms` - Total de habitaciones
11. `lot_to_house_ratio` - Ratio lote/casa

**Hyperparameter Tuning:**
- **Framework:** Optuna
- **Trials:** 10-20 por entrenamiento
- **Métricas:** Cross-validation R²
- **Parámetros optimizados:** n_estimators, max_depth, learning_rate, subsample, colsample_bytree, min_child_weight, reg_alpha, reg_lambda

**Promotion Criteria:**
- R² >= 0.35
- RMSE <= $700,000
- Si cumple → Auto-promotion a Production

### 6.3 Drift Detection

**Método:** Kolmogorov-Smirnov Test

**Features Monitoreadas:**
- `bed`, `bath`, `acre_lot`, `house_size`, `price`

**Threshold:** p-value < 0.05 indica drift

**Acción:** Si drift detectado → trigger training

---

## 7. CI/CD y GitOps

### 7.1 GitHub Actions

**Workflow:** `.github/workflows/ci.yaml`

**Steps:**
1. Checkout código
2. Set up Docker Buildx
3. Build imágenes:
   - `davidm094/mlops-airflow:latest`
   - `davidm094/mlops-api:latest`
   - `davidm094/mlops-frontend:latest`
4. Push a Docker Hub
5. Tests (unit + integration)

**Triggers:**
- Push a `main`
- Pull requests

### 7.2 Argo CD

**Configuración:**
- **Sync Policy:** Automated (prune, selfHeal)
- **Sync Options:** CreateNamespace=true
- **Applications:**
  - `secrets` (sync-wave: -1)
  - `postgres`
  - `seaweedfs`
  - `mlflow`
  - `airflow`
  - `api`
  - `frontend`
  - `prometheus-stack`

**Estado Actual:**
- ✅ Synced to HEAD
- ⚠️ Health: Degraded (pod API con readiness probe fallando)
- ✅ Auto sync enabled

---

## 8. Próximos Pasos

### 8.1 Inmediatos (Pendientes)

1. **Esperar Build de CI/CD**
   - La nueva imagen `davidm094/mlops-api:latest` con el fix del middleware
   - Verificar en GitHub Actions

2. **Verificar Despliegue Automático**
   - Argo CD debería detectar la nueva imagen y hacer rolling update
   - El pod nuevo debería pasar readiness probe

3. **Validar Fix**
   - Verificar que `/ready` responde 200 OK
   - Verificar que `/metrics` responde correctamente
   - Verificar que Argo CD marca la app como "Healthy"

### 8.2 Mejoras Futuras (Opcionales)

1. **Tests Automatizados**
   - Agregar tests de integración para el middleware
   - Tests de health checks

2. **Documentación**
   - Actualizar README con información del middleware
   - Documentar troubleshooting de health checks

3. **Optimizaciones**
   - Revisar resource limits de pods
   - Optimizar queries a PostgreSQL
   - Cache de métricas de Prometheus

---

## 9. Información Técnica Relevante

### 9.1 Comandos Útiles

**Ver logs del pod API:**
```bash
kubectl logs -n mlops -l app=api --tail=100
```

**Verificar readiness probe:**
```bash
kubectl get pods -n mlops -l app=api -o jsonpath='{.items[0].spec.containers[0].readinessProbe}'
```

**Probar endpoint /ready manualmente:**
```bash
kubectl port-forward -n mlops svc/api 8000:8000
curl http://localhost:8000/ready
```

**Ver estado en Argo CD:**
```bash
kubectl get applications -n argocd
```

**Forzar sync en Argo CD:**
```bash
argocd app sync api
```

### 9.2 Archivos Clave

**API:**
- `apps/api/src/main.py` - Código principal de FastAPI
- `apps/api/requirements.txt` - Dependencias Python
- `apps/api/k8s/deployment.yaml` - Deployment Kubernetes

**Airflow:**
- `apps/airflow/dags/mlops_pipeline.py` - DAG principal
- `apps/airflow/dags/src/` - Módulos del pipeline
- `apps/airflow/Dockerfile` - Imagen personalizada

**Infraestructura:**
- `infra/argocd/applications/` - Aplicaciones Argo CD
- `infra/manifests/` - Manifests Kubernetes
- `scripts/create_cluster.sh` - Script de creación de cluster

### 9.3 Variables de Entorno Importantes

**API:**
- `MLFLOW_TRACKING_URI` - URI de MLflow
- `S3_ENDPOINT` - Endpoint de SeaweedFS
- `DATABASE_URL` - Connection string de PostgreSQL

**Airflow:**
- `DATA_SOURCE_URL` - URL de API externa
- `API_URL` - URL de API interna
- `DATABASE_URL` - Connection string de PostgreSQL
- `MLFLOW_TRACKING_URI` - URI de MLflow

### 9.4 Secrets de Kubernetes

**Secretos configurados:**
- `s3-credentials` - Credenciales de SeaweedFS
- `postgres-credentials` - Credenciales de PostgreSQL
- `mlflow-credentials` - Credenciales de MLflow

**Ubicación:** `infra/manifests/secrets/credentials.yaml`

---

## 10. Resumen Ejecutivo

### Estado General: ⚠️ Degraded (Temporal)

**Causa:** Pod API con readiness probe fallando debido a endpoint `/ready` devolviendo 404.

**Solución:** Implementada y commiteada. Pendiente de build y despliegue.

**Expectativa:** Una vez desplegada la nueva imagen, el problema debería resolverse y la aplicación debería pasar a estado "Healthy".

### Componentes Funcionando: ✅

- ✅ Airflow (scheduler, webserver, triggerer)
- ✅ MLflow (tracking server)
- ✅ PostgreSQL (todas las bases de datos)
- ✅ SeaweedFS (S3 storage)
- ✅ Streamlit (frontend)
- ✅ Prometheus + Grafana (monitoring)
- ✅ Argo CD (GitOps)
- ⚠️ FastAPI (API funcionando pero readiness probe fallando)

### Próxima Acción Requerida

**Ninguna acción manual requerida.** El CI/CD construirá automáticamente la nueva imagen y Argo CD la desplegará. Solo es necesario esperar (~5-10 minutos).

---

**Última Actualización:** 25 de Noviembre 2025, 01:30 AM  
**Commit Actual:** `e9e8ad6`  
**Autor:** David Moreno

