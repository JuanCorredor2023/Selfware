import { useState } from "react";
import { API_BASE, USE_MOCKS, askQuestion, fetchCost, fetchPara } from "../api/client";
import AppShell from "../components/AppShell";
import AskBox from "../components/AskBox";
import AnswerCard from "../components/AnswerCard";
import ParaTracker from "../components/ParaTracker";
import CostPanel from "../components/CostPanel";
import CostStrip from "../components/CostStrip";
import Icon from "../components/Icon";
import { EMPTY_SUMMARY } from "../lib/cost";
import { EXAMPLE_QUESTIONS } from "../mocks/answers";
import { useResource } from "../lib/useResource";

// The only view today. All data goes through src/api/client.js: the real
// FastAPI app by default, or src/mocks/ when VITE_USE_MOCKS=true.
export default function DashboardView() {
  const [question, setQuestion] = useState("");
  const [strategy, setStrategy] = useState("para");
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [errorMessage, setErrorMessage] = useState("");
  const [result, setResult] = useState(null); // { answer, question, strategy }

  const para = useResource(fetchPara);
  const cost = useResource(fetchCost);
  const summary = cost.data ?? EMPTY_SUMMARY;

  async function ask(text = question) {
    const q = text.trim();
    if (!q) return;
    setQuestion(q);
    setStatus("loading");
    try {
      const answer = await askQuestion(q, strategy);
      setResult({ answer, question: q, strategy });
      setStatus("idle");
      cost.reload(); // the API just recorded this question's calls
    } catch (err) {
      console.error(err);
      setErrorMessage(err.message);
      setStatus("error");
    }
  }

  const loading = status === "loading";

  const main = (
    <div className="stage">
      <AskBox
        question={question}
        onQuestionChange={setQuestion}
        strategy={strategy}
        onStrategyChange={setStrategy}
        onAsk={() => ask()}
        loading={loading}
      />

      <div className="stage__live" aria-live="polite">
        {loading && !result && <div className="skeleton" role="status">Searching your email...</div>}
        {loading && result && <p className="progress" role="status">Asking with {strategy === "para" ? "PARA" : "Flat"}...</p>}

        {status === "error" && (
          <div className="notice notice--error" role="alert">
            <Icon name="warning" />
            <div>
              <p>
                <strong>Couldn't get an answer.</strong> {errorMessage}{" "}
                {!USE_MOCKS && <>Check that the API is running (<code className="mono">uvicorn api.app:app --reload</code>) and try again.</>}
              </p>
              <button type="button" className="btn btn--secondary" onClick={() => ask()}>
                <Icon name="refresh" /> Retry
              </button>
            </div>
          </div>
        )}

        {result && <AnswerCard result={result} stale={loading} />}

        {!result && status === "idle" && (
          <div className="empty">
            <h2 className="empty__title">Ask your first question</h2>
            <p className="empty__text">Atlas searches your email and shows where every answer came from. Try one of these:</p>
            <ul className="empty__examples">
              {EXAMPLE_QUESTIONS.map((q) => (
                <li key={q}>
                  <button type="button" className="btn btn--secondary" onClick={() => ask(q)}>{q}</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {USE_MOCKS && <p className="progress">Mock mode: the API at {API_BASE} is not being used.</p>}
    </div>
  );

  return (
    <AppShell
      left={<ParaTracker tree={para.data} status={para.status} onRetry={para.reload} />}
      main={main}
      right={<CostPanel summary={summary} status={cost.status} onRetry={cost.reload} />}
      strip={(openDrawer) => <CostStrip summary={summary} onOpen={openDrawer} />}
    />
  );
}
