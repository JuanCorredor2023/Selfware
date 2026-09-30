import { useMemo, useState } from "react";
import AppShell from "../components/AppShell";
import AskBox from "../components/AskBox";
import AnswerCard from "../components/AnswerCard";
import ParaTracker from "../components/ParaTracker";
import CostPanel from "../components/CostPanel";
import CostStrip from "../components/CostStrip";
import Icon from "../components/Icon";
import { aggregateCalls } from "../lib/cost";
import { askMock, EXAMPLE_QUESTIONS } from "../mocks/answers";
import { historyCalls, HISTORY_QUERY_COUNT } from "../mocks/costHistory";
import { paraTree } from "../mocks/para";

// The only view today. Everything here is backed by mocks (src/mocks/);
// swapping in the real API later means replacing askMock, paraTree and the
// cost history with fetch calls, not touching the components.
export default function DashboardView() {
  const [question, setQuestion] = useState("");
  const [strategy, setStrategy] = useState("para");
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const [result, setResult] = useState(null); // { answer, question, strategy }
  const [calls, setCalls] = useState(historyCalls);
  const [queryCount, setQueryCount] = useState(HISTORY_QUERY_COUNT);

  const summary = useMemo(() => aggregateCalls(calls, queryCount), [calls, queryCount]);

  async function ask(text = question) {
    const q = text.trim();
    if (!q) return;
    setQuestion(q);
    setStatus("loading");
    try {
      const answer = await askMock(q, strategy);
      setResult({ answer, question: q, strategy });
      setCalls((prev) => [...prev, ...answer.tier_calls]);
      setQueryCount((n) => n + 1);
      setStatus("idle");
    } catch (err) {
      console.error(err);
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
              <p><strong>Couldn't get an answer.</strong> The request failed before the agent replied. Check your connection and try again.</p>
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
    </div>
  );

  return (
    <AppShell
      left={<ParaTracker tree={paraTree} />}
      main={main}
      right={<CostPanel summary={summary} />}
      strip={(openDrawer) => <CostStrip summary={summary} onOpen={openDrawer} />}
    />
  );
}
