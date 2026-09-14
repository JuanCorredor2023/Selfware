# Atlas — Plan final · Nebius x NVIDIA Global AI Hackathon

**Track:** Personal AI · **Entrega:** 27 de octubre (deadline oficial 30 oct, 10:00 PT = 11:00 México)
**Arquitectura:** monolito modular · un repo · un paquete · un deploy · fronteras de módulo explícitas
**Equipo:** 4 · Video, guion, README, feedback y descripción: **los cuatro**

---

## 1. La idea

> Asistente personal sobre correo que organiza el contexto en PARA, **mide** si PARA mejora la recuperación frente a RAG plano, **sabe cuándo no sabe** (y busca en web), y lo muestra en un dashboard donde el juez ve la diferencia en vivo.

**H1:** clasificar en PARA y filtrar por esa estructura mejora *context precision* y *context recall* (RAGAS) frente a un índice plano sobre el mismo corpus. Se reporta **por categoría de pregunta**.

---

## 2. Diagrama final

Archivo: `atlas_arquitectura_final.mermaid` (se renderiza en GitHub; pégalo en el README).

Lectura en una línea: `Gmail + WhoareU.md → ingest (Nano, Serverless Jobs) → context (dos índices vivos) → agent (Ultra, confianza, Tavily) → api/web (toggle, procedencia, costo)`, con `eval` colgando de context y agent, y `observability` envolviendo toda llamada a Token Factory a través de **un solo punto de salida**.

---

## 3. Monolito modular: estructura del repo

```
atlas/
├── core/                 # compartido · dueño de esquemas: Persona 1
│   ├── schemas.py        # Document, ContextItem, Chunk, Provenance, Answer, TierCall
│   ├── config.py         # settings, umbrales, rutas PARA
│   └── llm.py            # ÚNICO cliente a Token Factory · emite spans OTel · enruta Nano/Ultra
├── ingest/               # Persona 1
│   ├── gmail.py          # conector (IMAP o MCP)
│   ├── normalize.py      # limpieza, dedup por hash, metadatos
│   ├── classify.py       # clasificación PARA con Nano
│   ├── profile.py        # carga WhoareU.md
│   ├── archive.py        # job: proyecto sin actividad N días → Archive
│   └── jobs.py           # entrypoints para Nebius Serverless Jobs
├── context/              # Persona 2
│   ├── store.py          # document store
│   ├── embed.py          # embeddings
│   ├── index_flat.py     # índice plano
│   ├── index_para.py     # índice + filtro estructural PARA
│   └── retrieve.py       # retrieve(query, strategy, k) → [Chunk con Provenance]
├── agent/                # Persona 3
│   ├── answer.py         # agente sobre Ultra
│   ├── confidence.py     # estimación de confianza por respuesta
│   ├── abstain.py        # política: confianza < umbral → web
│   └── tavily.py         # búsqueda web
├── eval/                 # Persona 3
│   ├── questions/        # ~200 preguntas, JSONL, etiquetadas por categoría PARA
│   ├── harness.py        # corre plano vs PARA sobre el set
│   ├── ragas_runner.py   # métricas RAGAS
│   └── report.py         # tabla por categoría + curvas costo/latencia
├── observability/        # Persona 4 (todos instrumentan)
│   ├── otel.py           # setup OpenTelemetry
│   └── cost.py           # tokens → costo por escalón
├── api/                  # Persona 4
│   └── app.py            # FastAPI: /ask, /ask?strategy=flat|para, /provenance, /cost, /projects
└── web/                  # Persona 4
    └── src/              # React: dashboard, toggle, procedencia, panel de costo
tests/
├── ingest/  context/  agent/  eval/  api/     # cada módulo entrega los suyos
README.md · LICENSE (Apache 2.0) · FEEDBACK.md · docs/guion_video.md
```

### Reglas del monolito
- **Ningún módulo importa de otro excepto de `core/`.** La comunicación entre módulos es por los contratos de la sección 4. Si necesitas algo de otro módulo, va al contrato, no al import.
- **Toda llamada a Token Factory pasa por `core/llm.py`.** Es la única forma de que el panel de costo y el cumplimiento sean verificables. Un `grep` por la URL de la API debe encontrar exactamente un archivo.
- Un solo `pyproject.toml`, un solo comando de arranque, un solo entrypoint de jobs.

---

## 4. Contratos entre módulos (se firman el día 5, con datos falsos si hace falta)

| Contrato | De → A | Firma |
|---|---|---|
| **C1** | ingest → context | `ContextItem(id, source, text, ts, hash, para_path, meta)` |
| **C2** | context → agent, eval, api | `retrieve(query: str, strategy: "flat" \| "para", k: int) -> list[Chunk]`, con `Chunk(text, item_id, para_path, ts, score)` |
| **C3** | agent → api, eval | `Answer(text, confidence: float, provenance: list[Chunk], used_web: bool, tier_calls: list[TierCall])` |
| **C4** | core/llm → observability | cada llamada emite `TierCall(model, tokens_in, tokens_out, latency_ms, cost_usd)` |
| **C5** | ingest/profile → agent | `Profile(text)` desde WhoareU.md, inyectado como system context |
| **C6** | eval → todos | `questions/*.jsonl`: `{q, expected, category: project\|area\|resource}` |

Cambiar un contrato requiere avisar a todos y actualizar `core/schemas.py` en el mismo PR.

---

## 5. Asignación de módulos

| Persona | Módulos | Es dueño de | Definition of done |
|---|---|---|---|
| **1 · Ingesta** | `ingest/`, `core/schemas.py`, `core/config.py`, deploy de Serverless Jobs | El esquema canónico. La compatibilidad con las reglas (Serverless Jobs + Token Factory). | Un job corre en Nebius, lee Gmail, escribe N `ContextItem` clasificados. Archivo automático mueve proyectos inactivos. |
| **2 · Contexto** | `context/` | Los dos índices vivos y la estrategia de recuperación. La procedencia como dato. | `retrieve()` responde en ambas estrategias con procedencia completa en < 500 ms sobre el corpus real. |
| **3 · Agente y evaluación** | `agent/`, `eval/` | **El número.** La confianza, el umbral, Tavily. | Reporte RAGAS por categoría, plano vs PARA, reproducible con un comando. Abstención calibrada sobre ese reporte. |
| **4 · Producto y observabilidad** | `api/`, `web/`, `observability/`, `core/llm.py` | **La evidencia.** Todo lo que el juez ve. El único punto de salida a Token Factory. | Dashboard con toggle, procedencia y panel de costo, desplegado en una URL pública que funciona sin que nadie del equipo esté conectado. |

**Sugerencia de reparto**, la decisión es suya: quien tenga más experiencia en sistemas toma Persona 1 (es la pieza de cumplimiento y del esquema que todos consumen). Quien más quiera aprender evaluación de LLMs toma Persona 3: es el módulo con más aprendizaje transferible y el que produce el resultado.

### Trabajo de los cuatro
- **Preguntas de evaluación:** 50 por persona sobre su propio correo, etiquetadas. Persona 3 consolida. **No las genera la IA.**
- **Guion del video:** se escribe en la semana 1 entre los cuatro (`docs/guion_video.md`) y se revisa cada viernes.
- **Video, README, descripción en Devpost, FEEDBACK.md:** semanas 7-8, los cuatro.
- **Code review:** nadie mergea sin revisión de otro. Nadie mergea lo que no puede explicar línea por línea.

---

## 6. Plan de 6 semanas de construcción + 2 de entrega

Cada viernes hay **demo interna de 30 minutos**: cada quien muestra su módulo corriendo, se revisa el guion, se decide qué se corta.

### Semana 1 · 7–13 sep · Cimientos y contratos
| Persona 1 | Persona 2 | Persona 3 | Persona 4 |
|---|---|---|---|
| Repo, Apache 2.0 visible en About, `pyproject`, CI mínimo. `core/schemas.py` v0. Acceso a Gmail funcionando (aunque sea un correo). | Document store vacío + `retrieve()` que devuelve datos falsos con la firma C2. | Formato de `questions/*.jsonl`. Primeras 20 preguntas propias. Esqueleto de `harness.py`. | `core/llm.py` con una llamada real a Nano y otra a Ultra vía Token Factory, emitiendo `TierCall`. FastAPI con `/health`. |

**Los cuatro:** guion del video v0 (`docs/guion_video.md`). Inventario de correos: ¿cuántos tenemos? Pedir al usuario externo. Correo a Devpost por el City Winner. Unirse al Builder Program (créditos).
**Viernes 11:** contratos C1–C6 firmados. Nadie cambia una firma sin PR a `core/`.

### Semana 2 · 14–20 sep · Cada módulo aislado, funcionando
| Persona 1 | Persona 2 | Persona 3 | Persona 4 |
|---|---|---|---|
| Conector Gmail real, normalización, dedup por hash. Clasificación PARA con Nano sobre 200 correos reales. Tests de dedup e idempotencia. | Embeddings + índice plano sobre lo que entrega P1. `retrieve("flat")` real. Tests de recuperación. | Agente de respuesta sobre Ultra consumiendo `retrieve()` (aunque sea plano). 50 preguntas propias. Corrida RAGAS sobre plano solo. | `/ask` conectado al agente. Dashboard: layout, lista de proyectos desde PARA (datos falsos). OTel exportando spans. |

**Viernes 18:** primer número, aunque sea solo del baseline. Guion v1.

### Semana 3 · 21–27 sep · Integración fea de punta a punta
| Persona 1 | Persona 2 | Persona 3 | Persona 4 |
|---|---|---|---|
| Job desplegado en **Serverless Jobs** corriendo la ingesta completa. WhoareU.md cargado. | Índice + filtro PARA. `retrieve("para")` real. **Ambos índices vivos.** | Harness corre plano vs PARA sobre las ~200 preguntas consolidadas. **Primer reporte por categoría.** | `/ask?strategy=` funcionando. Dashboard consume datos reales. Procedencia como dato en la respuesta. |

**Viernes 25 — hito duro:** una pregunta real entra por el dashboard, pasa por ingesta real, dos índices, Ultra, y regresa. Aunque esté feo. Si no pasa, la semana 4 se dedica a que pase y se recorta A6 y A3.

### Semana 4 · 28 sep–4 oct · Iterar sobre el número
| Persona 1 | Persona 2 | Persona 3 | Persona 4 |
|---|---|---|---|
| Robustez: reintentos, cursor de sincronización, corridas incrementales. Job de archivo automático (A6) si el hito 3 se cumplió. | Ajustar estrategia PARA según lo que el reporte diga (k, filtro, fallback al plano cuando la carpeta está vacía). | Analizar por categoría. Confianza por respuesta (`confidence.py`). Empezar calibración del umbral contra el reporte. | **Toggle** (A1) en el dashboard. **Procedencia visible** (A2). |

**Viernes 2:** número v2 por categoría. Decisión: ¿H1 se sostiene global, o solo por categoría? El guion se ajusta a la respuesta.

### Semana 5 · 5–11 oct · Adiciones y congelamiento
| Persona 1 | Persona 2 | Persona 3 | Persona 4 |
|---|---|---|---|
| Corrida de ingesta sobre el corpus del usuario externo. Limpieza de datos para el video. | Tests de regresión sobre recuperación. Documentar la estrategia en `docs/`. | **Abstención → Tavily** (A3) con umbral calibrado. Corrida final de evaluación. Reporte final. | **Panel de costo** (A4). Deploy a URL pública estable. |

**Viernes 9 — congelamiento de features.** Después de hoy solo bugs, docs y video. Todo lo que no entró, no entra.

### Semana 6 · 12–18 oct · Estabilidad y documentación
| Persona 1 | Persona 2 | Persona 3 | Persona 4 |
|---|---|---|---|
| README: setup, ejecución, dónde corre Serverless Jobs, dónde entra Nano. | README: cómo funcionan los dos índices, cómo reproducir la recuperación. | README: cómo reproducir el reporte con un comando. Gráficas finales. | README: cómo correr el dashboard. Verificar que la URL pública sobrevive sin nadie conectado. |

**Los cuatro:** `FEEDBACK.md` para Nebius (en serio, es un premio de $100 y diez ganadores). Descripción de Devpost v0. Guion final. Grabar el clip del usuario externo.

### Semanas 7–8 · 19–27 oct · Entrega (los cuatro)
- **19–23:** grabar el video. Editar. Ver. Regrabar. Tres minutos, con audio explicando Token Factory y Nemotron (requisito).
- **24–26:** descripción final en Devpost, README final, checklist de reglas (sección 8).
- **27:** **entregar.** Los tres días restantes son margen, no plan.

---

## 7. Qué se corta y en qué orden, si hay que cortar
1. A6 archivo automático
2. A3 abstención → Tavily (se pierde el bonus, no el proyecto)
3. A5 usuario externo (si no aparece a tiempo, el corpus es el de los cuatro)
4. A4 panel de costo (se sustituye por una gráfica estática en el video)

**Nunca se cortan:** los dos índices, el reporte por categoría, el toggle, la procedencia. Sin eso no hay proyecto.

---

## 8. Checklist de cumplimiento (se revisa el 24 de octubre)
- [ ] Llamada en runtime a Token Factory (`core/llm.py`) y Serverless Jobs desplegado
- [ ] Al menos un modelo NVIDIA open source: Nemotron Nano y Ultra
- [ ] Repo público, Apache 2.0 visible en la sección About
- [ ] README con setup y dónde se usa Nemotron / Token Factory / Serverless Jobs
- [ ] URL de demo funcional que no dependa de una laptop del equipo
- [ ] Video ≤ 3 min, YouTube público, con audio sobre Token Factory y Nemotron, sin música con derechos
- [ ] Todo en inglés (o con traducción)
- [ ] Track: Personal AI
- [ ] Feedback sobre Token Factory, AI Cloud y herramientas NVIDIA
- [ ] Tavily: llamada funcional en runtime (si A3 sobrevivió)
- [ ] Ciudad de Builders & Brews indicada, si Devpost confirmó que aplica

---

## 9. Siguientes pasos: los próximos 5 días

**Hoy, viernes 4:** decidir quién es Persona 1–4. Nombre del proyecto. Crear el repo con licencia. Registrarse los cuatro en Devpost y en el Builder Program.

**Sábado 5:** cada quien lee la parte del documento de su módulo y escribe, en `docs/<modulo>.md`, tres párrafos: qué hace, qué expone, qué consume. Es el borrador del contrato.

**Domingo 6:** contar correos. Cada quien exporta su Gmail o cuenta cuántos tiene. Si suman menos de 2,000, Persona 3 busca dataset público complementario.

**Lunes 7:** Persona 4 hace la primera llamada real a Token Factory. Es el desbloqueo de todo lo demás. Persona 1 sube `core/schemas.py` v0. Correo a Devpost.

**Martes 8:** guion del video v0, los cuatro, una hora. Pedir al usuario externo.

**Viernes 11:** primera demo interna. Contratos firmados.

---

## 10. Reglas de trabajo (no cambian)
- IA para lo que ya sabemos hacer. Humanos para lo que queremos aprender.
- Nadie mergea código que no puede explicar línea por línea.
- Cada módulo entrega sus tests. Prueban invariantes que nosotros decidimos.
- Cada viernes: ¿lo que construimos esta semana sale en el video? Si no, se corta.
- El video es la calificación.
