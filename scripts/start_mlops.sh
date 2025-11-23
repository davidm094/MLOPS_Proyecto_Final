#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║          🚀 MLOps Platform - Automated Deployment 🚀          ║"
echo "║                                                                ║"
echo "║  End-to-End MLOps Platform with Kubernetes & GitOps           ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "🔍 Verificando prerequisitos..."
for cmd in docker kubectl k3d; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ Error: $cmd no está instalado."
        exit 1
    fi
done
echo "✅ Todos los prerequisitos están instalados."
echo ""

# Step 1: Create K3d Cluster
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PASO 1/5: Creando Cluster K3d"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./scripts/create_cluster.sh
echo ""

# Step 2: Bootstrap Argo CD
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PASO 2/5: Instalando Argo CD"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./scripts/bootstrap_argocd.sh
echo ""

# Step 3: Deploy Applications
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PASO 3/5: Desplegando Aplicaciones MLOps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl apply -f infra/argocd/applications/core-apps.yaml
echo "✅ Aplicaciones registradas en Argo CD"
echo ""

# Step 4: Wait for deployments
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PASO 4/5: Esperando a que los servicios estén listos..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Esto puede tomar 3-5 minutos..."
echo ""

# Wait for Argo CD to be healthy
echo "   🔄 Esperando Argo CD..."
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s

# Wait for infrastructure
echo "   🔄 Esperando PostgreSQL..."
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=postgresql -n mlops --timeout=300s 2>/dev/null || echo "   ⚠️  PostgreSQL aún no está listo (continuando...)"

echo "   🔄 Esperando SeaweedFS..."
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=seaweedfs -n mlops --timeout=300s 2>/dev/null || echo "   ⚠️  SeaweedFS aún no está listo (continuando...)"

# Wait for MLOps apps
echo "   🔄 Esperando Airflow..."
kubectl wait --for=condition=Ready pods -l component=webserver -n mlops --timeout=300s 2>/dev/null || echo "   ⚠️  Airflow aún no está listo (continuando...)"

echo "   🔄 Esperando MLflow..."
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=mlflow -n mlops --timeout=300s 2>/dev/null || echo "   ⚠️  MLflow aún no está listo (continuando...)"

echo ""
echo "✅ Servicios principales están levantando..."
echo ""

# Step 5: Display access information
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PASO 5/5: Información de Acceso"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 URLs de Acceso:"
echo "   ┌─────────────────────────────────────────────────────────┐"
echo "   │ Argo CD:    https://localhost                           │"
echo "   │ Airflow:    http://localhost:8080                       │"
echo "   │ MLflow:     http://localhost:5000                       │"
echo "   │ API:        http://localhost:8000                       │"
echo "   │ Frontend:   http://localhost:8501                       │"
echo "   └─────────────────────────────────────────────────────────┘"
echo ""
echo "🔑 Credenciales de Argo CD:"
echo "   Usuario: admin"
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)
if [ -n "$ARGOCD_PASSWORD" ]; then
    echo "   Password: $ARGOCD_PASSWORD"
else
    echo "   Password: (ejecuta el siguiente comando para obtenerla)"
    echo "   kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
fi
echo ""
echo "📊 Estado de las Aplicaciones:"
kubectl get apps -n argocd
echo ""
echo "🎯 Comandos Útiles:"
echo "   Ver todos los pods:       kubectl get pods -A"
echo "   Ver servicios:            kubectl get svc -n mlops"
echo "   Logs de Airflow:          kubectl logs -n mlops -l component=webserver"
echo "   Logs de MLflow:           kubectl logs -n mlops -l app.kubernetes.io/name=mlflow"
echo "   Detener cluster:          k3d cluster delete mlops-cluster"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║          ✅ ¡Plataforma MLOps Desplegada Exitosamente! ✅      ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "💡 Nota: Algunos servicios pueden tardar unos minutos adicionales"
echo "   en estar completamente listos. Verifica el estado en Argo CD."
echo ""

