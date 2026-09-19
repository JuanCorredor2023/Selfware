import { useState } from "react";

// TODO(persona-4): mover a variable de entorno de verdad (.env de Vite)
// antes de desplegar. Por ahora localhost porque la API corre local.
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AskBox() {
  const [question, setQuestion] = useState("");
  const [strategy, setStrategy] = useState("para");
  const [answer, setAnswer] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | error

  async function handleAsk(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setStatus("loading");
    setAnswer(null);
    try {
      const url = `${API_BASE}/ask?q=${encodeURIComponent(question)}&strategy=${strategy}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`API respondió ${res.status}`);
      const data = await res.json();
      setAnswer(data);
      setStatus("idle");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }

  return (
    <section className="panel">
      <h2>Preguntar</h2>
      <p className="hint">
        Hoy responde un agente simulado (api/_mock_agent.py) — el real es
        de Persona 3.
      </p>
      <form onSubmit={handleAsk} className="ask-form">
        <input
          type="text"
          placeholder="Pregunta algo sobre tu correo..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          <option value="para">PARA</option>
          <option value="flat">Plano</option>
        </select>
        <button type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Preguntando…" : "Preguntar"}
        </button>
      </form>

      {status === "error" && (
        <p className="error">
          No se pudo conectar con la API en {API_BASE}. ¿Está corriendo{" "}
          <code>uvicorn api.app:app --reload</code>?
        </p>
      )}

      {answer && (
        <div className="answer">
          <p className="answer__text">{answer.text}</p>
          <p className="answer__confidence">
            confianza: {(answer.confidence * 100).toFixed(0)}%
            {answer.used_web && " · usó búsqueda web"}
          </p>
          <div className="answer__provenance">
            <strong>Procedencia:</strong>
            <ul>
              {answer.provenance.map((chunk, i) => (
                <li key={i}>
                  <code>{chunk.para_path}</code> — {chunk.text}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
