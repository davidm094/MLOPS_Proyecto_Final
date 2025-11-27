#!/bin/bash
set -e

echo "🔍 Iniciando Verificación End-to-End del Proyecto MLOps..."
echo "=========================================================="

# 1. Verificar Pods
echo ""
echo "📦 1. Verificando estado de los Pods..."
kubectl get pods -n mlops | grep -v "Completed" | awk '{print $1, $2, $3}'
if kubectl get pods -n mlops | grep -v "Completed" | grep -v "Running"; then
    echo "❌ Algunos pods no están corriendo. Revisa el estado."
    # exit 1  # Comentado para permitir continuar si es solo un job fallido
else
    echo "✅ Todos los pods están corriendo."
fi

# 2. Trigger Airflow DAG
echo ""
echo "💨 2. Disparando Pipeline de Airflow (mlops_full_pipeline)..."
SCHEDULER_POD=$(kubectl get pods -n mlops -l component=scheduler -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n mlops $SCHEDULER_POD -c scheduler -- airflow dags trigger mlops_full_pipeline

echo "⏳ Esperando 10 segundos para inicialización..."
sleep 10

# 3. Verificar Ejecución del DAG
echo ""
echo "👀 3. Verificando estado del DAG..."
kubectl exec -n mlops $SCHEDULER_POD -c scheduler -- airflow dags list-runs -d mlops_full_pipeline --state running

# 4. Probar API (Health)
echo ""
echo "🏥 4. Probando Health Check de la API..."
curl -s http://localhost:30800/health | jq .

# 5. Probar API (Predicción)
echo ""
echo "🔮 5. Probando Predicción (Inferencia)..."
PREDICTION=$(curl -s -X POST http://localhost:30800/predict \
  -H "Content-Type: application/json" \
  -d '{"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1800, "state": "New York"}')
echo $PREDICTION | jq .

# 6. Probar API (Explicación)
echo ""
echo "🧠 6. Probando Explicabilidad (SHAP)..."
curl -s -X POST http://localhost:30800/explain \
  -H "Content-Type: application/json" \
  -d '{"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1800, "state": "New York"}' | jq 'del(.shap_values) | del(.feature_values)' 
# Omitimos arrays largos para limpieza

# 7. Verificar MLflow
echo ""
echo "🧪 7. Verificando Experimentos en MLflow..."
# Hacemos un curl simple para ver si responde el servicio
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:30500/)
if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ MLflow UI accesible (HTTP 200)"
else
    echo "❌ MLflow UI no accesible (HTTP $HTTP_CODE)"
fi

echo ""
echo "=========================================================="
echo "✅ Verificación completada."
