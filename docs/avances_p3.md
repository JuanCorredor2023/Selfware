# Avances de P3 (agente y evaluación) — 24 a 29 de octubre de 2026

Ramas: `p3/enron-resultados` (mergeada en el PR #4) y `p3/metricas-finales`. Entrega oficial: **30 de octubre, 10:00 PT (11:00 CDMX)**;
el plan interno apuntaba al 27.

## 1. En una línea

Selfware ya tiene **dos buzones reales, 250 preguntas (200 verificadas por un humano)
y una evaluación reproducible con números reales**. El resultado, igual en los dos
buzones: con la carpeta del dueño PARA ordena mejor la respuesta, pero ni Nemotron
Super ni Nemotron Ultra eligen bien la carpeta, y el filtro esconde la respuesta.

## 2. Qué se hizo

### 2.1 Tres errores que impedían correr el sistema real

| Archivo | Dueño | Problema | Arreglo |
|---|---|---|---|
| `context/classifier.py` | P2 | `max_tokens=4`: Nemotron se corta mientras razona, devuelve `content=None` y `None.strip()` truena. El brazo PARA no podía responder ninguna pregunta | `max_tokens=1024` y `None` → carpeta por defecto (commit `2bd29cd`, *for Person 2*) |
| `core/llm.py` | P4 | `embed()` leía `MODEL_IDS["embedding"]` (`KeyError`) | Ya estaba arreglado en la rama de P4 y vino incluido |
| `api/_real_agent.py` | P4 | Llamaba a `Classifier(cat)`, que ya no existe | `Classifier()` (commit `563e87e`, *for Person 4*) |

### 2.2 Corpus

- **Enron**, buzón de **Vince Kaminski** (jefe de Research): 3,084 correos limpios
  (solo las carpetas del dueño, sin hilos citados, sin duplicados).
- PARA tomado de la carpeta del dueño (`tools/enron_para_kaminski-v.json`, congelado
  el 25 de octubre): 875 projects, 1,940 areas y 269 resources.
- Dos índices Chroma: uno con las **etiquetas del dueño** y otro con las **etiquetas
  de Nano** (el clasificador real de ingesta).
- El corpus vive fuera del repo; `questions/README.md` explica cómo reproducirlo.

### 2.3 Preguntas (`questions/`)

- **200 con respuesta** (67 projects, 67 areas, 66 resources), cada una con un
  correo de evidencia distinto, y **25 sin respuesta** (abstención).
- Método en dos pasos contra la contaminación léxica (D27): primero se extrae el
  hecho y después se escribe la pregunta sin mirar el correo. Jaccard mediano entre
  pregunta y correo: 0.06–0.07.
- `evidence_alt` en 20 preguntas (30 correos): en un buzón real la respuesta suele
  estar en varios correos (original, recordatorio, "Re:"), y cualquiera cuenta como
  acierto.
- **Las 200 están verificadas por un humano (P3)**: un triaje por IA primero, luego
  revisión una por una contra el correo, en lotes de 20, con 5 criterios. 45 se
  reescribieron durante el proceso (campo `revised`).
- `tools/verificar_preguntas.py` comprueba formato, cita literal y única, categoría,
  alternos y abstención. Las 225 pasan.

### 2.4 Código nuevo (todo con tests: 431 pasan, ruff limpio)

- `eval/retrieval_metrics.py`: **hit@k y MRR** contra la evidencia (gratis, sin
  juez), y **tabla de enrutamiento** del clasificador.
- `eval/harness.py`: guarda los ids recuperados, una falla de Ultra marca la fila en
  vez de tumbar la corrida, y corre en paralelo.
- `scripts/index_enron.py`: carga los correos en Chroma (etiquetas por carpeta o por
  Nano).
- `scripts/run_eval.py`: tres modos (`--fake`, `--retrieval-only`, `--real`) más
  `--oracle`, y reporta el gasto en créditos de cada corrida.
- `agent/answer.py`: prompt y centinela en inglés (antes en español, y Ultra mezclaba
  idiomas).

## 3. Resultados

### 3.1 Resultados finales: 250 preguntas, dos buzones (28 oct)

Reportes `final250-*.md` (solo recuperación). Por buzón: 100 preguntas con respuesta
(34 projects / 33 areas / 33 resources, todas `human-verified`) y 25 sin respuesta.
`kaminski-v` usa el subconjunto de 100 (`enron_kaminski-v_100.jsonl`); `shapiro-r` sus
100. Correos etiquetados con las carpetas del dueño; la pregunta la enruta Super (el
sistema actual), Ultra (mismo prompt, modelo ~4 veces más grande) o el oráculo (la
carpeta real). Gráficas para el video: `scripts/plot_video.py`.

**hit@5** (¿el correo correcto está entre los 5 primeros?)

| Buzón | flat | PARA · oráculo | PARA · Super | PARA · Ultra |
|---|---:|---:|---:|---:|
| Kaminski (research, 3,084 correos) | 0.91 | **0.94** (+0.03 [+0.00, +0.07]) | 0.48 (**−0.43** [−0.53, −0.33]) | 0.40 (**−0.51** [−0.61, −0.41]) |
| Shapiro (gov. affairs, 1,179 correos) | 0.95 | **0.96** (+0.01 [+0.00, +0.03]) | 0.40 (**−0.55** [−0.65, −0.45]) | 0.38 (**−0.57** [−0.67, −0.47]) |

**MRR** (qué tan arriba queda el correo correcto)

| Buzón | flat | PARA · oráculo | PARA · Super | PARA · Ultra |
|---|---:|---:|---:|---:|
| Kaminski | 0.82 | **0.87** (**+0.05** [+0.02, +0.09]) | 0.44 (**−0.38**) | 0.38 (**−0.44**) |
| Shapiro | 0.87 | **0.90** (**+0.02** [+0.01, +0.04]) | 0.37 (**−0.50**) | 0.37 (**−0.50**) |

**Enrutamiento** (los dos buzones juntos): ¿la pregunta fue a la carpeta de su respuesta?

| Respuesta en | Super | Ultra |
|---|---:|---:|
| projects (68) | 19 (28%) | 4 (6%) |
| areas (66) | **0 (0%)** | **0 (0%)** |
| resources (66) | 56 (85%) | 62 (94%) |
| **Total** | 75/200 (38%) | 66/200 (33%) |
| Preguntas mandadas a resources | 73% / 80% | 86% / 94% |

**Qué significa:**
1. **Se repite en los dos buzones.** Ya no es una anécdota de Kaminski.
2. **Con la carpeta del dueño, PARA ordena mejor**: el MRR sube en los dos buzones
   (significativo). En hit@5 la ganancia es pequeña y su intervalo toca el 0, porque flat
   ya acierta 91–95%: queda poco margen (efecto techo).
3. **Un modelo más grande no arregla el enrutamiento.** Ultra cae todavía más en el
   atractor de resources que Super, y ninguno acierta una sola pregunta de areas. El
   problema es la tarea (adivinar la taxonomía personal del dueño a partir de una pregunta
   de una línea), no la capacidad del modelo.
4. Con el filtro duro, cada error de enrutamiento esconde la respuesta: PARA pierde
   0.43–0.57 de hit@5 frente a flat.

Gasto de las corridas finales: Ultra US$0.158, Super US$0.061, oráculo e índice de
Shapiro < US$0.01. **Gasto total del proyecto en Nebius: ≈ US$6.1.**

### 3.2 Corridas anteriores: Kaminski, 200 preguntas (25 oct)

Reportes `final-*.md`, con las 200 preguntas ya verificadas por el humano. Incluyen las
etiquetas de Nano y la corrida completa con Ultra y el juez de RAGAS, que no se
repitieron sobre las 250.

**hit@5: ¿el correo correcto está entre los 5 primeros? (flat ≈ 0.92)**

| Quién archivó los correos | Quién clasifica la pregunta | PARA | PARA − flat (IC 95%) |
|---|---|---:|---|
| El dueño (sus carpetas) | Super (sistema actual) | 0.45 | **−0.48** [−0.55, −0.41] |
| El dueño (sus carpetas) | **Oráculo** (la carpeta real) | **0.95** | **+0.03** [+0.01, +0.06] |
| Nano | Super (dos criterios distintos) | 0.24 | **−0.68** [−0.74, −0.61] |
| Nano | **Nano** (el mismo modelo en los dos lados) | 0.43 | **−0.48** [−0.56, −0.41] |
| Nano | Oráculo | 0.41 | **−0.51** [−0.58, −0.43] |

MRR del oráculo con las carpetas del dueño: **+0.05** [+0.03, +0.07]; en projects el
hit@5 sube +0.06 [+0.01, +0.12].

**Sistema real completo** (Ultra responde, RAGAS juzga; corrida v2, de antes de las
últimas correcciones humanas, con números prácticamente iguales):

| | flat | PARA | PARA − flat |
|---|---:|---:|---|
| context precision | 0.83 | 0.43 | **−0.40** [−0.47, −0.34] |
| context recall | 0.93 | 0.46 | **−0.47** [−0.54, −0.40] |
| Abstención en las 25 sin respuesta | 25/25 | 25/25 | |
| "No sé" de más en las 200 con respuesta | 8% | 55% | |

**Qué significa (la historia para el video):**
1. Con la carpeta correcta, PARA **sí mejora** la recuperación (oráculo: hit@5 +0.03 y
   MRR +0.05, significativos): el correo correcto queda más arriba.
2. Un filtro duro exige que **archivar y buscar usen la misma taxonomía**. Con dos
   criterios distintos (Nano archiva, Super busca) es la peor configuración (0.24);
   con el mismo modelo en los dos lados casi se duplica (0.43).
3. **Pero ni así basta:** el mismo modelo no clasifica igual un correo completo que
   una pregunta corta (Nano mandó 34 de las 67 preguntas de areas a projects y 19 a
   archive), y el filtro esconde la respuesta en más de la mitad de los casos.
4. Cuando eso pasa, el sistema casi siempre dice **"no sé"** en vez de inventar. Lo
   detecta la señal de confianza de recuperación (D24).
5. RAGAS (un juez por significado) y hit@5 (por id) dan lo mismo, y los números no
   cambiaron al corregir las preguntas: el resultado es robusto.
6. La salida natural, para trabajo futuro: un **filtro suave**, que use PARA para
   ordenar los resultados y no para excluirlos.

Gasto hasta el 25 oct: ≈ US$5.7 (indexado ≈ US$0.20; corridas de solo recuperación
≈ US$0.05 cada una; corridas completas con Ultra y RAGAS ≈ US$1.5–2.2).

## 4. Cómo reproducirlo

```bash
# corpus, índices y preguntas: ver questions/README.md
# Una corrida final (shapiro-r; kaminski-v igual con enron_kaminski-v_100.jsonl)
uv run python -m scripts.run_eval --retrieval-only --router super \
    --chroma ~/dev/atlas-lab/enron/shapiro-r/chroma_folders \
    --run final250-shapiro-super --threshold 0.3 \
    --questions questions/enron_shapiro-r.jsonl \
    --questions questions/enron_shapiro-r_abstain.jsonl
# --router ultra: Ultra enruta (~US$0.08) · --oracle: la carpeta real, solo el archivo
# con respuesta · --real: además Ultra responde y RAGAS juzga (dólares)

# Las gráficas del video, desde los reportes final250-*.md (sin red)
uv run --with matplotlib python -m scripts.plot_video --out docs/video
```

El paquete para el equipo (corpus de los dos buzones, mapeos, huellas SHA-256 y, aparte,
los índices) se comparte fuera del repo: `paquete_equipo_v2.zip`.

## 5. Lo que falta antes de entregar

### Bloqueante para la entrega (plan §8, checklist de cumplimiento)

| # | Qué | Quién | Nota |
|---|---|---|---|
| 1 | **README.md completo.** Hoy solo tiene la línea de la licencia. Debe explicar el setup, cómo correrlo y dónde se usan Nemotron, Token Factory y Serverless Jobs | Todos (cada uno su sección, plan §6) | La sección de P3 puede salir de este documento y de `questions/README.md` |
| 2 | **Video ≤ 3 min** en YouTube, con audio sobre Token Factory y Nemotron | Todos | `docs/video_script.md` no existe. La historia está en la sección 3 |
| 3 | **URL pública de la demo** que no dependa de ninguna laptop | P4 | `/ask` con `SELFWARE_AGENT=real` y el índice de Enron |
| 4 | **Serverless Jobs desplegado** (requisito del track) | P1 | `ingest/jobs.py` dice "still incomplete" |
| 5 | **FEEDBACK.md** sobre Token Factory, AI Cloud y las herramientas de NVIDIA | Todos | No existe |
| 6 | **Todo en inglés**, repo público con Apache 2.0 visible, descripción en Devpost | Todos | |

### De P3 (cerrar el número)

| # | Qué | Costo |
|---|---|---|
| 7 | ~~Corrida final de solo recuperación~~ (hecha: `final-*.md`). Opcional: la completa con Ultra y RAGAS sobre las preguntas finales | ≈ US$2.2 |
| 8 | **Calibrar el umbral de abstención** con `eval/calibrate.py` (hoy es 0.30 fijado de antemano). Hace falta guardar el detalle por fila en `run_eval` | Cambio chico |
| 9 | **R18**: medir si Ultra dice "no sé" cuando la respuesta sí estaba en los fragmentos (el prompt cambió a inglés) | Sale de lo mismo que el #8 |
| 10 | Revisar a mano las **25 preguntas de abstención** (siguen `ai-drafted`) | ~20 min |
| 11 | Gráficas finales para el video, a partir de los reportes | |
| 12 | Declarar en el README que **Tavily se recortó** (D37) | |

### De los demás

| # | Qué | Quién |
|---|---|---|
| 13 | Revisar y aprobar los commits *for Person 2* y *for Person 4* de esta rama | P2, P4 |
| 14 | **Decidir qué hacer con el clasificador**, el hallazgo principal. La corrida Nano + Nano muestra que el problema es la consistencia entre archivar y buscar, más que un modelo en particular. Opciones: dejarlo como resultado, o probar un filtro suave que complete con flat. Si se cambia después de ver los resultados, hay que declararlo | P2 + equipo |
| 15 | Formatear 5 archivos de `context/` para que el CI quede en verde (`ruff format`) | P2 |
| 16 | Fusionar `p1/full-ingestion`: choca con `core/schemas.py` (`ContextItem`) y duplica los pines de RAGAS en `pyproject.toml` | P1 |

### Riesgos

- **Fecha:** quedan 5 días y el video, el README y la demo pública no existen todavía.
- **Las etiquetas PARA son nuestra interpretación** de las carpetas de otra persona
  (declarado en `questions/README.md`).
- **Efecto techo:** flat acierta el 92%, lo que deja poco margen para que PARA gane.
  Por eso la mejora del oráculo es chica (+3 puntos), aunque significativa.
- El corpus de Enron es público, pero es **correo real** de personas: no se publica
  el corpus, solo las preguntas.
