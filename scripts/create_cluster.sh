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
echo "   - Puertos mapeados directamente a servicios NodePort"
echo ""

# Crear cluster con mapeo EXPLÍCITO de puertos NodePort a localhost
k3d cluster create mlops-cluster \
    --api-port 6443 \
    -p "30080:30080@server:0" \
    -p "30443:30443@server:0" \
    -p "30800:30800@server:0" \
    -p "30500:30500@server:0" \
    -p "30501:30501@server:0" \
    -p "30090:30090@server:0" \
    -p "30300:30300@server:0" \
    -p "30903:30903@server:0" \
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
echo ""
echo "📝 Puertos mapeados:"
echo "   30080 → Airflow"
echo "   30443 → Argo CD"
echo "   30800 → API"
echo "   30500 → MLflow"
echo "   30501 → Frontend"
echo "   30090 → Prometheus"
echo "   30300 → Grafana"
echo "   30903 → AlertManager"
echo "---------------------------------------------------"
