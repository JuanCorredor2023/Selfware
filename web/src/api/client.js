// The ONLY place the dashboard talks to the outside world. Components never
// call fetch: they call these three functions.
//
//   VITE_API_URL     base URL of the FastAPI app (default http://localhost:8000)
//   VITE_USE_MOCKS   "true" -> ignore the API and use src/mocks/ instead
//                    (handy for design work with no backend running)
import { askMock } from "../mocks/answers";
import { historyCalls, HISTORY_QUERY_COUNT } from "../mocks/costHistory";
import { paraTree } from "../mocks/para";
import { aggregateCalls } from "../lib/cost";

export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

export class ApiError extends Error {
  constructor(message) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson(path, params) {
  const url = new URL(path, API_BASE);
  if (params) url.search = new URLSearchParams(params).toString();

  let response;
  try {
    response = await fetch(url);
  } catch {
    // fetch only rejects when the request never got an answer
    // (API down, wrong URL, blocked by CORS).
    throw new ApiError(`Could not reach the API at ${API_BASE}.`);
  }
  if (!response.ok) {
    throw new ApiError(`The API answered with status ${response.status}.`);
  }
  return response.json();
}

// ---- Mock mode: a tiny in-browser stand-in for the API's cost ledger ----
const mockSession = { calls: [...historyCalls], queries: HISTORY_QUERY_COUNT };

/** GET /ask -> Answer (contract C3). */
export async function askQuestion(question, strategy) {
  if (USE_MOCKS) {
    const answer = await askMock(question, strategy);
    mockSession.calls.push(...answer.tier_calls);
    mockSession.queries += 1;
    return answer;
  }
  return getJson("/ask", { q: question, strategy });
}

/** GET /para -> [{ key, items: [{ id, name, email_count, last_activity, status? }] }]. */
export async function fetchPara() {
  if (USE_MOCKS) return structuredClone(paraTree);
  return getJson("/para");
}

/** GET /cost -> aggregate of every TierCall (see src/selfware/observability/ledger.py). */
export async function fetchCost() {
  if (USE_MOCKS) return aggregateCalls(mockSession.calls, mockSession.queries);
  return getJson("/cost");
}
