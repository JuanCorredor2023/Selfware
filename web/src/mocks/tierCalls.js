// Builds TierCall-shaped mock records with REAL prices, so the mocked cost
// panel does the same math the real one will. Model ids and prices mirror
// observability/cost.py (USD per 1M tokens, region eu-north1).
export const NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B";
export const ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b";

const PRICE = {
  [NANO]: { input: 0.06, output: 0.24 },
  [ULTRA]: { input: 1.0, output: 3.0 },
};

export function makeCall(model, tokensIn, tokensOut, latencyMs) {
  const p = PRICE[model];
  return {
    model,
    tokens_in: tokensIn,
    tokens_out: tokensOut,
    latency_ms: latencyMs,
    cost_usd: (tokensIn * p.input + tokensOut * p.output) / 1_000_000,
  };
}
