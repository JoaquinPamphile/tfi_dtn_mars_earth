# DTN Mars–Earth Telemetry Synchronization

Aplicación y banco experimental para estudiar registro y sincronización de telemetría DTN-native bajo conectividad intermitente Marte–Tierra.

Estado actual: estructura inicial del proyecto.

Las responsabilidades de cada módulo y la dirección de dependencias están en [docs/architecture.md](docs/architecture.md).

## Áreas previstas

### Core científico

`backend/core` concentra la lógica científica: dominio, simulación, contactos, telemetría, store-and-forward, sincronización y métricas. Es un núcleo independiente de la API y de las interfaces.

### Experimentos

`backend/experiments` orquesta corridas y campañas sobre el core y produce resultados reproducibles.

### API

`backend/api` expone HTTP sobre el core, los experimentos y la lectura de la evidencia oficial. No contiene algoritmos científicos.

### Laboratorio

`frontend/lab` es la aplicación de investigación: ejecutar corridas, inspeccionar escenarios, contactos y telemetría, y analizar el backlog.

### Vista académica TFI

`frontend/tfi` es la presentación académica: panorama, metodología, resultados y reproducibilidad, a partir de evidencia oficial congelada.

### Evidencia

`evidence/` guarda la evidencia científica oficial congelada. Las ejecuciones de desarrollo no escriben en esta carpeta.

### Workspace

`workspace/` guarda salidas temporales de corridas, campañas y pruebas. No es evidencia oficial.
