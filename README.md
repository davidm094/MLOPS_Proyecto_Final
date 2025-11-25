# MLOps Proyecto Final - End-to-End Kubernetes Platform

Este repositorio contiene la implementación completa de una plataforma MLOps End-to-End desplegada sobre Kubernetes (K3d) y gestionada vía GitOps con Argo CD.

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              K3d Cluster                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Argo CD   │  │   Airflow   │  │   MLflow    │  │  SeaweedFS  │        │
│  │  (GitOps)   │  │ (Pipelines) │  │ (Tracking)  │  │    (S3)     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│         │                │                │                │                │
│         └────────────────┴────────────────┴────────────────┘                │
│                                   │                                          │
│  ┌─────────────┐  ┌─────────────┐│  ┌─────────────┐                        │
│  │   FastAPI   │  │  Streamlit  ││  │ PostgreSQL  │                        │
│  │    (API)    │  │ (Frontend)  ││  │  (Metadata) │                        │
│  └─────────────┘  └─────────────┘│  └─────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Infraestructura
- **Kubernetes:** K3d (K3s en Docker) - Ideal para desarrollo local
- **GitOps:** Argo CD (Continuous Deployment desde Git)
- **Storage:** SeaweedFS (S3-compatible) + PostgreSQL
- **Networking:** NodePort Services

### Componentes MLOps
- **Orquestación:** Apache Airflow con KubernetesExecutor y Git-Sync
- **Experiment Tracking:** MLflow (Backend: Postgres, Artifacts: SeaweedFS S3)
- **Model Serving:** FastAPI con endpoints de predicción y explicabilidad
- **Interpretabilidad:** SHAP TreeExplainer para explicaciones de predicciones
- **Frontend:** Streamlit con visualizaciones interactivas
- **CI/CD:** GitHub Actions para build y push de imágenes Docker

## 🚀 Inicio Rápido

### Prerequisitos
- Docker Desktop (Windows/macOS) o Docker Engine (Linux)
- WSL2 (si estás en Windows)
- kubectl instalado
- 8GB RAM mínimo, 16GB recomendado
- 20GB de espacio en disco

### Despliegue Automatizado

```bash
# 1. Clonar el repositorio
git clone https://github.com/davidm094/MLOPS_Proyecto_Final.git
cd MLOPS_Proyecto_Final

# 2. Dar permisos de ejecución a los scripts
chmod +x scripts/*.sh

# 3. Ejecutar el despliegue completo
./scripts/start_mlops.sh
```

**Tiempo estimado:** 5-7 minutos

Este script:
1. ✅ Crea un cluster K3d con puertos mapeados
2. ✅ Instala y configura Argo CD
3. ✅ Despliega toda la infraestructura (Postgres, SeaweedFS)
4. ✅ Despliega las aplicaciones MLOps (Airflow, MLflow, API, Frontend)
5. ✅ Crea buckets S3 necesarios
6. ✅ Muestra las URLs de acceso y credenciales

## 🌐 Acceso a Servicios

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Argo CD** | http://localhost:30443 | admin / (ver comando abajo) |
| **Airflow** | http://localhost:30080 | admin / admin |
| **MLflow** | http://localhost:30500 | - |
| **API (FastAPI)** | http://localhost:30800 | - |
| **Frontend (Streamlit)** | http://localhost:30501 | - |

### Obtener Password de Argo CD
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d && echo
```

## 🤖 Pipeline de Machine Learning

### Flujo del DAG
```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    start     │───▶│ ingest_data  │───▶│ check_drift  │───▶│ train_model  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                               │                    │
                                               │ (no drift)         │
                                               ▼                    ▼
                                        ┌──────────────┐    ┌──────────────┐
                                        │ end_pipeline │◀───│ end_pipeline │
                                        └──────────────┘    └──────────────┘
```

### Descripción de Tareas

| Tarea | Descripción |
|-------|-------------|
| `ingest_data` | Descarga datos de API externa, guarda en S3 |
| `check_drift` | Compara datos actuales vs referencia (KS-test) |
| `train_model` | Entrena RandomForest, registra en MLflow con SHAP |
| `end_pipeline` | Marca finalización del pipeline |

### Modelo y Features

- **Algoritmo:** Random Forest Regressor
- **Target:** Precio de propiedades inmobiliarias
- **Features utilizadas:**
  - `bed` - Número de habitaciones
  - `bath` - Número de baños
  - `acre_lot` - Tamaño del lote (acres)
  - `house_size` - Tamaño de la casa (sqft)

### Métricas Registradas
- **RMSE:** Root Mean Squared Error (~$1.4M)
- **R²:** Coeficiente de determinación

## 🔍 Explicabilidad con SHAP

### ¿Qué es SHAP?
SHAP (SHapley Additive exPlanations) es una técnica que explica las predicciones de modelos ML asignando a cada feature un valor de importancia para cada predicción individual.

### Implementación

1. **Durante el entrenamiento:**
   - Se genera un `TreeExplainer` para el modelo RandomForest
   - Se guarda como artefacto `explainer.pkl` en MLflow/S3

2. **En la API (`/explain`):**
   - Carga el explainer desde S3
   - Calcula SHAP values para la entrada
   - Retorna valores, base value y nombres de features

3. **En el Frontend:**
   - Visualiza un gráfico de barras con contribuciones
   - Muestra tabla detallada de impacto por feature
   - Indica dirección del impacto (aumenta/disminuye precio)

### Ejemplo de Respuesta `/explain`
```json
{
  "price": 350000.0,
  "shap_values": [15000.5, -8000.2, 5000.0, 25000.8],
  "base_value": 312999.9,
  "feature_names": ["bed", "bath", "acre_lot", "house_size"],
  "feature_values": [3.0, 2.0, 0.25, 1800.0]
}
```

## 📂 Estructura del Proyecto

```
.
├── apps/
│   ├── airflow/
│   │   ├── dags/                 # DAGs de Airflow
│   │   │   ├── mlops_pipeline.py # DAG principal
│   │   │   └── src/              # Scripts de ML
│   │   │       ├── data_loader.py
│   │   │       ├── preprocessing.py
│   │   │       ├── drift_detection.py
│   │   │       └── model_training.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── api/
│   │   ├── src/main.py           # FastAPI con /predict y /explain
│   │   ├── k8s/deployment.yaml
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/app.py            # Streamlit con SHAP visualization
│       ├── k8s/deployment.yaml
│       ├── Dockerfile
│       └── requirements.txt
├── infra/
│   ├── argocd/
│   │   ├── applications/
│   │   │   └── core-apps.yaml    # Todas las aplicaciones Argo CD
│   │   └── install/
│   │       └── install.yaml      # Manifiestos de Argo CD
│   └── manifests/
│       ├── services/             # NodePort services
│       └── setup/                # Jobs de inicialización
├── scripts/
│   ├── start_mlops.sh            # 🚀 Script principal
│   ├── create_cluster.sh
│   └── bootstrap_argocd.sh
├── DEPLOYMENT_LOG.md             # Bitácora detallada
└── README.md
```

## 🧪 Testing del Pipeline

### 1. Ejecutar el DAG manualmente

```bash
# Trigger desde CLI
kubectl exec -n mlops $(kubectl get pods -n mlops -l component=scheduler -o jsonpath="{.items[0].metadata.name}") \
  -c scheduler -- airflow dags trigger mlops_full_pipeline
```

O desde la UI de Airflow: http://localhost:30080

### 2. Probar la API

```bash
# Predicción
curl -X POST http://localhost:30800/predict \
  -H "Content-Type: application/json" \
  -d '{"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1800}'

# Explicación SHAP
curl -X POST http://localhost:30800/explain \
  -H "Content-Type: application/json" \
  -d '{"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1800}'

# Health check
curl http://localhost:30800/health

# Recargar modelo
curl -X POST http://localhost:30800/reload
```

### 3. Usar el Frontend

1. Acceder a http://localhost:30501
2. Tab "Predict Price": Llenar formulario y obtener predicción
3. Tab "SHAP Explanation": Ver contribución de cada feature
4. Tab "Model Info": Ver estado del modelo y métricas

## 🛠 Comandos Útiles

### Gestión del Cluster
```bash
# Ver todos los pods
kubectl get pods -A

# Ver aplicaciones de Argo CD
kubectl get apps -n argocd

# Logs del scheduler de Airflow
kubectl logs -n mlops -l component=scheduler -c scheduler -f

# Logs de MLflow
kubectl logs -n mlops -l app.kubernetes.io/name=mlflow -f

# Detener cluster (conserva datos)
k3d cluster stop mlops-cluster

# Eliminar cluster
k3d cluster delete mlops-cluster
```

### Debugging
```bash
# Shell en un pod
kubectl exec -it <pod-name> -n mlops -- /bin/bash

# Ver eventos recientes
kubectl get events -n mlops --sort-by='.lastTimestamp' | tail -20

# Describir pod problemático
kubectl describe pod <pod-name> -n mlops

# Ver datos en S3
kubectl exec -n mlops <scheduler-pod> -c scheduler -- python3 -c "
import boto3
s3 = boto3.client('s3', endpoint_url='http://seaweedfs-s3.mlops.svc:8333', 
                  aws_access_key_id='any', aws_secret_access_key='any')
for bucket in s3.list_buckets()['Buckets']:
    print(bucket['Name'])
"
```

## 🔄 CI/CD Pipeline

### GitHub Actions
El workflow `.github/workflows/ci.yaml` se ejecuta en cada push a `main`:

1. Build de imágenes Docker (airflow, api, frontend)
2. Tag con `github.sha` y `latest`
3. Push a Docker Hub

### Configuración de Secretos
En GitHub → Settings → Secrets:
- `DOCKERHUB_USERNAME`: Usuario de Docker Hub
- `DOCKERHUB_TOKEN`: Token de acceso

### Actualización de Imágenes
```bash
# Forzar actualización de deployments
kubectl rollout restart deployment/api -n mlops
kubectl rollout restart deployment/frontend -n mlops
```

## 🐛 Troubleshooting

### Pods en CrashLoopBackOff
```bash
kubectl logs <pod-name> -n mlops --previous
kubectl describe pod <pod-name> -n mlops
```

### Argo CD no sincroniza
```bash
# Hard refresh
kubectl delete application <app-name> -n argocd
kubectl apply -f infra/argocd/applications/core-apps.yaml
```

### MLflow no guarda artefactos
```bash
# Verificar buckets S3
kubectl exec -n mlops <scheduler-pod> -c scheduler -- python3 -c "
import boto3
s3 = boto3.client('s3', endpoint_url='http://seaweedfs-s3.mlops.svc:8333',
                  aws_access_key_id='any', aws_secret_access_key='any')
print([b['Name'] for b in s3.list_buckets()['Buckets']])
"
# Debe mostrar: ['airflow-logs', 'data-raw', 'mlflow-artifacts']
```

### API no carga modelo
```bash
# Verificar que hay artefactos
curl http://localhost:30800/health

# Forzar recarga
curl -X POST http://localhost:30800/reload
```

## 📚 Referencias

- [K3d Documentation](https://k3d.io/)
- [Argo CD Documentation](https://argo-cd.readthedocs.io/)
- [Apache Airflow](https://airflow.apache.org/)
- [MLflow](https://mlflow.org/)
- [SHAP Documentation](https://shap.readthedocs.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Streamlit](https://streamlit.io/)

## 👥 Autor

David Moreno - Proyecto Final MLOps 2025

## 📄 Licencia

Este proyecto es parte de un trabajo académico.
