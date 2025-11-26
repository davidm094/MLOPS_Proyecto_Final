Aquí tienes una guía concisa y directa, diseñada para ser una referencia rápida ("cheat sheet") sobre cómo resolver el problema de imágenes estancadas y versionar correctamente en Kubernetes.

-----

# Guía Rápida: Versionado y Actualización de Imágenes en K8s

El problema principal: **Kubernetes es declarativo**. Si el manifiesto (YAML) no cambia (ej. la etiqueta sigue siendo `mi-imagen:latest` o `dev`), K8s asume que el estado deseado ya se cumple y **no reinicia los Pods** ni descarga la nueva imagen, aunque esta haya cambiado en el registro.

Aquí tienes las 4 estrategias para solucionar esto, de la **mejor práctica** a la solución temporal.

### 1\. La Regla de Oro: Etiquetas Únicas (Inmutabilidad)

La forma correcta de garantizar actualizaciones es cambiar la etiqueta de la imagen en cada despliegue. Esto obliga a K8s a detectar un cambio en la especificación y disparar un *RollingUpdate*.

  * **Cómo hacerlo:** Usa el SHA del commit de Git, un timestamp o Versionado Semántico (SemVer) en tu pipeline de CI/CD.
  * **Ejemplo:**
    ```yaml
    containers:
      - name: mi-app
        image: mi-registry/app:v1.0.2  # O usa: app:commit-a1b2c3d
    ```
  * **Ventaja:** Permite hacer **rollbacks** instantáneos (`kubectl rollout undo`) porque las versiones anteriores siguen existiendo.

-----

### 2\. La Configuración: `imagePullPolicy`

Si insistes en usar etiquetas mutables (como `:latest` o `:staging`), debes configurar explícitamente la política de descarga.

  * **Configuración:**
    ```yaml
    containers:
      - name: mi-app
        image: mi-registry/app:latest
        imagePullPolicy: Always  # OBLIGATORIO para tags constantes
    ```
  * **Advertencia:** Esto **NO** reinicia el pod automáticamente si subes una nueva imagen. Solo garantiza que, *cuando* el pod se reinicie (por error o manualmente), K8s forzará la descarga de la imagen fresca en lugar de usar la caché del nodo.

-----

### 3\. El "Truco" Manual: Forzar el Reinicio

Si usas una etiqueta constante (ej. `:dev`) y `imagePullPolicy: Always`, K8s no detecta cambios al hacer `kubectl apply`. Debes forzar el reinicio para que descargue la nueva versión.

  * **Comando:**
    ```bash
    kubectl rollout restart deployment/nombre-de-tu-deployment -n tu-namespace
    ```
  * **Efecto:** Esto apaga los pods viejos y crea nuevos paso a paso, disparando el `imagePullPolicy: Always` y bajando el código nuevo.

-----

### 4\. La Opción Nuclear: Uso de Digests (SHA256)

Para entornos de ultra-seguridad donde necesitas garantizar que el código es bit a bit exacto.

  * **Cómo hacerlo:** No usas etiquetas, usas el hash único de la imagen.
  * **Ejemplo:**
    ```yaml
    image: mi-registry/app@sha256:45b23dee08af5e43e7...
    ```
  * **Ventaja:** Es imposible que cambie el código sin cambiar el YAML.

-----

### Resumen de Estrategias

| Estrategia | Tag en YAML | ¿Actualiza Auto? | ¿Permite Rollback? | Uso Recomendado |
| :--- | :--- | :---: | :---: | :--- |
| **Etiquetas Únicas** | `v1.2`, `a1b2c` | **Sí** | **Sí** | **Producción (Best Practice)** |
| **Forzar Rollout** | `latest` | No (requiere comando) | No | Desarrollo / Pruebas |
| **Digests** | `@sha256:...` | **Sí** | **Sí** | Alta Seguridad |

### Flujo de Trabajo Recomendado (CI/CD)

1.  **Build:** Tu CI construye la imagen docker.
2.  **Tag:** Etiqueta la imagen con el **Git Commit SHA** (ej. `app:xf34s`).
3.  **Push:** Sube esa imagen al registro.
4.  **Update:** Tu CD usa una herramienta (como `kustomize`, `helm` o `sed`) para reemplazar el tag en el YAML:
    `kustomize edit set image mi-app=mi-registry/app:xf34s`
5.  **Apply:** `kubectl apply -k .` -\> K8s detecta el cambio y actualiza solo.

-----

**Siguiente paso:** ¿Te gustaría que te genere un ejemplo de **GitHub Actions** o **GitLab CI** que implemente automáticamente el cambio de etiqueta (Estrategia 1) para que no tengas que hacerlo manual?