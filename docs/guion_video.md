# Guion del video final (borrador v2, 29 oct)

Requisito: video público en YouTube de **3 minutos o menos** que muestre el proyecto
funcionando, cómo usamos Nebius Token Factory y Nemotron (u otros modelos abiertos de
NVIDIA) y, como no hay hardware, **al menos un minuto de los módulos clave en acción**.

Duración objetivo: **~2:50** (narración ~2:45 a ~150 palabras por minuto). Narración en
inglés, indicaciones en español. Números: corridas finales `final250-*` (100 preguntas
con respuesta por buzón, `docs/avances_p3.md` §3.1). Gráficas: `docs/video/*.png`
(`scripts/plot_video.py`).

---

## 0:00–0:15 · El problema

🎬 *Una bandeja de entrada saturada desplazándose rápido.*

> "Your inbox already knows the answers — the budget someone confirmed, the date a
> meeting moved, who owns a project. Finding them is the hard part. Atlas turns your
> email into a second brain you can ask."

## 0:15–0:30 · Qué es Atlas

🎬 *El dashboard abierto, en modo real.*

> "Atlas files every email into PARA — Projects, Areas, Resources, Archive — and lets
> you ask in plain language. Every answer comes with the emails behind it."

## 0:30–1:40 · Demo: los módulos funcionando (≥ 1 min, lo que exige la regla)

🎬 *Grabación de pantalla continua, sin cortes falsos. API con `SELFWARE_AGENT=real`.*

1. **(0:30) Ingesta.** Terminal: `scripts.index_emails --demo` sobre los correos
   inventados. Primero imprime la estimación de costo; con `--yes` clasifica cada correo
   con Nano y lo indexa.
   > "New mail is classified into a PARA folder by Nemotron Nano and embedded with Qwen3
   > Embedding — and the script tells you what it will cost before it spends anything."
2. **(0:50) Pregunta** en el AskBox, una que sí está en los correos. Aparece la respuesta
   con su procedencia (correo, fecha, carpeta) y el medidor de confianza.
   > "Nemotron Super picks the folder to search, Nemotron Ultra writes the answer, and
   > every claim links back to the email it came from."
3. **(1:10) Toggle flat ↔ PARA** con la misma pregunta.
   > "You can search the whole mailbox, or only the folder PARA picked."
4. **(1:20) Abstención.** Una pregunta cuya respuesta no está; Atlas dice que no lo sabe.
   > "When the evidence isn't there, Atlas says so. Its confidence comes from Ultra's
   > token log-probabilities, and the threshold lives in code, not in the prompt."
5. **(1:30) Panel de costo**: dólares, tokens y latencia por modelo, con la llamada de
   Super para enrutar incluida.
   > "Every call is metered per model, in real time."

## 1:40–2:00 · Cómo usamos Nebius Token Factory y Nemotron

🎬 *El diagrama de la arquitectura del README: correo → Nano → índice; pregunta → Super →
filtro → Ultra → respuesta; `core/llm.py` como única puerta a Token Factory.*

> "Every model call goes through one client to Nebius Token Factory. Three Nemotron
> sizes, each where it pays off: Nano files emails cheaply, Super routes questions,
> Ultra answers with log-probs for calibrated abstention. Qwen3 Embedding builds the
> index, and Qwen3-235B, a different model family, served as an independent judge in our
> full evaluation runs. The whole evaluation cost about six dollars."

## 2:00–2:45 · Evaluación honesta

🎬 *(2:00) `1_hit_at_5.png`.*

> "We tested the core idea on the public Enron corpus: two real mailboxes, 250
> questions, 200 of them checked by hand against their source email."

🎬 *(2:10) `2_oracle_gain.png`.*

> "When a question goes to the folder the owner actually used, PARA ranks the answer
> higher in both mailboxes — MRR up five and two points, statistically significant.
> Flat search already finds over ninety percent, so the gain is in ranking."

🎬 *(2:22) `3_routing.png`.*

> "But today's routers pick the wrong folder. Nemotron Super sends most questions to
> Resources, and Nemotron Ultra, four times bigger, does it even more. Neither gets a
> single Areas question right — so in practice the filter hides the answer, and flat
> search wins.
> Routing, not the model, is the bottleneck. Next, we'll let the user's own context
> choose the folder."

## 2:45–2:55 · Cierre

🎬 *Logo, URL del repo y de la demo.*

> "Atlas: ask your inbox. Built on Nemotron and Nebius Token Factory."

---

## Números que dice la narración (de `docs/avances_p3.md` §3.1)

| Frase | Dato |
|---|---|
| "two real mailboxes, 250 questions, 200 checked by hand" | Kaminski 100 + 25 y Shapiro 100 + 25; las 50 sin respuesta siguen `ai-drafted` |
| "MRR up five and two points, significant" | Oráculo: +0.05 [+0.02, +0.09] y +0.02 [+0.01, +0.04] |
| "Flat already finds over ninety percent" | hit@5 de flat: 0.91 y 0.95 |
| "Super sends most questions to Resources" | 73% y 80% de las preguntas; Ultra 86% y 94% |
| "Neither gets a single Areas question right" | 0/66 con Super y con Ultra |
| "the filter hides the answer, and flat search wins" | hit@5 de PARA: 0.38–0.48 contra 0.91–0.95 |
| "about six dollars" | ≈ US$6.1 en total, desde el 25 oct |

## Antes de grabar

- [ ] **La demo es real**: API con `SELFWARE_AGENT=real` y `SELFWARE_CHROMA_PATH` apuntando
  al índice de demo, y dashboard sin `VITE_USE_MOCKS`.
- [ ] **No mostrar el árbol PARA del dashboard como real.** `/para`, `/projects`, etc.
  siguen saliendo de `api/_mock_para.py`. La carpeta que sí es real es la que viene en
  la procedencia de cada respuesta.
- [ ] **Privacidad.** Grabar con el índice de `--demo` (correos inventados), en una
  carpeta propia (`--chroma-path chroma_demo`). Si se usa el índice de Enron, no acercar
  la cámara a datos personales.
- [ ] Elegir de antemano la pregunta con respuesta y la de abstención, y probarlas: con
  una docena de correos, flat y PARA pueden dar lo mismo. Eso está bien; el contraste
  está en la parte de evaluación.
- [ ] **Serverless Jobs:** el README dice que `ingest/jobs.py` es la entrada de una
  ingesta programada. Mencionarlo en el video solo si de verdad corre en Nebius
  Serverless Jobs.
- [ ] **Demo pública:** el despliegue en VM está en la rama `main-vm` (`deploy/`); la URL
  va en el cierre y en la descripción del video.
- [ ] **≤ 3:00 y público en YouTube.** Grabar a ~2:45 para tener margen.
- [ ] El filtro suave y el enrutamiento con el contexto del usuario son trabajo futuro:
  no mostrarlos como funciones de la app.
