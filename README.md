# MLOps Proyecto Final - End-to-End Kubernetes Platform

Este repositorio contiene la implementación completa de una plataforma MLOps End-to-End desplegada sobre Kubernetes (K3d) y gestionada vía GitOps con Argo CD.

## 🏗 Arquitectura

### Infraestructura
- **Kubernetes:** K3d (K3s en Docker) - Ideal para desarrollo local en WSL/Linux/macOS
- **GitOps:** Argo CD (Continuous Deployment)
- **Storage:** SeaweedFS (S3-compatible) + PostgreSQL
- **Networking:** Traefik (integrado con K3d) + LoadBalancer Services

### Componentes MLOps
- **Orquestación:** Apache Airflow con KubernetesExecutor y Git-Sync
- **Experiment Tracking:** MLflow (Backend: Postgres, Artifacts: SeaweedFS S3)
- **Model Serving:** FastAPI con endpoints de predicción y explicabilidad (SHAP)
- **Frontend:** Streamlit con visualizaciones interactivas
- **CI/CD:** GitHub Actions para build y push de imágenes Docker

## 🚀 Inicio Rápido

### Prerequisitos
- Docker Desktop (Windows/macOS) o Docker Engine (Linux)
- WSL2 (si estás en Windows)
- 8GB RAM mínimo, 16GB recomendado
- 20GB de espacio en disco

### Despliegue Automatizado (Un Solo Comando)

```bash
# 1. Clonar el repositorio
git clone https://github.com/davidm094/MLOPS_Proyecto_Final.git
cd MLOPS_Proyecto_Final

# 2. Dar permisos de ejecución a los scripts
chmod +x scripts/*.sh

# 3. Ejecutar el despliegue completo
./scripts/start_mlops.sh
```

Este script:
1. ✅ Crea un cluster K3d con configuración optimizada
2. ✅ Instala y configura Argo CD
3. ✅ Despliega toda la infraestructura (Postgres, SeaweedFS)
4. ✅ Despliega las aplicaciones MLOps (Airflow, MLflow, API, Frontend)
5. ✅ Muestra las URLs de acceso y credenciales

**Tiempo estimado:** 5-7 minutos

> **Nota Airflow + Argo CD:** El chart oficial requiere deshabilitar los hooks de `createUserJob` y `migrateDatabaseJob` y marcar la migración con `argocd.argoproj.io/hook: Sync` para que las migraciones se ejecuten en cada sincronización. Esta configuración ya está aplicada en `infra/argocd/applications/core-apps.yaml` siguiendo la guía oficial.[^airflow-helm]
>
> Adicionalmente forzamos al subchart de PostgreSQL de Airflow a usar la imagen pública `library/postgres:13-alpine`, evitando los `ImagePullBackOff` que provoca la imagen de Bitnami en entornos restringidos.

## 🌐 Acceso a Servicios

Una vez completado el despliegue, los servicios están disponibles en:

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Argo CD** | http://localhost:30080 | admin / (ver output del script) |
| **Airflow** | http://localhost:30443 | admin / admin |
| **MLflow** | http://localhost:30500 | - |
| **API (FastAPI)** | http://localhost:30800 | - |
| **Frontend (Streamlit)** | http://localhost:30501 | - |

> Airflow expone su UI mediante un `Service` tipo NodePort (`infra/manifests/services/airflow-webserver-nodeport.yaml`), aplicado automáticamente por `start_mlops.sh`.

### Obtener Password de Argo CD
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d && echo
```

## 📂 Estructura del Proyecto

```
.
├── apps/
│   ├── airflow/
│   │   ├── dags/                 # DAGs de Airflow (sincronizados vía Git-Sync)
│   │   │   └── src/              # Scripts de ML (training, drift, preprocessing)
│   │   ├── Dockerfile            # Imagen custom de Airflow
│   │   └── requirements.txt
│   ├── api/
│   │   ├── src/                  # FastAPI application
│   │   ├── k8s/                  # Manifiestos de Kubernetes
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/                  # Streamlit application
│       ├── k8s/                  # Manifiestos de Kubernetes
│       ├── Dockerfile
│       └── requirements.txt
├── infra/
│   ├── argocd/
│   │   ├── applications/         # Definiciones de Apps de Argo CD
│   │   └── install/              # Manifiestos de instalación de Argo CD
│   ├── charts/                   # Helm values (deprecado, ahora inline)
│   └── manifests/
│       ├── ingress/              # Reglas de Ingress (deprecado en local)
│       └── setup/                # Jobs de inicialización (buckets S3)
├── scripts/
│   ├── start_mlops.sh            # 🚀 Script principal de despliegue
│   ├── create_cluster.sh         # Creación del cluster K3d
│   ├── bootstrap_argocd.sh       # Instalación de Argo CD
│   └── setup_host.sh             # Setup para VM (deprecado en local)
└── README.md
```

## 🤖 Pipeline de Machine Learning

### Flujo Completo
1. **Ingesta de Datos:** Obtención desde API externa (`http://10.43.100.103:8000`)
2. **Detección de Drift:** Kolmogorov-Smirnov test en features numéricas
3. **Entrenamiento Condicional:** Se ejecuta solo si hay drift detectado
4. **Registro en MLflow:** Modelo, métricas (RMSE, R²) y artefacto SHAP
5. **Promoción a Producción:** Tag "Production" en MLflow Model Registry

### Modelo y Features
- **Algoritmo:** Random Forest Regressor
- **Target:** Precio de propiedades
- **Features:** Superficie, habitaciones, baños, ubicación, etc.
- **Explicabilidad:** SHAP TreeExplainer registrado como artefacto

### DAG de Airflow
```
ingest_data → check_drift → [train_model | skip_training]
```

## 🔍 Explicabilidad con SHAP

### Endpoints de la API
- `POST /predict`: Predicción de precio
- `POST /explain`: Valores SHAP para interpretabilidad
- `GET /health`: Health check

### Visualización en Streamlit
- Formulario interactivo de entrada
- Predicción en tiempo real
- Gráficos SHAP (bar plot con contribución de features)
- Historial de experimentos de MLflow

## 🛠 Comandos Útiles

### Gestión del Cluster
```bash
# Ver estado de todos los pods
kubectl get pods -A

# Ver servicios en el namespace mlops
kubectl get svc -n mlops

# Ver estado de las aplicaciones en Argo CD
kubectl get apps -n argocd

# Ver logs de Airflow
kubectl logs -n mlops -l component=webserver -f

# Ver logs de MLflow
kubectl logs -n mlops -l app.kubernetes.io/name=mlflow -f

# Detener el cluster (conserva datos)
k3d cluster stop mlops-cluster

# Reiniciar el cluster
k3d cluster start mlops-cluster

# Eliminar el cluster completamente
k3d cluster delete mlops-cluster
```

### Debugging
```bash
# Ejecutar shell en un pod
kubectl exec -it <pod-name> -n mlops -- /bin/bash

# Ver eventos del cluster
kubectl get events -n mlops --sort-by='.lastTimestamp'

# Describir un recurso
kubectl describe pod <pod-name> -n mlops
```

## 🔄 CI/CD Pipeline

### GitHub Actions
El workflow `.github/workflows/ci.yaml` se ejecuta automáticamente en cada push a `main`:

1. Build de imágenes Docker (airflow, api, frontend)
2. Tag con `github.sha` y `latest`
3. Push a Docker Hub

### Configuración de Secretos
En GitHub → Settings → Secrets and variables → Actions:
- `DOCKERHUB_USERNAME`: Tu usuario de Docker Hub
- `DOCKERHUB_TOKEN`: Token de acceso (no password)

### Actualización de Imágenes
Argo CD sincroniza automáticamente cada 3 minutos. Para forzar actualización:
```bash
kubectl rollout restart deployment/api -n mlops
kubectl rollout restart deployment/frontend -n mlops
```

## 📊 Monitoreo y Observabilidad

### Métricas en MLflow
- RMSE (Root Mean Squared Error)
- R² Score
- Historial de experimentos con comparación visual

### Logs de Airflow
Accesibles desde la UI de Airflow (`http://localhost:8080`) en cada tarea del DAG.

### Estado de Sincronización
Argo CD UI (`https://localhost`) muestra el estado de salud y sincronización de todas las aplicaciones en tiempo real.

## 🧪 Testing del Pipeline

### 1. Activar el DAG en Airflow
```
1. Acceder a http://localhost:8080
2. Login: admin / admin
3. Activar el DAG "mlops_full_pipeline"
4. Trigger manual: botón "▶️" (Play)
```

### 2. Verificar Ejecución
- Ver logs en cada tarea del DAG
- Confirmar que `train_model` se ejecuta si hay drift
- Verificar registro en MLflow

### 3. Probar la API
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "MedInc": 3.5,
    "HouseAge": 15.0,
    "AveRooms": 5.0,
    "AveBedrms": 1.2,
    "Population": 1000.0,
    "AveOccup": 3.0,
    "Latitude": 34.0,
    "Longitude": -118.0
  }'
```

### 4. Usar el Frontend
```
1. Acceder a http://localhost:8501
2. Llenar el formulario con valores de prueba
3. Ver predicción y gráficos SHAP
```

## 🐛 Troubleshooting

### El cluster no arranca
```bash
# Verificar Docker
docker ps

# Recrear el cluster
k3d cluster delete mlops-cluster
./scripts/start_mlops.sh
```

### Los pods están en CrashLoopBackOff
```bash
# Ver logs del pod problemático
kubectl logs <pod-name> -n mlops

# Verificar eventos
kubectl get events -n mlops --sort-by='.lastTimestamp'
```

### Argo CD no sincroniza
```bash
# Forzar sincronización desde CLI
kubectl patch application <app-name> -n argocd --type merge -p '{"operation": {"sync": {"prune": true}}}'

# O desde la UI: botón "SYNC" en cada aplicación
```

### Imágenes no se descargan
```bash
# Verificar conectividad a Docker Hub
docker pull davidm094/mlops-api:latest

# Si falla, verificar credenciales en GitHub Actions
```

### Actualización de Imágenes (Airflow/API)
Este proyecto utiliza la estrategia de **Tags Mutables** (`:v1`, `:latest`) con `imagePullPolicy: Always`.
Para actualizar una imagen sin cambiar el tag:

1. Push de la nueva imagen a DockerHub.
2. Reiniciar los pods para forzar la descarga:
```bash
kubectl rollout restart deployment/airflow-scheduler -n mlops
kubectl rollout restart deployment/airflow-webserver -n mlops
```

## 📚 Referencias

- [Documentación de K3d](https://k3d.io/)
- [Argo CD Documentation](https://argo-cd.readthedocs.io/)
- [Apache Airflow](https://airflow.apache.org/)
- [MLflow](https://mlflow.org/)
- [SHAP (SHapley Additive exPlanations)](https://shap.readthedocs.io/)
- [Helm Chart for Apache Airflow](https://airflow.apache.org/docs/helm-chart/stable/index.html)[^airflow-helm]

[^airflow-helm]: Sección “Installing the Chart with Argo CD, Flux, Rancher or Terraform” de la documentación oficial del chart de Airflow.

## 👥 Autor

David Moreno - Proyecto Final MLOps 2025

## 📄 Licencia

Este proyecto es parte de un trabajo académico.
