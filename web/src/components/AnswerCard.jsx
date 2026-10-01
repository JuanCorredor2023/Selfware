import { bandFor } from "../lib/confidence";
import ConfidenceMeter from "./ConfidenceMeter";
import ProvenanceList from "./ProvenanceList";
import Icon from "./Icon";

// Shows one answer: question, strategy used, confidence, web tag, text and
// sources. `stale` dims the previous answer while a new one is loading.
export default function AnswerCard({ result, stale }) {
  const { answer, question, strategy } = result;
  const low = bandFor(answer.confidence) === "low";
  // finish_reason (contract C3): "stop" is a normal end, "no_chunks" means the
  // agent had nothing to read and did not call the model, anything else
  // (for example "length") means the answer was cut short.
  const noChunks = answer.finish_reason === "no_chunks";
  const cutShort = !noChunks && Boolean(answer.finish_reason) && answer.finish_reason !== "stop";
  return (
    <article className={`answer${low ? " answer--low" : ""}${stale ? " is-stale" : ""}`} aria-busy={stale}>
      <header className="answer__header">
        <p className="answer__question">{question}</p>
        <div className="answer__badges">
          <span className="tag">Answered with {strategy === "para" ? "PARA" : "Flat"}</span>
          {cutShort && (
            <span className="tag"><Icon name="warning" size={12} /> Answer cut short</span>
          )}
          {answer.used_web && (
            <span className="tag tag--web"><Icon name="globe" size={12} /> Web search used</span>
          )}
        </div>
        <ConfidenceMeter confidence={answer.confidence} />
      </header>
      {low && <p className="answer__unsure">I'm not sure about this one.</p>}
      <p className="answer__text">
        {noChunks ? "I found nothing in your email for this question." : answer.text}
      </p>
      <ProvenanceList chunks={answer.provenance} />
    </article>
  );
}
