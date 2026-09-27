# Registro de decisiones — Carril `context/` (Persona 2)

> Proyecto Atlas · Nebius x NVIDIA Global AI Hackathon · Track Personal AI
> Documento vivo. Se actualiza conforme se cierran o reabren decisiones.

---

## Decisiones de arquitectura — `context/`

| # | Decisión | Qué se eligió | Por qué | Estado |
|---|---|---|---|---|
| 1 | Clasificación de la query | Se clasifica **dentro** de `retrieve`, con la query cruda | Comparación flat vs PARA perfectamente controlada; misma query cruda a ambas ramas, la única diferencia es el paso de filtro | Cerrada |
| 2 | Modelo clasificador de query | **Nemotron Super** vía `core/llm.py` | Escalón intermedio para tarea rápida con razonamiento; habilita panel de costo de 3 niveles | Cerrada |
| 3 | Estructura del filtro PARA | **Filtro duro top-1**, una sola categoría | PARA es mutuamente excluyente por diseño; máximo contraste con el baseline | Cerrada |
| 4 | Multicategoría / grados de pertenencia | **No** | PARA es single-label por método; innecesario | Cerrada |
| 5 | Red de seguridad ante mala clasificación | **Fallback a plano** si el filtro PARA queda vacío | Sin la salida "suave" del multicategoría, el fallback protege el recall; además es reportable en la eval | Cerrada |
| 6 | Archive en el retrieval | **Excluido por defecto**, salvo query clasificada como archive | Archive = historial inactivo; excluirlo es un mecanismo nombrable de por qué PARA gana al plano | Cerrada |
| 7 | Número de índices físicos | **Uno solo**; flat y PARA son el mismo store consultado con/sin filtro | Garantiza comparación justa (mismos embeddings, misma data); PARA vive como tags, no directorios | Cerrada |
| 8 | Vector store | **Chroma** ahora → **Qdrant** después | Chroma sin fricción in-process para la eval; Qdrant natural para el endpoint serverless | Cerrada |
| 9 | Frontera de aislamiento | Los objetos de Chroma **mueren en `store.py`**; hacia afuera solo tipos propios | Hace la migración a Qdrant "cambiar un archivo"; permite que los tipos viajen a otros carriles sin arrastrar infra | Cerrada |
| 10 | Generación de embeddings | La hace **`embed.py`**, no el store | Embeddings portables; el store es almacén tonto, no pensador | Cerrada |
| 11 | Chunking | **Un correo = un chunk** para empezar | Lo más simple; suficiente salvo correos que excedan el embedder | Cerrada |
| 12 | Salvaguarda de chunking | `embed.py` **detecta y registra** correos que exceden el límite, no trunca en silencio | Saber que el caso existe antes de que sorprenda en la eval | Cerrada |
| 13 | Empaquetado | **In-process ahora**, `retrieve` como función pura → endpoint serverless después | Cero fricción para eval y desarrollo; envolver en HTTP al final es trivial si `retrieve` no toca web ni estado global | Cerrada |
| 14 | Validación del tag PARA | `add_documents` **valida y rechaza** documentos sin `para_folder` válido | Que reviente en la inserción con error claro, no como recall bajo misterioso 3 semanas después | Cerrada |
| 15 | Pipeline dinámico | `add_documents(lote)` **incremental** desde el diseño, no `build_index(todo)` | Soporta introducir información nueva sin reconstruir; idempotente por email_id | Cerrada |
| 16 | Capa de consolidación | **Pospuesta** (post-hackathon) | El contrato ya la admite; no se estresa la incrementalidad en el hackathon | Diferida |
| 17 | Telemetría de confianza de clasificación | **Pospuesta**; el esqueleto confía en el clasificador | La elección forzada de Super es legítima (salió de razonamiento); el fallback ya protege | Diferida |

---

## Decisiones de dominio — `types.py`

| Campo / aspecto | Decisión | Por qué | Estado |
|---|---|---|---|
| Naturaleza de `types.py` | **Capa de dominio**: solo imports de librería estándar, cero comportamiento | Todo depende de ella, ella no depende de nada; permite que los tipos viajen sin arrastrar infra | Cerrada |
| `score` — tipo | **float** | Es un decimal; no sobre-diseñar con clase `Score` hasta confirmar que hacen falta dos valores | Cerrada |
| `score` — significado | Convención fija, **mayor = más relevante**, documentada junto al campo | Persona 3 calibra la abstención contra él; no puede estar semánticamente ambiguo | Cerrada (semántica) |
| `score` — representación | Cercanía cruda **vs** normalizada 0–1 | Ambas son float; la normalizada sobrevive a cambio de embedder pero cuesta más | **Abierta → junta** |
| `date` — tipo | **Objeto fecha real**, no string | Se querrá aritmética de fechas; comparar strings de fecha es fuente de bugs | Cerrada |
| `date` — zona horaria | **Aware, normalizado a UTC** interno; conversión a local solo al mostrar | Evita mezclar fechas aware/naive; el correo trae zonas distintas | Cerrada |
| `date` — parseo | String→objeto ocurre en la **frontera** (`store.py`/`add_documents`), no en el dominio | El dominio no tiene lógica de parseo; el string sucio muere en la frontera | Cerrada |
| `para_folder` — tipo | **Enum** de las cuatro categorías | Validación fácil, definición canónica única de PARA, reglas de negocio referencian el enum no strings | Cerrada |
| `RetrievalResult` — origen | **Autocontenido**: incluye strategy, k (query aún no se incluyó; ver nota) | Un agente de EDA post-hackathon necesita resultados autoexplicativos fuera de contexto | Cerrada |
| `RetrievalResult` — `query_category` | Enum PARA opcional; `None` **solo** si strategy = FLAT. En PARA **siempre** tiene categoría, incluso con fallback | Sirve al toggle, a la procedencia y al diagnóstico de la eval | Cerrada |
| `RetrievalResult` — `fell_back_to_flat` | Bool. Eje **independiente** de `query_category` | Un resultado PARA + categoría + fallback=True es válido y es el caso diagnóstico clave del clasificador | Cerrada |
| `RetrievalResult` — `score` agregado | **Fuera del módulo**: no va en `RetrievalResult` | Un score a nivel de resultado es telemetría (OTel), no dato de dominio; los scores viven por `Chunk` | Cerrada |
| `Document.category` — tipo | **`str`** (no enum) | Entra crudo de Persona 1, que no conoce `ParaFolder`; se convierte-y-valida a enum en la frontera (`add_documents`) | Cerrada |
| `Document.date` — tipo | **`str`** (asimetría intencional con `Source.date` = `datetime`) | Frontera cruda entrando; el parseo str→datetime ocurre al construir `Source` | Cerrada |
| `Source.date` — default | **Sin default**, obligatorio | Un correo tiene fecha real; un default de "ahora" enmascararía la ausencia con una fecha falsa plausible | Cerrada |
| Mixin `str` en enums | `ParaFolder(str, Enum)` y `Strategy(str, Enum)` | Serializan a JSON directo y sobreviven a persistencia sin tratamiento especial (necesario para EDA/guardado) | Cerrada |
| Marca de versión de esquema | **Incluida** como campo `version` en `RetrievalResult`, **obligatorio** (sin default) | Único requisito de persistencia caro de retrofitear; obligatorio fuerza asignación deliberada, no en piloto automático | Cerrada |
| Invariantes de `RetrievalResult` | **`__post_init__`** hace cumplir 3 estados imposibles (verificado 6/6) | "60 líneas ahora vs 1000 después": el objeto se niega a nacer corrupto, no depende de que todos recuerden las reglas | Cerrada |

### Invariantes hechas cumplir en `RetrievalResult.__post_init__`

| Regla | Estado que rechaza | Razón |
|---|---|---|
| 1 | `FLAT` con `query_category` no nula | FLAT nunca clasifica |
| 2 | `FLAT` con `fell_back_to_flat=True` | No se puede caer a plano estando ya en plano |
| 3 | `PARA` con `query_category` nula | PARA siempre clasifica (un `None` aquí sería bug del clasificador) |

> Usar `is None` / `is not None` explícito, no veracidad — por el mixin `str`, un valor podría ser falsy.
> Comparar contra `Strategy.FLAT`/`Strategy.PARA`, no `ParaFolder`.

---

## Decisiones de implementación — `embedder.py`

| Aspecto | Decisión | Por qué | Estado |
|---|---|---|---|
| Embedder de arranque | **`FakeEmbedder` determinista por hash** (sha256 del texto → semilla → `random.Random` local → N floats) | Prototipar `store.py` sin instalar nada, sin red, con tests reproducibles | Cerrada |
| Forma del embedder | **`embed(list[str]) -> list[list[float]]`** (batch, no uno a uno) | Los servicios reales embeben en lote; forma batch evita cambiar el contrato al migrar | Cerrada |
| Aislamiento del generador | **Instancia local `random.Random(seed)`**, no `random.seed()` global | No contaminar el estado de aleatoriedad del resto del programa | Cerrada |
| Dimensión | **384** (alineada con MiniLM), fija | Que el intercambio Fake→real sea transparente (misma dimensión en la colección) | Cerrada |
| Migración prevista | `FakeEmbedder` → `sentence-transformers` (MiniLM) para relevancia real → embedder de producción | Intercambiables por inyección; misma forma, `store.py` no cambia | Diferida |
| Límite del Fake | Valida **plomería** (inserta/filtra/ensambla), **no relevancia** (vectores sin sentido semántico) | La relevancia real solo se valida con MiniLM; scores del Fake no son señal de calidad | Nota |

## Decisiones de implementación — `store.py` (`ChromaStore`)

| Aspecto | Decisión | Por qué | Estado |
|---|---|---|---|
| Embedder | **Inyectado en el constructor**, fijo de por vida | Mezclar embedders corrompe la búsqueda (peras con manzanas); inyección permite cambiar sin tocar el store | Cerrada |
| Aislamiento | Objetos de Chroma **mueren dentro de `store.py`**; hacia afuera solo `Chunk`/`Source` | Frontera de aislamiento; migración a Qdrant = cambiar un archivo | Cerrada |
| API de búsqueda | **`collection.query()` clásico**, densa pura | Estable y probado; suficiente para H1 | Cerrada |
| Recuperación híbrida (dense+sparse+RRF) | **Descartada para el hackathon** → extensión post-hackathon | Ortogonal a H1; añade complejidad y variable extra al experimento. Chroma la soporta nativa, retomarla será barato. Segundo experimento del blog. | Diferida |
| Métrica de distancia | **Coseno** (`{"hnsw": {"space": "cosine"}}`) | Similitud semántica vive en la dirección del vector, no la magnitud; robusto sin depender de que los embeddings vengan normalizados; distancia acotada [0,2] facilita normalizar el score | Cerrada |
| Operación de inserción | **`upsert`** (no `add`) | Permite reclasificación (activo→archive) e idempotencia "mismo estado final". `add` ignora ids existentes en silencio | Cerrada |
| id del registro | **Hash sha256** de `source_id + source + chunk_index` | Tamaño fijo, único, inmune al separador; procedencia va en metadata, no en el id. Determinismo del hash = idempotencia | Cerrada |
| id universal multi-fuente | Esquema soporta **`source` + `source_id` + `chunk_index`** desde ya (hoy: source="email", chunk_index=0) | Evita refactor de ids al añadir 2ª fuente (WhatsApp, etc.) o al partir correos en chunks. Solo la forma; la funcionalidad multi-fuente espera | Cerrada (forma) |
| Fecha en Chroma | Se guarda **ISO string** (Chroma no acepta datetime); se reconstruye a `datetime` aware al recuperar (`_to_datetime`) | Chroma solo acepta str/int/float/bool; el viaje datetime→ISO→datetime cierra en el ensamblado | Cerrada |
| Normalización de score | **`1 - (distancia/2)`** sobre coseno → [0,1], mayor = más relevante | El sentido correcto (mayor=mejor) es no negociable; la escala exacta se acuerda con Persona 3 | Cerrada (sentido); escala → junta |
| Conversores de dominio | Tres privados: `_to_para_folder`, `_to_datetime`, `_distance_to_score` | Cada campo crudo de Chroma pasa por su traductor a dominio; concentra la traducción, testeable | Cerrada |
| Chunking | **Un correo = un chunk** (`chunk_index=0` explícito, sin default) | Simple y suficiente hoy; partir correos = después. Sin default fuerza pasarlo conscientemente | Cerrada |
| `path` del store | Parámetro del constructor | **Pendiente**: el default apunta a un escritorio de Windows; cambiar a ruta relativa portable (`./chroma_data`) antes de compartir | Abierta |

## Deuda conocida en `store.py` (no bloqueante)

- **Validación de relevancia**: espera al embedder real (MiniLM). El `FakeEmbedder` solo valida plomería.
- **Escala del score**: `1 - dist/2` es el sentido correcto; la fórmula/escala final se acuerda con Persona 3.
- **`path` portable**: cambiar el default de la ruta de Windows a relativa.
- **Indentación**: adoptar espacios (4) en el editor — el bug de tabs+espacios ha reaparecido varias veces.
- **Linter**: montar `ruff` (o `pyflakes`) — varias rondas de bugs fueron typos, `self.` faltantes y mayúsculas de import que un linter caza al instante.

---

## Decisiones de implementación — `retrieve.py` (`Retrieve`) y `classifier.py`

| Aspecto | Decisión | Por qué | Estado |
|---|---|---|---|
| Naturaleza de `retrieve` | **Lógica de negocio pura** (decisión), separada de `store` (mecánica Chroma) y `parser` (aduana datos) | No cambiaría al migrar de vector store; 100% tuya y portable | Cerrada |
| Forma | **Clase `Retrieve`** con store y classifier **inyectados** en `__init__` | Dependencias estables entre llamadas; mismo patrón que embedder→store | Cerrada |
| Pureza | `retrieve` **no toca web ni estado global**; entra `(query, strategy, k)`, sale `RetrievalResult` | Permite envolver en endpoint serverless al final sin reescribir | Cerrada |
| `strategy` de entrada | Llega como **enum `Strategy`**, no str; la conversión str→enum vive en la frontera de API (fuera de `retrieve`) | `retrieve` es lógica, no frontera de entrada; ignorante del transporte | Cerrada |
| `k` | Fluye de `retrieve` **a los métodos search del store** (no al constructor); el store deja de hardcodear `n_results` | El llamador controla cuántos chunks; el store se inyecta ya construido | Cerrada |
| Interfaz store↔retrieve | Los search del store pasan de **privados a públicos** (`search_flat`, `search_filtered`); su contrato es `→ list[Chunk]` | `retrieve` los llama desde afuera; son la interfaz pública del store | Cerrada |
| `category` hacia el store | `retrieve` pasa **`ParaFolder`** (enum), no str; el store convierte a str con `.value` para el `where` de Chroma | Comunicación interna en dominio rico; seguridad de tipos; conversión enum↔str concentrada en el adaptador | Cerrada |
| Despacho por rama | `retrieve` ramifica FLAT/PARA; clasifica **solo dentro de PARA** | En FLAT `query_category=None` (invariante); clasificar en FLAT la violaría | Cerrada |
| Nacimiento de los 3 campos | `strategy` del argumento; `query_category` del classifier (solo PARA); `fell_back_to_flat` de inspeccionar si el filtrado vino vacío | El store no conoce ninguno — solo entrega chunks; `retrieve` les da sentido | Cerrada |
| Condición de fallback | **Filtrado vacío** (`if not search_result`) → busca plano y marca `fell_back_to_flat=True`; conserva `query_category` | Vacío estricto, simple. PARA+categoría+fallback=True es válido (caso diagnóstico del clasificador) | Cerrada |
| `SCHEMA_VERSION` | Constante de módulo, pasada por `retrieve` a cada `RetrievalResult` | Un solo lugar donde vive la versión | Cerrada |
| Classifier de arranque | **`Classifier` falso configurable**: recibe la categoría a devolver en `__init__` | Permite forzar cualquier categoría y disparar el fallback en tests; hardcodeado no lo permitiría | Cerrada |
| Forma del classifier | `classify_query(query: str) -> ParaFolder` | Contrato que el real (Nemotron Super) cumplirá; query→categoría | Cerrada |
| Classifier real (pendiente) | `classify_query.py` con Super; debe **garantizar salida `ParaFolder` válida** (elección forzada, nunca "no sé") | Igual que el parser garantiza `Document`s válidos; `retrieve` confía en recibir enum válido | Diferida |

---

## Pendientes para la junta

1. **Representación del `score`** — ya existe fórmula concreta (`1 - distancia_coseno/2`, rango [0,1], mayor=más relevante). Falta que Persona 3 confirme si esa escala le sirve para calibrar el umbral de abstención. El sentido ya es correcto; la escala es lo negociable.
2. **Confirmar con quien diseñe `core/llm.py`**: ¿los embeddings entran por el mismo `core/llm.py` o por una puerta aparte? (afecta `embed.py`).
3. **Avisar a Persona 4**: el panel de costo (`COST`) lleva 3 barras (Nano/Super/Ultra), no 2.
4. **Avisar a Persona 3**: OTel debe etiquetar `tier` con 3 valores posibles.
5. **Confirmar a Persona 3 y 4**: el store físico es UNO; IDXF/IDXP en el diagrama global son dos vistas lógicas, no dos estructuras. (Se corrige el global en la próxima junta.)
6. **Acordar con Persona 1 el vocabulario exacto de strings de categoría**: los 4 valores en minúscula (`"projects"`, `"areas"`, `"resources"`, `"archive"`), para que la conversión str→`ParaFolder` no falle por casing o idioma.

## Cabos sueltos menores en `types.py`

- **`query` en `RetrievalResult`**: se acordó autocontención con query/strategy/k, pero el `RetrievalResult` incluye strategy y k, **no** el texto de la query. Si se añade (útil para trazabilidad de EDA), `retrieve` es el punto que lo llenaría (tiene la query a mano) y hay que añadir el campo al dominio. Decisión aún diferida.
- **`query` como clase vs string**: nunca se cerró. Por defecto, string hasta que cargue algo que un string no lleve.
- **Significado de los valores de `version`**: `version` obligatorio disciplina *tu* construcción, pero Persona 3 (que lee, no construye) necesita saber qué forma implica cada valor. Va en el contrato del día 5, no en el tipo.

## Contratos del día 5 (pendientes de redactar)

- **Con Persona 1 (ingest):** shape del documento de entrada con `para_folder` validado (exactamente una de las 4 categorías, nunca vacío), y fecha como string parseable.
- **Con Persona 3 (agent/eval):** firma de `retrieve` + significado fijo de `score` para la abstención.
- **Con Persona 4 (api/web):** `retrieve` es función pura importable in-process, no un servicio (todavía).
