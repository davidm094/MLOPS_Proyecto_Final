#!/bin/bash
set -e

echo "🚀 Iniciando inicialización del Proyecto MLOps..."

# Definir raíz del proyecto
PROJECT_ROOT="."

# 1. Crear Estructura de Directorios
echo "📂 Creando estructura de directorios..."

# .github
mkdir -p $PROJECT_ROOT/.github/workflows

# apps
mkdir -p $PROJECT_ROOT/apps/airflow/dags/src
mkdir -p $PROJECT_ROOT/apps/api/src
mkdir -p $PROJECT_ROOT/apps/frontend/src

# infra
mkdir -p $PROJECT_ROOT/infra/argocd/applications
mkdir -p $PROJECT_ROOT/infra/argocd/install
mkdir -p $PROJECT_ROOT/infra/charts
mkdir -p $PROJECT_ROOT/infra/manifests/databases
mkdir -p $PROJECT_ROOT/infra/manifests/ingress
mkdir -p $PROJECT_ROOT/infra/manifests/secrets

# scripts (ya existe, pero por si acaso)
mkdir -p $PROJECT_ROOT/scripts

# 2. Generar Archivos Base
echo "📄 Generando archivos base..."

# __init__.py para paquetes python
touch $PROJECT_ROOT/apps/airflow/dags/__init__.py
touch $PROJECT_ROOT/apps/airflow/dags/src/__init__.py
touch $PROJECT_ROOT/apps/api/src/__init__.py
touch $PROJECT_ROOT/apps/frontend/src/__init__.py

# Dockerfiles Base (Placeholders)
# Airflow Custom Image
cat <<EOF > $PROJECT_ROOT/apps/airflow/Dockerfile
FROM apache/airflow:2.10.2
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
USER airflow
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
EOF

touch $PROJECT_ROOT/apps/airflow/requirements.txt

# API Dockerfile
cat <<EOF > $PROJECT_ROOT/apps/api/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

touch $PROJECT_ROOT/apps/api/requirements.txt

# Frontend Dockerfile
cat <<EOF > $PROJECT_ROOT/apps/frontend/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ .
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
EOF

touch $PROJECT_ROOT/apps/frontend/requirements.txt

# Values.yaml Placeholders
touch $PROJECT_ROOT/infra/charts/airflow-values.yaml
touch $PROJECT_ROOT/infra/charts/mlflow-values.yaml
touch $PROJECT_ROOT/infra/charts/minio-values.yaml

# README
if [ ! -f "$PROJECT_ROOT/README.md" ]; then
    echo "# MLOps Proyecto Final" > $PROJECT_ROOT/README.md
fi

# 3. Permisos de ejecución
chmod +x $PROJECT_ROOT/scripts/*.sh 2>/dev/null || true

echo "✅ Estructura generada exitosamente."

