#!/bin/bash
set -e

echo "🧹 Limpiando cluster existente..."
if k3d cluster list | grep -q "mlops-cluster"; then
    k3d cluster delete mlops-cluster
    echo "✅ Cluster anterior eliminado"
fi

echo ""
echo "☸️  Creando nuevo cluster K3d con configuración optimizada..."
echo "   - Traefik habilitado (integrado de K3d)"
echo "   - Puertos mapeados: 80, 443, 8080 (Airflow), 5000 (MLflow)"
echo ""

k3d cluster create mlops-cluster \
    --api-port 6443 \
    -p "80:80@loadbalancer" \
    -p "443:443@loadbalancer" \
    -p "8080:8080@loadbalancer" \
    -p "5000:5000@loadbalancer" \
    -p "8501:8501@loadbalancer" \
    --agents 1

echo ""
echo "⏳ Esperando a que el cluster esté listo..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

echo ""
echo "🔌 Configurando contexto de kubectl..."
kubectl config use-context k3d-mlops-cluster

echo ""
echo "✅ Cluster K3d creado exitosamente!"
echo "---------------------------------------------------"
echo "📊 Información del Cluster:"
kubectl get nodes
echo "---------------------------------------------------"

