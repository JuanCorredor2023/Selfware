import { formatDate } from "../lib/format";
import { isWebChunk } from "../lib/para";
import ParaChip from "./ParaChip";
import Icon from "./Icon";

function ChunkItem({ chunk }) {
  const web = isWebChunk(chunk);
  // Web chunks show the host; email chunks show the PARA path.
  const label = web ? chunk.item_id.replace(/^web:/, "").split("/")[0] : chunk.para_path;
  return (
    <li>
      <details className="chunk">
        <summary className="chunk__summary">
          <Icon name="chevron" size={14} />
          <ParaChip path={chunk.para_path} label={label} />
          <span className="chunk__meta">{formatDate(chunk.ts)}</span>
          <span className="chunk__meta chunk__score">score {chunk.score.toFixed(2)}</span>
        </summary>
        <p className="chunk__text">{chunk.text}</p>
        <p className="chunk__id">{chunk.item_id}</p>
      </details>
    </li>
  );
}

// Source chunks behind an answer, collapsed by default, best score first.
// Email sources and web sources are listed under separate headings.
export default function ProvenanceList({ chunks }) {
  const sorted = [...chunks].sort((a, b) => b.score - a.score);
  const email = sorted.filter((c) => !isWebChunk(c));
  const web = sorted.filter(isWebChunk);

  return (
    <section className="provenance" aria-labelledby="provenance-title">
      <h3 id="provenance-title" className="section-title">Sources</h3>
      {email.length > 0 && (
        <>
          <h4 className="provenance__group">From your email</h4>
          <ul className="provenance__list">{email.map((c) => <ChunkItem key={c.item_id} chunk={c} />)}</ul>
        </>
      )}
      {web.length > 0 && (
        <>
          <h4 className="provenance__group">From the web</h4>
          <ul className="provenance__list">{web.map((c) => <ChunkItem key={c.item_id} chunk={c} />)}</ul>
        </>
      )}
    </section>
  );
}
