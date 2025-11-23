#!/bin/bash
set -e

echo "🚀 Iniciando Setup de MLOps en WSL (K3d)..."

# 1. Verificar Requisitos
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no encontrado. Asegúrate de tener Docker Desktop corriendo."
    exit 1
fi

# 2. Instalar K3d (si no existe)
if ! command -v k3d &> /dev/null; then
    echo "📦 Instalando K3d..."
    wget -q -O - https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
else
    echo "✅ K3d ya está instalado."
fi

# 3. Instalar kubectl (si no existe)
if ! command -v kubectl &> /dev/null; then
    echo "📦 Instalando kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
fi

# 4. Crear Cluster
if k3d cluster list | grep -q "mlops-cluster"; then
    echo "♻️  El cluster 'mlops-cluster' ya existe. Borrando para iniciar limpio..."
    k3d cluster delete mlops-cluster
fi

echo "☸️  Creando cluster K3d 'mlops-cluster'..."
# Mapeamos puerto 80 y 443 del LoadBalancer de K3d al localhost de Windows
# Deshabilitamos traefik por defecto para usar el nuestro (o podemos usar el que trae k3d si es v2)
# K3d usa traefik por defecto. Vamos a usar --k3s-arg "--disable=traefik@server:0" para usar NUESTRO setup.
k3d cluster create mlops-cluster \
    --api-port 6443 \
    -p "80:80@loadbalancer" \
    -p "443:443@loadbalancer" \
    --agents 1 \
    --k3s-arg "--disable=traefik@server:0" \
    --volume "$(pwd)/data:/tmp/data" # Volumen para persistencia de datos locales si se necesita

echo "⏳ Esperando a que el cluster esté listo..."
kubectl wait --for=condition=Ready nodes --all --timeout=60s

# 5. Configurar Kubeconfig
echo "🔌 Configurando contexto..."
kubectl config use-context k3d-mlops-cluster

# 6. Bootstrap Argo CD
echo "🚀 Lanzando Bootstrap de Argo CD..."
./scripts/bootstrap_argocd.sh

echo "✅ ¡Cluster Listo en WSL!"
echo "---------------------------------------------------"
echo "🌐 Acceso:"
echo "   Argo CD: https://argocd.mlops.local (Configura tu DNS/Hosts)"
echo "   Airflow: http://airflow.mlops.local"
echo "   MLflow:  http://mlflow.mlops.local"
echo ""
echo "📝 Próximo Paso: Agrega esto a tu C:\Windows\System32\drivers\etc\hosts (en Windows):"
echo "   127.0.0.1  argocd.mlops.local airflow.mlops.local mlflow.mlops.local minio.mlops.local seaweedfs.mlops.local"
echo "---------------------------------------------------"

