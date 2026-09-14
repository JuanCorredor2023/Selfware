# Planteamiento del proyecto — Nebius x NVIDIA Global AI Hackathon (v2)

**Track:** Personal AI
**Nombre provisional:** *Atlas*
**Equipo:** 4 personas (+1 para producto si se consigue) · **Entrega:** 30 de octubre, 10:00 PT (11:00 hora México). Entregamos el 27.

---

## 1. La idea en una frase

> Un asistente personal sobre correo que organiza el contexto del usuario en estructura PARA, **mide** si esa estructura mejora la recuperación frente a un RAG plano, **sabe cuándo no sabe** y lo muestra todo en una interfaz donde el juez ve la diferencia en vivo.

---

## 2. La hipótesis

**H1:** Clasificar el contexto personal en PARA (Projects, Areas, Resources, Archive) y filtrar la recuperación por esa estructura mejora la calidad de recuperación frente a un índice vectorial plano sobre el mismo corpus.

- **Baseline:** índice plano (AutoRAG) sobre el corpus de correo.
- **Tratamiento:** mismo corpus, clasificado en PARA por Nemotron Nano, recuperado con filtro estructural.
- **Métrica principal:** *context precision* y *context recall* (RAGAS), **reportadas por categoría de pregunta** (proyectos / áreas / recursos), no solo el global.
- **Secundarias:** latencia p95, costo por consulta, distribución de tokens por escalón (OpenTelemetry).

Reportar por categoría es el seguro: si PARA no mejora el global, casi seguro mejora en preguntas de proyectos. Siempre hay un resultado presentable.

---

## 3. Arquitectura

```
Gmail ─────┐
           ├──▶ Ingesta (Serverless Jobs)
WhoareU.md ┘      normalizar · dedup · clasificar PARA (Nemotron NANO)
                        │
                        ▼
                  Contexto  ──── dos índices VIVOS, no solo para eval
                  ├─ Índice plano ──────────────┐
                  └─ Índice + filtro PARA ──────┤
                                                ▼
                                       Estrategia de recuperación
                                                │
                                                ▼
                                  Agente de respuesta (Nemotron ULTRA)
                                  · confianza por respuesta
                                  · si confianza < umbral ──▶ Tavily (web)
                                  · procedencia: carpeta PARA + correos + fechas
                                                │
                              ┌─────────────────┴─────────────────┐
                              ▼                                   ▼
                     Dashboard (React, propio)          Evaluación (RAGAS)
                     · toggle plano vs PARA              → EL NÚMERO, por categoría
                     · procedencia visible
                     · panel de costo por escalón
                     · archivo automático

              OpenTelemetry envuelve todo: tokens, latencia, costo, escalón
```

### Mapa a la plataforma (va en el README y se dice en el video)
| Tarea | Servicio | Por qué |
|---|---|---|
| Clasificar miles de correos en PARA | **Nemotron Nano** | Barato, masivo, tarea de clasificación |
| Responder preguntas con contexto | **Nemotron 3 Ultra** | Pocas llamadas, razonamiento real |
| Ingesta batch, archivo automático, corridas de eval | **Nebius Serverless Jobs** | Asíncrono, no bloquea la app |
| Búsqueda web cuando el contexto no alcanza | **Tavily** | Bonus $3,000; requiere llamada en runtime |
| Todas las llamadas de inferencia | **Token Factory** | Cumplimiento del requisito |

---

## 4. Qué construimos

### Núcleo (sin esto no hay proyecto)
| # | Componente | Qué es |
|---|---|---|
| N1 | Conector Gmail | Uno solo. IMAP o MCP de Gmail. |
| N2 | Ingesta batch | Normalizar → dedup → clasificar PARA con Nano. Serverless Jobs. |
| N3 | Dos índices | Plano y PARA, ambos vivos en producción, no solo en eval. |
| N4 | Agente de respuesta | Ultra, con contexto recuperado y confianza por respuesta. |
| N5 | Arnés de evaluación | ~200 preguntas escritas a mano, RAGAS, OTel, resultados por categoría. |
| N6 | Dashboard | Uno. React propio. Tracker de proyectos derivado de PARA. |
| N7 | WhoareU.md | Perfil de usuario en texto plano. Se inyecta al agente. |

### Adiciones para ganar (cada una aparece en el video; orden = prioridad)
| # | Adición | Qué ataca | Costo |
|---|---|---|---|
| A1 | **Toggle en vivo** plano vs PARA sobre la misma pregunta, dos columnas | Design, Tech. Impl. | Bajo (ambos índices ya existen) |
| A2 | **Procedencia visible**: carpeta PARA + correos fuente + fechas en cada respuesta | Design, Impact | Bajo |
| A3 | **Abstención → Tavily**: confianza bajo umbral = busca en web y lo dice | Idea, bonus Tavily | Medio (calibrar umbral) |
| A4 | **Panel de costo por escalón**: % Nano vs Ultra, costo/consulta, latencia | Tech. Impl. (1er desempate) | Muy bajo con OTel |
| A5 | **Usuario externo** que lo usa dos semanas y sale 10 s en el video | Impact | Bajo en código, pedirlo YA |
| A6 | **Archivo automático**: proyecto sin actividad N días → Archive, visible | Idea | Bajo |

Regla: si una adición amenaza al núcleo, se corta la adición. A6 es la primera en caer, luego A3.

### Fuera (portafolio, después del 30 de octubre)
Descubrimiento de necesidades implícitas · generación de dashboards · segundo conector · WhatsApp/redes · Lovable en código entregado.

---

## 5. El número

> "Sobre ___ correos reales de ___ personas y ___ preguntas, PARA mejora *context recall* en preguntas de proyectos de ___ a ___ (y ___ en áreas, ___ en recursos), con el ___% de las llamadas en Nano y un costo de $___ por consulta."

**Corpus:** correo de los cuatro + el usuario externo. Si son menos de ~2,000 correos, complementar con dataset público.
**Preguntas:** ~200, escritas a mano, con respuesta conocida, etiquetadas por categoría PARA. **No las genera la IA**: si las genera un modelo, medimos qué tan bien el modelo se responde a sí mismo.

---

## 6. Carriles

| Carril | Responsable | Núcleo | Adiciones |
|---|---|---|---|
| **A. Ingesta** | ___ | N1, N2, N7 | A6 |
| **B. Contexto y recuperación** | ___ | N3, estrategia de recuperación | Soporte a A1 |
| **C. Evaluación** | ___ | N5, OTel, curvas por categoría | A4, umbral de A3 |
| **D. Producto y video** | ___ | N4, N6, guion de 3 min | A1, A2, A3 (UI), A5 |

Contratos entre carriles el **día 5** con datos falsos si hace falta. Carril D es el que más carga; si se consigue una quinta persona, va ahí.

---

## 7. Calendario

| Sem | Fechas | Hito |
|---|---|---|
| 1 | 7–13 sep | Repo público con Apache 2.0. Contratos. **Guion del video escrito.** Corpus inventariado. **Pedir usuario externo (A5).** Correo a Devpost sobre City Winner. |
| 2 | 14–20 sep | Cada carril con su pieza aislada. Primeros tests. Preguntas de eval: primeras 50. |
| 3 | 21–27 sep | **Integración fea de punta a punta.** Primera corrida RAGAS con número preliminar. |
| 4 | 28 sep–4 oct | Iterar según el número. Dashboard funcional. A1 y A2. |
| 5 | 5–11 oct | A3, A4. Corrida final de eval. **Congelar features.** |
| 6 | 12–18 oct | README, descripción, feedback para Nebius (aplicar al premio de $100 en serio). A6 si sobra tiempo. |
| 7 | 19–25 oct | **Video.** Grabar, editar, regrabar. |
| 8 | 26–30 oct | Entrega el **27**. Margen. |

---

## 8. Guion del video (3:00)

| Tiempo | Qué se ve |
|---|---|
| 0:00–0:20 | El problema. El usuario externo en pantalla diciendo qué le costaba. |
| 0:20–1:00 | Una pregunta real. Respuesta con **procedencia visible** (A2). |
| 1:00–1:40 | **El toggle** (A1): misma pregunta, plano vs PARA. El juez ve la diferencia. |
| 1:40–2:10 | **El número** por categoría. **Panel de costo** por escalón (A4): "91% Nano". |
| 2:10–2:40 | Una pregunta que el correo no responde. El sistema lo admite y va a **Tavily** (A3). |
| 2:40–3:00 | Cierre: qué es, para quién, qué medimos, repo. |

Cada semana: ¿lo que estamos construyendo sale aquí? Si no, se corta.

---

## 9. Reglas de trabajo

- **IA:** para lo que ya sabemos (boilerplate, scaffolding, wrappers, CSS). No para lo que queremos aprender (esquema, clasificación, tests de invariantes).
- **Merge:** nadie mergea código que no puede explicar línea por línea a otro del equipo. Si no, se reescribe o se borra.
- **Tests:** cada carril entrega tests con su módulo. Prueban invariantes que nosotros decidimos.
- **Video:** el juez puede evaluar solo con video y descripción. El video **es** la calificación.

---

## 10. Si no llegamos

El hackathon es un subconjunto estricto del portafolio. Mismo repo. Después del 30 de octubre: descubrimiento de necesidades, más conectores, evolución de esquemas.

El estudio de ablación con números ya es pieza de portafolio el día que termine. Blog post: *"Medimos si PARA mejora RAG sobre correo personal"*, con gráficas y repo.

---

## 11. Decisiones de hoy

1. ¿H1 como eje? Sí / No.
2. Responsable por carril.
3. ¿Cuántos correos tenemos? ¿Dataset público?
4. Gmail MCP o IMAP.
5. ¿A quién le pedimos ser el usuario externo? Se pide esta semana.
6. ¿Buscamos quinta persona para producto?
7. Nombre.
