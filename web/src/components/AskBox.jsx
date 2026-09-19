import { useState } from "react";

// TODO(person-4): move to a real environment variable (Vite .env)
// before deploying. Hardcoded to localhost for now since the API runs
// locally.
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
      if (!res.ok) throw new Error(`API responded ${res.status}`);
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
      <h2>Ask</h2>
      <p className="hint">
        Today this is answered by a simulated agent (api/_mock_agent.py) —
        the real one belongs to Person 3.
      </p>
      <form onSubmit={handleAsk} className="ask-form">
        <input
          type="text"
          placeholder="Ask something about your email..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          <option value="para">PARA</option>
          <option value="flat">Flat</option>
        </select>
        <button type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Asking…" : "Ask"}
        </button>
      </form>

      {status === "error" && (
        <p className="error">
          Could not connect to the API at {API_BASE}. Is{" "}
          <code>uvicorn api.app:app --reload</code> running?
        </p>
      )}

      {answer && (
        <div className="answer">
          <p className="answer__text">{answer.text}</p>
          <p className="answer__confidence">
            confidence: {(answer.confidence * 100).toFixed(0)}%
            {answer.used_web && " · used web search"}
          </p>
          <div className="answer__provenance">
            <strong>Provenance:</strong>
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
