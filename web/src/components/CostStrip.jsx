import { formatPercent, formatUsd } from "../lib/format";
import Icon from "./Icon";

// One-line cost summary shown in the header when the right rail is not
// visible (below 1280px). The button opens the full panel where it is a drawer.
export default function CostStrip({ summary, onOpen }) {
  const nano = summary.tiers.find((t) => t.tier === "nano");
  const ultra = summary.tiers.find((t) => t.tier === "ultra");
  return (
    <div className="strip">
      <span className="strip__item"><span className="strip__label">Total</span> <span className="mono">{formatUsd(summary.total_usd)}</span></span>
      <span className="strip__item"><span className="strip__label">Per query</span> <span className="mono">{formatUsd(summary.per_query_usd)}</span></span>
      <span className="strip__item"><span className="strip__label">Nano / Ultra</span> <span className="mono">{formatPercent(nano?.cost_share ?? 0)} / {formatPercent(ultra?.cost_share ?? 0)}</span></span>
      <button type="button" className="btn btn--ghost strip__open" onClick={onOpen}>
        <Icon name="panel" /> Cost details
      </button>
    </div>
  );
}
