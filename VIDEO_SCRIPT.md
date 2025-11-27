# Guión para Video de Sustentación - MLOps Proyecto Final

**Duración máxima:** 10 minutos  
**Formato:** YouTube (público o no listado)

---

##  Checklist de Requisitos de Entrega

### Requisitos Obligatorios

| # | Requisito | Estado | Evidencia |
|---|-----------|--------|-----------|
| 1 | Código fuente en repositorio público |  | https://github.com/davidm094/MLOPS_Proyecto_Final |
| 2 | Workflows en GitHub Actions funcionales |  | `.github/workflows/ci.yaml` - Build de 3 imágenes |
| 3 | Despliegue mediante Argo CD |  | 7 aplicaciones gestionadas en namespace `argocd` |
| 4 | MLflow con bucket y base de datos |  | PostgreSQL + SeaweedFS S3 |
| 5 | Inferencia toma modelo de "producción" sin cambios de código |  | API carga último modelo de S3 automáticamente |
| 6 | Recolección/procesamiento/entrenamiento con Airflow |  | DAG `mlops_full_pipeline` |
| 7 | Explicación de por qué se da el entrenamiento (más allá de periodicidad) |  | **Data Drift Detection** con test KS |
| 8 | Video en YouTube ≤ 10 minutos |  | Por grabar |

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

##  GUIÓN DEL VIDEO

### INTRO (0:00 - 0:30)

**[Pantalla: Título del proyecto]**

> "Hola, somos el Grupo 5 (Anderson Alvarado, David Moreno, Juan Peña) y este es nuestro proyecto final de Operaciones de Machine Learning. 
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
> 7. **Streamlit** proporciona la interfaz gráfica.
> 8. **Prometheus y Grafana** (Nuevo) monitorean la salud del sistema y métricas de negocio."

**[Pantalla: Argo CD UI]**

> "Aquí vemos Argo CD con todas las aplicaciones sincronizadas y saludables."

**Comando para mostrar:**
```bash
kubectl get apps -n argocd
```

---

---

### SECCIÓN 2.5: Observabilidad (4:00 - 4:30)

**[Pantalla: Grafana Dashboards]**

> "Un punto destacado es la observabilidad completa del sistema."

**[Acción: Mostrar Dashboard de MLOps API en Grafana]**

> "Implementamos Prometheus y Grafana para monitorear métricas críticas en tiempo real:
> - Latencia de predicción (p95)
> - Tasa de errores
> - Total de predicciones por estado
> - Estado de carga del modelo"

> "Esto nos permite detectar problemas proactivamente, no solo en la infraestructura, sino en el negocio."

### SECCIÓN 3: Procesamiento y Experimentación (4:00 - 6:00)

**[Pantalla: Airflow UI]**

> "Para demostrar la automatización, vamos a ejecutar el pipeline en vivo."

**[Acción: Click en el botón 'Trigger DAG' en Airflow]**

> "Mientras el pipeline se ejecuta, veamos sus componentes en la vista de Grafo:"

**Mostrar DAG y explicar:**

```
start → ingest_data → check_drift → [train_model | end_pipeline]
```

> "1. **ingest_data**: Descarga datos de la API externa y los guarda en S3.
> 2. **check_drift**: Compara los datos nuevos con los de referencia usando el test de Kolmogorov-Smirnov.
> 3. **train_model**: Se ejecuta SOLO si se detecta drift estadístico significativo.
> 4. **end_pipeline**: Marca el fin del pipeline."

**[Pantalla: Logs de la tarea check_drift]**

> "Entremos a los logs de la tarea de drift. Aquí es donde cumplimos el requisito de 'Entrenamiento Condicional'."

**Mostrar log resaltado:**
```
Drift detected in feature: price (p-value: 0.001)
Proceeding to training...
```

> "El sistema detecta matemáticamente que los datos han cambiado (p-value < 0.05) y decide re-entrenar automáticamente. No es por tiempo, es por datos."

---

### SECCIÓN 4: Interfaz Gráfica para Inferencia (6:00 - 7:30)
... (Mantener igual) ...

---

### SECCIÓN 5: Cambios entre Versiones de Modelos (7:30 - 9:00)

**[Pantalla: MLflow Model Registry]**

> "Ahora demostraremos el requisito: 'Inferencia toma modelo de producción sin cambios de código'."

**[Acción: Mostrar versión actual en MLflow (ej: v5) etiquetada como 'Production']**

> "Actualmente la API está sirviendo la versión 5. Supongamos que el pipeline anterior terminó y generó la versión 6."

**[Pantalla: Terminal dividida con API logs y comando curl]**

> "En lugar de redeployar el pod o cambiar el código, simplemente notificamos a la API."

**Demo en vivo:**
```bash
# 1. Verificar modelo actual
curl http://localhost:30800/model
# Respuesta: {"version": "5", "stage": "Production"}

# 2. Forzar recarga (Simulación de CD continuo)
curl -X POST http://localhost:30800/reload

# 3. Logs de la API muestran:
# "Loading Production model version 5... Success"
```

> "La API descarga 'en caliente' el artefacto marcado como Production en MLflow. 
> Esto garantiza que el modelo en servicio siempre es el correcto sin detener el servicio."

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

##  NOTAS PARA LA GRABACIÓN

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
   curl http://localhost:30800/ready  # Verificar health check
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

##  URLs para el Video

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
| Grafana (local) | http://localhost:30300 |
| Prometheus (local) | http://localhost:30090 |
| Frontend (local) | http://localhost:30501 |

---

##  PUNTO CRÍTICO A ENFATIZAR

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

---

## Apéndice: Matriz de Cumplimiento (Para tu tranquilidad)

Usa esta tabla para asegurarte de que has cubierto todo mientras grabas:

| Requisito | Dónde se demuestra en el video | Acción Clave |
|-----------|--------------------------------|--------------|
| **1. Código Público** | Sección 1 (0:30) | Mostrar repo de GitHub en pantalla. |
| **2. GitHub Actions** | Sección 6 (9:00) | Mostrar pestaña "Actions" con checks verdes. |
| **3. Argo CD** | Sección 2 (2:00) | Mostrar UI de Argo con apps "Synced/Healthy". |
| **4. MLflow (DB+S3)** | Sección 3 (5:30) | Mostrar UI de MLflow y mencionar "Artefactos en S3". |
| **5. Inferencia sin cambios** | Sección 5 (7:30) | Ejecutar `curl /reload` y mostrar logs de "Loading model". |
| **6. Airflow Pipeline** | Sección 3 (4:00) | **Hacer click en Trigger** y mostrar Graph View. |
| **7. Explicación Drift** | Sección 3 (5:00) | Mostrar logs de `check_drift` o código de `ks_2samp`. |

*Si cubres estos 7 puntos visualmente, el proyecto es inobjetable.*

---

*Documento creado para preparación del video de sustentación - MLOps 2025*

