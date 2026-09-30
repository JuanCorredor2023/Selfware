import { bandFor } from "../lib/confidence";
import ConfidenceMeter from "./ConfidenceMeter";
import ProvenanceList from "./ProvenanceList";
import Icon from "./Icon";

// Shows one answer: question, strategy used, confidence, web tag, text and
// sources. `stale` dims the previous answer while a new one is loading.
export default function AnswerCard({ result, stale }) {
  const { answer, question, strategy } = result;
  const low = bandFor(answer.confidence) === "low";
  return (
    <article className={`answer${low ? " answer--low" : ""}${stale ? " is-stale" : ""}`} aria-busy={stale}>
      <header className="answer__header">
        <p className="answer__question">{question}</p>
        <div className="answer__badges">
          <span className="tag">Answered with {strategy === "para" ? "PARA" : "Flat"}</span>
          {answer.used_web && (
            <span className="tag tag--web"><Icon name="globe" size={12} /> Web search used</span>
          )}
        </div>
        <ConfidenceMeter confidence={answer.confidence} />
      </header>
      {low && <p className="answer__unsure">I'm not sure about this one.</p>}
      <p className="answer__text">{answer.text}</p>
      <ProvenanceList chunks={answer.provenance} />
    </article>
  );
}
