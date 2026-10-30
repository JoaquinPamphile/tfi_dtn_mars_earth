# Arquitectura

## Objetivo

Este repositorio contiene la aplicación y el banco experimental para estudiar registro y sincronización de telemetría DTN-native bajo conectividad intermitente Marte–Tierra.

Separa el núcleo científico, la ejecución de experimentos, la interfaz HTTP, la evidencia oficial y las salidas de desarrollo.

Estado actual: el dominio base vive en `backend/core/domain`. Todavía no hay reloj, motor de simulación, contactos, transporte, nodos, sincronización, experimentos ejecutables ni API funcional.

## Módulos

### `backend/core`

Lugar de la lógica científica:

- dominio;
- reloj discreto y simulación;
- contactos;
- telemetría;
- store-and-forward;
- sincronización;
- persistencia;
- ACK;
- batching;
- recuperación;
- métricas.

`backend/core` se utiliza y se prueba como un núcleo científico independiente.

No depende de:

- FastAPI;
- HTTP;
- PostgreSQL;
- la UI.

Tampoco depende de `backend/experiments`, de `backend/api` ni del diseño concreto de `evidence/` y `workspace`.

### `backend/experiments`

Orquesta experimentos científicos usando `backend/core`.

Puede:

- ejecutar una corrida;
- ejecutar una campaña;
- parametrizar las familias E1, E2 y E3;
- producir resultados reproducibles.

No depende de la API. Puede leer entradas declarativas bajo `config/`.

### `backend/api`

Interfaz HTTP sobre:

- core;
- experiments;
- la lectura de la evidencia oficial.

No contiene algoritmos científicos.

### `evidence/`

Evidencia científica oficial congelada.

Ubicaciones:

- `evidence/official/e1`
- `evidence/official/e2`
- `evidence/official/e3`
- `evidence/manifests` — procedencia de la evidencia oficial.

E1, E2 y E3 son las familias oficiales de experimentos. Las ejecuciones de desarrollo no escriben dentro de `evidence/`. El contenido de `evidence/` se versiona.

### `workspace/`

Salidas temporales y exploratorias:

- `workspace/runs/`
- `workspace/campaigns/`
- pruebas manuales;
- salidas de desarrollo.

`workspace/` no es evidencia científica oficial. El contenido de corridas y campañas queda fuera del versionado; los marcadores `.gitkeep` se versionan para conservar los directorios.

## Resto del árbol

- `backend/tests` — pruebas del backend. Hoy cubren el dominio base.
- `config/` — entradas declarativas (`scenarios/`, `workloads/`, `experiments/`). No es lógica científica ni evidencia.
- `docker/` — imagen mínima para ejecutar los tests del núcleo. `docker-compose.yml` define el servicio `test`. No hay servicios de aplicación.

## Dirección de dependencias

Las capas superiores dependen de las inferiores. Las inferiores no dependen de las superiores.

```text
API
   ↓
Experiments
   ↓
Core
```

Permitido:

- `backend/api` depende de `backend/core`, de `backend/experiments` y de la lectura de `evidence/`.
- `backend/experiments` depende de `backend/core`.
- `backend/experiments` puede leer `config/`.

Prohibido:

- que `backend/core` dependa de FastAPI, de HTTP, de PostgreSQL o de la UI;
- que `backend/core` dependa de experiments o de la API;
- que `backend/experiments` dependa de la API;
- algoritmos científicos dentro de `backend/api`;
- que las corridas de desarrollo escriban en `evidence/`.

## Evidencia y workspace

| | `evidence/` | `workspace/` |
| --- | --- | --- |
| Significado | Evidencia científica oficial congelada | Salida temporal o exploratoria |
| Escritura | Resultados oficiales que pasan a formar parte del registro del proyecto | Corridas, campañas, pruebas y desarrollo |
| Git | Versionado | Contenido ignorado; se conserva `.gitkeep` |
| Experimentos | Familias oficiales E1, E2 y E3 | Cualquier ejecución exploratoria |

## Idioma

Los identificadores del código pueden usar nombres técnicos en inglés. Los docstrings, los comentarios y esta documentación están en español.

Se permiten términos técnicos en inglés cuando son naturales: ACK, backlog, SyncUnit, sender-driven, receiver-driven, retry, gap, store-and-forward.

## Ausente en esta estructura

El dominio base está en `backend/core/domain`. Los tests de ese dominio se ejecutan con el contenedor de `docker/`.

Esta estructura todavía no contiene:

- un motor de simulación;
- ejecutores de experimentos;
- una API funcional.
