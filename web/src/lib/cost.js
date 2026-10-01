// Aggregates TierCall records (contract C4) into what the cost panel shows.
// Until the dashboard is wired to the API, this runs in the browser over the
// mocked calls. Its output has EXACTLY the shape GET /cost returns
// (src/selfware/observability/ledger.py), so wiring the real endpoint is a fetch swap.

// Model tier from the model id. Ids mirror src/selfware/core/llm.py MODEL_IDS.
export function tierOf(model) {
  const id = String(model).toLowerCase();
  if (id.includes("ultra")) return "ultra";
  if (id.includes("super")) return "super";
  if (id.includes("qwen")) return "judge";
  if (id.includes("nano")) return "nano";
  return "other";
}

export const TIER_LABEL = {
  nano: "Nemotron Nano",
  super: "Nemotron Super",
  ultra: "Nemotron Ultra",
  judge: "Qwen3 judge",
  other: "Other",
};

/** Summary with nothing recorded yet (same shape as GET /cost on a fresh API). */
export const EMPTY_SUMMARY = {
  total_usd: 0,
  per_query_usd: 0,
  avg_latency_ms: 0,
  tokens_in: 0,
  tokens_out: 0,
  call_count: 0,
  query_count: 0,
  unpriced_calls: 0,
  tiers: [],
};

/**
 * @param {Array<{model:string,tokens_in:number,tokens_out:number,latency_ms:number,cost_usd:number}>} calls
 * @param {number} queryCount number of user questions that produced the calls
 */
export function aggregateCalls(calls, queryCount) {
  const byTier = {};
  let total_usd = 0;
  let tokens_in = 0;
  let tokens_out = 0;
  let latency = 0;

  for (const c of calls) {
    const key = tierOf(c.model);
    const t = (byTier[key] ??= { tier: key, calls: 0, cost_usd: 0, tokens_in: 0, tokens_out: 0 });
    t.calls += 1;
    t.cost_usd += c.cost_usd;
    t.tokens_in += c.tokens_in;
    t.tokens_out += c.tokens_out;
    total_usd += c.cost_usd;
    tokens_in += c.tokens_in;
    tokens_out += c.tokens_out;
    latency += c.latency_ms;
  }

  const tiers = Object.values(byTier)
    .map((t) => ({
      ...t,
      label: TIER_LABEL[t.tier],
      call_share: calls.length ? t.calls / calls.length : 0,
      cost_share: total_usd ? t.cost_usd / total_usd : 0,
    }))
    .sort((a, b) => b.cost_usd - a.cost_usd);

  return {
    total_usd,
    per_query_usd: queryCount ? total_usd / queryCount : 0,
    avg_latency_ms: calls.length ? latency / calls.length : 0,
    tokens_in,
    tokens_out,
    call_count: calls.length,
    query_count: queryCount,
    // Calls on a model with no price list entry (their cost is reported as 0).
    unpriced_calls: calls.filter((c) => tierOf(c.model) === "other").length,
    tiers,
  };
}
