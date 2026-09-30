import { useEffect, useRef } from "react";
import StrategyControl from "./StrategyControl";

// The question input. State (question, strategy) lives in the parent view so
// example questions and re-asking can drive it.
export default function AskBox({ question, onQuestionChange, strategy, onStrategyChange, onAsk, loading }) {
  const ref = useRef(null);

  // Auto-grow the textarea with its content.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [question]);

  const canSubmit = question.trim().length > 0 && !loading;

  function submit(e) {
    e.preventDefault();
    if (canSubmit) onAsk();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
  }

  return (
    <form className="ask" onSubmit={submit}>
      <label htmlFor="ask-input" className="sr-only">Your question</label>
      <textarea
        id="ask-input"
        ref={ref}
        rows={2}
        className="ask__input"
        placeholder="Ask something about your email..."
        value={question}
        onChange={(e) => onQuestionChange(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className="ask__bar">
        <StrategyControl value={strategy} onChange={onStrategyChange} disabled={loading} />
        <span className="ask__hint" aria-hidden="true">⌘ / Ctrl + Enter</span>
        <button type="submit" className="btn btn--primary" disabled={!canSubmit}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </div>
    </form>
  );
}
