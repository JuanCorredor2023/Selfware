import { formatInt, formatMs, formatPercent, formatUsd } from "../lib/format";

function Stat({ label, value }) {
  return (
    <div className="stat">
      <dt className="stat__label">{label}</dt>
      <dd className="stat__value">{value}</dd>
    </div>
  );
}

// Right rail: glanceable numbers first, per-tier detail on demand.
// `summary` is the output of aggregateCalls() (lib/cost.js).
export default function CostPanel({ summary }) {
  return (
    <section className="cost" aria-labelledby="cost-title">
      <h2 id="cost-title" className="section-title">Cost and telemetry</h2>
      <dl className="cost__stats">
        <Stat label="Total cost" value={formatUsd(summary.total_usd)} />
        <Stat label="Per query" value={formatUsd(summary.per_query_usd)} />
        <Stat label="Avg latency" value={formatMs(summary.avg_latency_ms)} />
        <Stat label="Queries" value={formatInt(summary.query_count)} />
      </dl>

      <h3 className="cost__sub">Cost by model tier</h3>
      <div className="tierbar" role="img" aria-label={summary.tiers.map((t) => `${t.label} ${formatPercent(t.cost_share)}`).join(", ")}>
        {summary.tiers.map((t) => (
          <span key={t.tier} className={`tierbar__seg tierbar__seg--${t.tier}`} style={{ flexGrow: Math.max(t.cost_share, 0.02) }} />
        ))}
      </div>
      <ul className="tierlegend">
        {summary.tiers.map((t) => (
          <li key={t.tier} className="tierlegend__row">
            <span className={`tierlegend__swatch tierbar__seg--${t.tier}`} aria-hidden="true" />
            <span className="tierlegend__name">{t.label}</span>
            <span className="tierlegend__calls">{t.calls} {t.calls === 1 ? "call" : "calls"}</span>
            <span className="mono">{formatPercent(t.cost_share)}</span>
          </li>
        ))}
      </ul>

      <details className="cost__details">
        <summary>Tokens and calls per tier</summary>
        <table className="cost__table">
          <thead>
            <tr><th scope="col">Tier</th><th scope="col">Calls</th><th scope="col">In</th><th scope="col">Out</th><th scope="col">Cost</th></tr>
          </thead>
          <tbody>
            {summary.tiers.map((t) => (
              <tr key={t.tier}>
                <th scope="row">{t.label}</th>
                <td>{t.calls}</td>
                <td>{formatInt(t.tokens_in)}</td>
                <td>{formatInt(t.tokens_out)}</td>
                <td>{formatUsd(t.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
