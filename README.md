# MLOps Proyecto Final - End-to-End Kubernetes Platform

Este repositorio contiene la implementación completa de la plataforma MLOps requerida para el Proyecto Final, desplegada sobre Kubernetes (K3s) y gestionada vía GitOps con Argo CD.

## 🏗 Arquitectura

- **Infraestructura:** K3s en Rocky Linux 9 (Bare Metal).
- **Orquestación:** Apache Airflow (Helm + Git-Sync).
- **Experiment Tracking:** MLflow (Backend Postgres, Artifacts MinIO).
- **Model Serving:** FastAPI (Docker Container).
- **Frontend:** Streamlit (Docker Container).
- **GitOps:** Argo CD.
- **Observabilidad:** Prometheus & Grafana.

## 🚀 Despliegue

### 1. Preparación del Host
Ejecutar el script de configuración en la VM (Rocky Linux):
```bash
sudo ./scripts/setup_host.sh
```

### 2. Bootstrap de Infraestructura
Inicializar el clúster y desplegar Argo CD:
```bash
./scripts/bootstrap_argocd.sh
```

### 3. CI/CD
Los pipelines de GitHub Actions construirán las imágenes automáticamente al hacer push a `main`.
Asegurarse de configurar los secretos en GitHub: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.

### 4. Acceso a Servicios (MetalLB IPs)
- **Airflow:** `http://airflow.10.43.100.94.nip.io`
- **MLflow:** `http://mlflow.10.43.100.94.nip.io`
- **API:** `http://10.43.100.95:8000` (LoadBalancer IP)
- **Streamlit:** `http://10.43.100.96:8501` (LoadBalancer IP)

## 📂 Estructura del Proyecto
- `apps/`: Código fuente de las aplicaciones (Airflow DAGs, API, Frontend).
- `infra/`: Manifiestos de Kubernetes y Helm Charts (Argo CD).
- `scripts/`: Scripts de automatización.

## 🤖 Modelo ML & SHAP
El pipeline de entrenamiento incluye:
1. Ingesta de datos desde API externa.
2. Detección de Drift (KS Test).
3. Entrenamiento (Random Forest).
4. Cálculo de explicabilidad (SHAP).
5. Registro en MLflow.

La API expose `/explain` para obtener valores SHAP, visualizados en Streamlit.
