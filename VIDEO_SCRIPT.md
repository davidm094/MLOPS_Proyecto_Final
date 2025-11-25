# Guión para Video de Sustentación - MLOps Proyecto Final

**Duración máxima:** 10 minutos  
**Formato:** YouTube (público o no listado)

---

## 📋 Checklist de Requisitos de Entrega

### Requisitos Obligatorios

| # | Requisito | Estado | Evidencia |
|---|-----------|--------|-----------|
| 1 | Código fuente en repositorio público | ✅ | https://github.com/davidm094/MLOPS_Proyecto_Final |
| 2 | Workflows en GitHub Actions funcionales | ✅ | `.github/workflows/ci.yaml` - Build de 3 imágenes |
| 3 | Despliegue mediante Argo CD | ✅ | 7 aplicaciones gestionadas en namespace `argocd` |
| 4 | MLflow con bucket y base de datos | ✅ | PostgreSQL + SeaweedFS S3 |
| 5 | Inferencia toma modelo de "producción" sin cambios de código | ✅ | API carga último modelo de S3 automáticamente |
| 6 | Recolección/procesamiento/entrenamiento con Airflow | ✅ | DAG `mlops_full_pipeline` |
| 7 | Explicación de por qué se da el entrenamiento (más allá de periodicidad) | ✅ | **Data Drift Detection** con test KS |
| 8 | Video en YouTube ≤ 10 minutos | ⏳ | Por grabar |

### Contenido del Video (según enunciado)

| # | Sección | Tiempo Sugerido |
|---|---------|-----------------|
| 1 | Organización del proyecto | 1:30 min |
| 2 | Arquitectura y conexiones entre componentes | 2:00 min |
| 3 | Procesamiento y experimentación realizada | 2:00 min |
| 4 | Interfaz gráfica para inferencia | 1:30 min |
| 5 | Cambios entre versiones de modelos con explicación | 1:30 min |
| 6 | Ejecución de workflows de GitHub Actions | 1:30 min |
| **Total** | | **10:00 min** |

---

## 🎬 GUIÓN DEL VIDEO

### INTRO (0:00 - 0:30)

**[Pantalla: Título del proyecto]**

> "Hola, soy David Moreno y este es mi proyecto final de Operaciones de Machine Learning. 
> He implementado una plataforma MLOps End-to-End desplegada completamente en Kubernetes, 
> cumpliendo con todos los requisitos del proyecto incluyendo el Bono opcional."

---

### SECCIÓN 1: Organización del Proyecto (0:30 - 2:00)

**[Pantalla: GitHub Repository]**

> "El proyecto está organizado como un monorepo en GitHub. Veamos la estructura:"

**Mostrar en pantalla:**
```
MLOPS_Proyecto_Final/
├── apps/                    # Aplicaciones
│   ├── airflow/dags/        # DAGs y scripts de ML
│   ├── api/                 # FastAPI
│   └── frontend/            # Streamlit
├── infra/                   # Infraestructura como código
│   ├── argocd/applications/ # Definiciones de Argo CD
│   └── manifests/           # Manifiestos Kubernetes
├── scripts/                 # Scripts de despliegue
└── .github/workflows/       # CI con GitHub Actions
```

> "Cada componente tiene su propio Dockerfile y se despliega de forma independiente.
> Los DAGs de Airflow están en `apps/airflow/dags/` y se sincronizan automáticamente 
> con el cluster mediante Git-Sync."

---

### SECCIÓN 2: Arquitectura y Conexiones (2:00 - 4:00)

**[Pantalla: Diagrama de arquitectura]**

> "La arquitectura sigue el patrón GitOps. Veamos los componentes:"

**Mostrar diagrama y explicar:**

```
┌─────────────────────────────────────────────────────────────┐
│                     K3d CLUSTER                              │
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │ Argo CD │    │ Airflow │    │ MLflow  │    │SeaweedFS│  │
│  │ (GitOps)│    │(Pipeline)│   │(Tracking)│   │  (S3)   │  │
│  └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘  │
│       │              │              │              │        │
│       └──────────────┴──────────────┴──────────────┘        │
│                          │                                   │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                 │
│  │ FastAPI │◄───│Streamlit│    │PostgreSQL│                 │
│  │  (API)  │    │  (UI)   │    │(Metadata)│                 │
│  └─────────┘    └─────────┘    └─────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

> "1. **Argo CD** observa el repositorio de Git y sincroniza el estado del cluster.
> 2. **Airflow** orquesta el pipeline de ML con KubernetesExecutor.
> 3. **MLflow** registra experimentos, métricas y modelos.
> 4. **SeaweedFS** proporciona almacenamiento S3-compatible para artefactos.
> 5. **PostgreSQL** almacena metadatos de MLflow y Airflow.
> 6. **FastAPI** sirve el modelo para inferencia.
> 7. **Streamlit** proporciona la interfaz gráfica."

**[Pantalla: Argo CD UI]**

> "Aquí vemos Argo CD con todas las aplicaciones sincronizadas y saludables."

**Comando para mostrar:**
```bash
kubectl get apps -n argocd
```

---

### SECCIÓN 3: Procesamiento y Experimentación (4:00 - 6:00)

**[Pantalla: Airflow UI]**

> "El pipeline de ML está implementado como un DAG en Airflow. Tiene 4 tareas principales:"

**Mostrar DAG y explicar:**

```
start → ingest_data → check_drift → [train_model | end_pipeline]
```

> "1. **ingest_data**: Descarga datos de la API externa y los guarda en S3.
> 2. **check_drift**: Compara los datos nuevos con los de referencia usando el test de Kolmogorov-Smirnov.
> 3. **train_model**: Se ejecuta SOLO si se detecta drift estadístico significativo.
> 4. **end_pipeline**: Marca el fin del pipeline."

**[Pantalla: Código de drift_detection.py]**

> "Aquí está la clave del proyecto: el entrenamiento NO es periódico ni por cantidad de datos.
> Se entrena SOLO cuando hay Data Drift - cuando la distribución estadística de los datos
> cambia significativamente. Usamos el test de Kolmogorov-Smirnov con p-value < 0.05."

```python
from scipy.stats import ks_2samp
statistic, p_value = ks_2samp(ref_data, curr_data)
if p_value < p_value_threshold:
    drift_detected = True
```

**[Pantalla: MLflow UI]**

> "Cada entrenamiento se registra en MLflow con métricas como RMSE y R².
> Los modelos y el SHAP Explainer se guardan como artefactos en S3."

---

### SECCIÓN 4: Interfaz Gráfica para Inferencia (6:00 - 7:30)

**[Pantalla: Streamlit UI - Tab Predict]**

> "La interfaz de Streamlit permite realizar predicciones de forma interactiva.
> Ingresamos las características de una propiedad:"

**Demo en vivo:**
- Bed: 3
- Bath: 2
- Acre Lot: 0.25
- House Size: 1800

> "Al hacer clic en 'Predict', la aplicación llama a la API de FastAPI
> y muestra el precio predicho junto con métricas adicionales."

**[Pantalla: Streamlit UI - Tab SHAP]**

> "En la pestaña de SHAP Explanation, vemos cómo cada feature contribuye al precio.
> Las barras rojas aumentan el precio, las verdes lo disminuyen.
> Por ejemplo, tener solo 2 baños reduce el precio en casi $184,000 respecto al promedio."

**[Pantalla: Respuesta de API /explain]**

```json
{
  "price": 860129.46,
  "shap_values": [7874.74, -183896.72, -1301.69, -94446.21],
  "base_value": 1131899.34,
  "feature_names": ["bed", "bath", "acre_lot", "house_size"]
}
```

---

### SECCIÓN 5: Cambios entre Versiones de Modelos (7:30 - 9:00)

**[Pantalla: API endpoint /reload]**

> "El sistema está diseñado para que los cambios de modelo NO requieran cambios de código.
> Cuando se entrena un nuevo modelo, se guarda en S3. La API puede recargar el modelo
> con un simple POST a /reload."

**Demo en vivo:**
```bash
# Ver modelo actual
curl http://localhost:30800/

# Recargar modelo (si hay uno nuevo)
curl -X POST http://localhost:30800/reload
```

> "La API automáticamente carga el modelo más reciente del bucket de MLflow.
> No hay que modificar código, ni hacer redeploy, ni cambiar tags."

**[Pantalla: Explicación del mecanismo]**

> "¿Por qué se entrena un nuevo modelo? NO es por periodicidad ni por cantidad de datos.
> Es por DATA DRIFT. Cuando la distribución estadística de los datos nuevos
> difiere significativamente de los datos de referencia, el test KS detecta el drift
> y dispara el entrenamiento automáticamente."

**Mostrar log de Airflow:**
```
Drift detected in feature: price (p-value: 0.001)
Proceeding to training...
```

---

### SECCIÓN 6: GitHub Actions Workflows (9:00 - 10:00)

**[Pantalla: GitHub Actions]**

> "El CI está implementado con GitHub Actions. Cada push a la rama main
> que modifica archivos en `apps/` dispara el workflow."

**Mostrar workflow:**
```yaml
on:
  push:
    branches: [ main ]
    paths:
      - 'apps/**'
```

> "El workflow construye 3 imágenes Docker en paralelo: airflow, api y frontend.
> Las publica en DockerHub con dos tags: el SHA del commit y 'latest'."

**[Pantalla: DockerHub]**

> "Aquí vemos las imágenes publicadas en DockerHub:
> - davidm094/mlops-airflow
> - davidm094/mlops-api
> - davidm094/mlops-frontend"

**[Pantalla: Ejecución exitosa del workflow]**

> "Y aquí vemos una ejecución exitosa del workflow, con los 3 jobs completados."

---

### CIERRE (9:45 - 10:00)

**[Pantalla: Resumen]**

> "En resumen, este proyecto implementa una plataforma MLOps completa:
> - GitOps con Argo CD
> - Orquestación con Airflow
> - Tracking con MLflow
> - Inferencia con FastAPI
> - UI con Streamlit
> - Interpretabilidad con SHAP
> - CI/CD con GitHub Actions
> 
> Todo desplegado en Kubernetes cumpliendo con el Bono del proyecto.
> Gracias por su atención."

---

## 📝 NOTAS PARA LA GRABACIÓN

### Preparación antes de grabar:

1. **Verificar que todos los servicios estén corriendo:**
   ```bash
   kubectl get pods -n mlops
   kubectl get apps -n argocd
   ```

2. **Abrir en pestañas del navegador:**
   - Argo CD: http://localhost:30443
   - Airflow: http://localhost:30080
   - MLflow: http://localhost:30500
   - Frontend: http://localhost:30501
   - GitHub repo: https://github.com/davidm094/MLOPS_Proyecto_Final
   - GitHub Actions: https://github.com/davidm094/MLOPS_Proyecto_Final/actions

3. **Tener terminal lista con comandos:**
   ```bash
   # Para mostrar pods
   kubectl get pods -n mlops
   
   # Para mostrar apps de Argo CD
   kubectl get apps -n argocd
   
   # Para probar API
   curl http://localhost:30800/
   curl -X POST http://localhost:30800/predict -H "Content-Type: application/json" \
     -d '{"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1800}'
   ```

### Tips para el video:

1. **Hablar claro y pausado** - 10 minutos es suficiente si no te apresuras
2. **Mostrar pantalla completa** cuando muestres UIs
3. **Usar zoom** en código importante
4. **Pausar brevemente** después de cada sección
5. **Tener backup** de screenshots por si algo falla en vivo

### Herramientas sugeridas para grabar:

- **OBS Studio** (gratis, multiplataforma)
- **Loom** (fácil de usar, sube directo)
- **Zoom** (grabación local)

---

## 🔗 URLs para el Video

| Servicio | URL |
|----------|-----|
| GitHub Repo | https://github.com/davidm094/MLOPS_Proyecto_Final |
| GitHub Actions | https://github.com/davidm094/MLOPS_Proyecto_Final/actions |
| DockerHub | https://hub.docker.com/u/davidm094 |
| Argo CD (local) | http://localhost:30443 |
| Airflow (local) | http://localhost:30080 |
| MLflow (local) | http://localhost:30500 |
| API (local) | http://localhost:30800 |
| Frontend (local) | http://localhost:30501 |

---

## ⚠️ PUNTO CRÍTICO A ENFATIZAR

**El requisito más importante que debes explicar claramente:**

> "Cada nuevo entrenamiento después del creado con la línea base debe estar acompañado 
> de una explicación de por qué se da el entrenamiento más allá de un factor de 
> periodicidad o cantidad de datos nuevos."

**Tu respuesta:**

> "El entrenamiento se dispara por **Data Drift** - cambios estadísticos significativos 
> en la distribución de los datos. Usamos el test de Kolmogorov-Smirnov para comparar 
> los datos nuevos con los de referencia. Si el p-value es menor a 0.05, significa que 
> la distribución cambió significativamente y el modelo actual podría no ser válido 
> para los nuevos datos. Por eso se reentrena."

---

*Documento creado para preparación del video de sustentación - MLOps 2025*

