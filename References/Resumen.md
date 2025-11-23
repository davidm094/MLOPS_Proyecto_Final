Esta es la documentación técnica consolidada y optimizada para tu proyecto final de MLOps. Este documento integra los requerimientos originales del PDF, las especificaciones del "Bono" (Kubernetes/GitOps) y las recomendaciones técnicas para el despliegue en tus VMs con Rocky Linux.

Puedes guardar este contenido como `PROJECT_SPECS.md` en la raíz de tu repositorio para que Cursor (y cualquier desarrollador) tenga el contexto completo.

---

# Especificación Técnica: Proyecto Final MLOps (End-to-End con Kubernetes & GitOps)

**Fecha:** Noviembre 2025
**Nivel:** Avanzado (Incluye Bonus de Despliegue K8s)
**Infraestructura Objetivo:** Cluster K3s sobre 1-3 VMs (Rocky Linux)

## 1. Resumen Ejecutivo
El objetivo es diseñar, desarrollar y desplegar una plataforma MLOps completa que automatice el ciclo de vida de un modelo de aprendizaje automático. El sistema debe ser capaz de ingerir datos, detectar cambios en su distribución (Data Drift), reentrenar automáticamente, promover el mejor modelo y desplegarlo en producción sin intervención manual, utilizando una arquitectura **Cloud-Native** sobre Kubernetes gestionada por **Argo CD**.

## 2. Stack Tecnológico

| Dominio | Herramienta | Función |
| :--- | :--- | :--- |
| **Infraestructura** | **K3s** | Orquestador Kubernetes ligero (Server + Agents). |
| **Despliegue (CD)** | **Argo CD** | GitOps Operator para gestión del estado del clúster. |
| **Empaquetado** | **Helm** | Gestión de aplicaciones K8s mediante Charts. |
| **Orquestación ML**| **Apache Airflow** | Gestión de pipelines (ETL, Drift, Training). |
| **Experimentos** | **MLflow** | Tracking de métricas, parámetros y registro de modelos. |
| **Almacenamiento** | **MinIO** | Object Storage (S3 Compatible) para artefactos y logs. |
| **Base de Datos** | **PostgreSQL** | Backend para Airflow y MLflow. |
| **API Inferencia** | **FastAPI** | Servicio REST para consumo del modelo. |
| **Frontend** | **Streamlit** | Interfaz de usuario para predicción e interpretabilidad. |
| **Observabilidad** | **Prometheus + Grafana** | Monitoreo de infraestructura y métricas. |
| **CI** | **GitHub Actions** | Construcción y publicación de imágenes Docker. |

---

## 3. Requerimientos Funcionales (El Pipeline MLOps)

El sistema debe implementar un flujo continuo automatizado que cumpla con los siguientes pasos:

### 3.1. Ingesta y Detección (Airflow)
* **Fuente de Datos:** Consumir datos de la API del profesor: `http://10.43.100.103:8000`.
* **Trigger de Entrenamiento:** El sistema no debe entrenar ciegamente. Debe implementar un mecanismo de **Detección de Data Drift** (ej. usando *Evidently AI* o pruebas estadísticas como Kolmogorov-Smirnov).
    * *Lógica:* Si `Drift Detectado` == `True` $\rightarrow$ Iniciar Pipeline de Entrenamiento.
    * *Lógica:* Si `Drift Detectado` == `False` $\rightarrow$ Terminar ejecución.

### 3.2. Entrenamiento y Registro (Airflow + MLflow)
* **Experiment Tracking:** Cada ejecución de entrenamiento debe registrar en MLflow:
    * Parámetros del modelo (hiperparámetros).
    * Métricas de desempeño (Accuracy, F1, RMSE, etc.).
    * Artefacto del modelo serializado.
* **Estrategia de Promoción:** El pipeline debe comparar el modelo recién entrenado contra el modelo actual en "Production".
    * Si `Nueva Métrica` > `Métrica Actual` $\rightarrow$ Marcar nuevo modelo con alias/stage "Production".

### 3.3. Inferencia (FastAPI)
* La API debe servir el modelo marcado como "Production" en MLflow.
* **Carga Dinámica:** Idealmente, la API debe ser capaz de cargar la nueva versión del modelo sin requerir una recompilación del contenedor (o usar Argo CD para redestplegar el pod al detectar una nueva versión).
* **Endpoints Requeridos:**
    * `POST /predict`: Recibe features, devuelve predicción.
    * `POST /explain`: Recibe features, devuelve valores SHAP (ver punto 3.4).

### 3.4. Interfaz de Usuario e Interpretabilidad (Streamlit)
* Formulario amigable para ingresar datos de prueba.
* Visualización clara de la predicción.
* **Requerimiento Crítico (Bono):** Integrar **SHAP (SHapley Additive exPlanations)**.
    * La UI debe mostrar gráficamente qué variables influyeron más en la decisión del modelo (ej. gráfico de barras de importancia o waterfall plot).

---

## 4. Requerimientos Técnicos de Despliegue (El "Bono" K8s)

El despliegue debe seguir estrictamente la metodología **GitOps**. No se permiten comandos `kubectl apply` manuales para los servicios principales.

### 4.1. Estrategia GitOps & Argo CD
* Toda la configuración del clúster (Deployments, Services, Ingress, ConfigMaps) debe residir en un repositorio Git.
* Argo CD debe estar configurado para sincronizar el estado del clúster con este repositorio.

### 4.2. Requerimientos Específicos de Helm Charts
Todos los componentes deben ser desplegados vía Helm. Se deben cumplir estas configuraciones específicas:

1.  **Airflow con Git-Sync:**
    * No se deben "quemar" los DAGs en la imagen Docker.
    * Se debe configurar el sidecar `git-sync` en el Helm Chart de Airflow para que lea los DAGs dinámicamente desde un repositorio Git privado/público.
    * *Complemento:* Configurar correctamente el `known_hosts` y las llaves SSH (Secrets) para la conexión segura.

2.  **MinIO con Auto-Buckets:**
    * MinIO debe inicializarse y **crear automáticamente** los buckets necesarios (`mlflow-artifacts`, `airflow-logs`) si no existen.
    * *Implementación:* Usar la propiedad `defaultBuckets` del chart de Bitnami o un `job` post-install de Kubernetes.

3.  **Grafana "Zero-Touch":**
    * El dashboard de monitoreo no debe importarse manualmente.
    * Se debe usar el patrón **Sidecar** de Grafana: Crear un `ConfigMap` en Kubernetes con el JSON del dashboard y una etiqueta específica (ej. `grafana_dashboard: "1"`) para que Grafana lo aprovisione al iniciar.

4.  **Actualización de Imágenes (CI/CD):**
    * Un cambio en el código de la API (GitHub) debe disparar un GitHub Action que construya la imagen y la suba a un Registry.
    * Argo CD (con Image Updater o via commit automático al repo de configuración) debe detectar el nuevo tag y actualizar el despliegue en el clúster.

---

## 5. Arquitectura de Infraestructura (VMs)

Para tu configuración específica de Rocky Linux (1, 2 o 3 VMs), se recomienda la siguiente topología con **K3s**:

* **Escenario 1 VM:** Nodo único (Server + Agent).
* **Escenario 2 VMs:** 1 Server (Control Plane + DBs) + 1 Agent (Cargas de trabajo ML pesadas).
* **Escenario 3 VMs:** 1 Server (Control Plane) + 2 Agents (Workers).

**Configuración de Red:**
* Asegurar que los puertos necesarios (NodePorts o LoadBalancer vía MetalLB si se configura) sean accesibles entre las VMs.
* Ingress Controller (Traefik o Nginx) para enrutar el tráfico a:
    * `airflow.tu-dominio`
    * `mlflow.tu-dominio`
    * `api.tu-dominio`
    * `argocd.tu-dominio`

---

## 6. Entregables del Proyecto

1.  **Repositorios de Código:**
    * Repo de Aplicación (Código Python, Dockerfiles, Tests).
    * Repo de Infraestructura/GitOps (Helm Charts, Argo Apps).
2.  **Video Demo (Max 5 min):**
    * Explicación de la arquitectura.
    * Demostración del pipeline ejecutándose (Airflow).
    * Demostración del cambio automático (CI/CD) o re-entrenmaiento.
    * Uso de la UI y explicación SHAP.
3.  **URL de Acceso:** Link funcional a la aplicación Streamlit.

---

## 7. Recomendaciones Adicionales ("Pro-Tips" para Cursor)

Para asegurar el éxito y mejorar la calidad del código generado por Cursor, ten en cuenta:

* **Gestión de Secretos:** NO subir contraseñas al Git. Utiliza `Secrets` de Kubernetes. Cursor debe generar templates donde los valores sensibles vengan de `env variables`.
* **Persistencia:** Asegura que PostgreSQL y MinIO tengan `PersistentVolumeClaims` (PVCs) configurados. Si reinicias el clúster K3s, no deberías perder los datos de entrenamiento.
* **Resource Quotas:** Define `requests` y `limits` de CPU/RAM en tus Helm Charts para evitar que el entrenamiento del modelo bloquee la API o Airflow, especialmente si usas pocas VMs.
* **Namespace Isolation:** Despliega ArgoCD en `argocd`, las herramientas de monitoreo en `monitoring`, y tu aplicación MLOps en un namespace dedicado (ej. `mlops-prod`).