// Aggregates TierCall records (contract C4) into what the cost panel shows.
// The future GET /cost endpoint should return this same shape, computed on
// the server from the real TierCalls.

// Model tier from the model id. Ids mirror observability/cost.py.
export function tierOf(model) {
  const id = String(model).toLowerCase();
  if (id.includes("ultra")) return "ultra";
  if (id.includes("nano")) return "nano";
  return "other";
}

export const TIER_LABEL = {
  nano: "Nemotron Nano",
  ultra: "Nemotron Ultra",
  other: "Other",
};

/**
 * @param {Array<{model:string,tokens_in:number,tokens_out:number,latency_ms:number,cost_usd:number}>} calls
 * @param {number} queryCount number of user questions that produced the calls
 */
export function aggregateCalls(calls, queryCount) {
  const tiers = {};
  let totalUsd = 0;
  let tokensIn = 0;
  let tokensOut = 0;
  let latency = 0;

  for (const c of calls) {
    const key = tierOf(c.model);
    const t = (tiers[key] ??= { tier: key, calls: 0, costUsd: 0, tokensIn: 0, tokensOut: 0 });
    t.calls += 1;
    t.costUsd += c.cost_usd;
    t.tokensIn += c.tokens_in;
    t.tokensOut += c.tokens_out;
    totalUsd += c.cost_usd;
    tokensIn += c.tokens_in;
    tokensOut += c.tokens_out;
    latency += c.latency_ms;
  }

  const tierList = Object.values(tiers)
    .map((t) => ({
      ...t,
      label: TIER_LABEL[t.tier],
      callShare: calls.length ? t.calls / calls.length : 0,
      costShare: totalUsd ? t.costUsd / totalUsd : 0,
    }))
    .sort((a, b) => b.costUsd - a.costUsd);

  return {
    totalUsd,
    perQueryUsd: queryCount ? totalUsd / queryCount : 0,
    avgLatencyMs: calls.length ? latency / calls.length : 0,
    tokensIn,
    tokensOut,
    callCount: calls.length,
    queryCount,
    tiers: tierList,
  };
}
