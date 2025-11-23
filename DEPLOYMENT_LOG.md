# Bitácora de Despliegue - Proyecto Final MLOps

Este documento registra cronológicamente el progreso, los desafíos encontrados, las soluciones aplicadas (fixes) y las decisiones de arquitectura tomadas durante el despliegue de la plataforma en el entorno Bare Metal (Rocky Linux 9).

## 📅 Hitos del Despliegue

### 1. Inicialización y Estructura del Proyecto
- **Estado:** ✅ Completado
- **Acción:** Se diseñó una estructura de Monorepo para soportar GitOps.
- **Detalle:**
    - `apps/`: Código fuente (Airflow, API, Frontend).
    - `infra/`: Manifiestos Kubernetes y Helm Charts.
    - `scripts/`: Automatización de host y bootstrap.

### 2. Preparación del Host (VM Rocky Linux)
- **Estado:** ✅ Completado
- **Reto:** Conflicto de direcciones IP. La VM tiene la IP `10.43.100.94`, que entra en conflicto con el CIDR por defecto de K3s (`10.43.0.0/16`).
- **Solución:** Se implementó `scripts/setup_host.sh` instalando K3s con CIDRs personalizados:
    - Pod CIDR: `10.44.0.0/16`
    - Service CIDR: `10.45.0.0/16`
    - DNS IP: `10.45.0.10`
- **Fix Adicional:** Se instaló `iscsi-initiator-utils` y se deshabilitó `firewalld` para permitir el funcionamiento de Longhorn y la comunicación entre pods.

### 3. Bootstrap de Argo CD
- **Estado:** ✅ Completado
- **Reto:** La VM tiene restricciones de red que bloquean el acceso directo a `raw.githubusercontent.com`, impidiendo la instalación remota de Argo CD.
- **Solución:** Se descargó el manifiesto `install.yaml` oficial, se agregó al repositorio (`infra/argocd/install/install.yaml`) y se modificó el script de bootstrap para aplicar el archivo localmente.
- **Resultado:** Argo CD desplegado y accesible.

### 4. Capa de Datos (Storage & DB)
- **Estado:** ✅ Completado (SeaweedFS & Postgres)
- **Reto 1 (MinIO):** Las imágenes de Bitnami MinIO (`bitnami/minio`) fallaban al descargarse (`ErrImagePull`) debido a bloqueos de red o rate limiting hacia Docker Hub/Quay desde la VM.
- **Solución 1:** Se reemplazó MinIO por **SeaweedFS**.
    - SeaweedFS usa imágenes que sí pudieron descargarse.
    - Se configuró como Gateway S3 (`s3.enabled: true`) en el puerto 8333.
    - Se creó un Job (`setup-buckets-job`) para crear automáticamente los buckets (`mlflow-artifacts`, `airflow-logs`, etc.) post-despliegue.
- **Reto 2 (Postgres):** La imagen de Bitnami Postgres también falló (`ImagePullBackOff`).
- **Solución 2:** Se modificó la definición de la App `postgres` en Argo CD para usar la imagen oficial `postgres:13-alpine` de Docker Hub, la cual se confirmó que funciona (igual que `alpine`).

### 5. Limpieza de Recursos Huérfanos
- **Situación:** El pod de MinIO quedaba en estado `ImagePullBackOff` a pesar de haber eliminado su configuración del repositorio.
- **Explicación:** Argo CD no borra automáticamente las aplicaciones ("Application" CRD) si solo se quitan del manifiesto padre, a menos que se configure un prune específico o se borre el objeto Application.
- **Acción:** Se ejecutó `kubectl delete application minio -n argocd`, limpiando exitosamente el namespace `mlops`.

---

## 🛠 Estado Actual del Clúster (Snapshot)

| Componente | Estado | Notas |
| :--- | :--- | :--- |
| **K3s** | 🟢 Running | CIDRs custom (`10.45.x.x`). |
| **Argo CD** | 🟢 Running | Gestionando Apps vía GitOps. |
| **SeaweedFS**| 🟢 Running | Reemplazo de MinIO. S3 Endpoint: `http://seaweedfs-s3.mlops.svc:8333`. |
| **Postgres** | 🟢 Running | Imagen oficial `13-alpine`. |
| **MetalLB** | 🟡 Pendiente | Manifiestos cargados, verificando despliegue de controladores. |
| **Airflow** | ⚪ Pendiente | Esperando sincronización de Argo. |
| **MLflow** | ⚪ Pendiente | Esperando sincronización de Argo. |

## 📋 Próximos Pasos Inmediatos
1. Verificar despliegue de **Airflow** y **MLflow**.
2. Confirmar que MetalLB asigne IPs externas.
3. Ejecutar el pipeline de MLOps de prueba (DAG `mlops_full_pipeline`).

