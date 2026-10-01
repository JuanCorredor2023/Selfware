import { NANO, ULTRA, makeCall } from "./tierCalls";

// Calls from earlier queries in the session, so the cost panel is not empty
// on first load. 5 queries: each is a small Nano step plus an Ultra answer.
export const HISTORY_QUERY_COUNT = 5;

export const historyCalls = [
  makeCall(NANO, 610, 92, 310), makeCall(ULTRA, 1820, 205, 1420),
  makeCall(NANO, 580, 88, 295), makeCall(ULTRA, 2140, 260, 1610),
  makeCall(NANO, 640, 101, 330), makeCall(ULTRA, 1760, 190, 1380),
  makeCall(NANO, 600, 95, 305), makeCall(ULTRA, 2480, 240, 1750),
  makeCall(NANO, 620, 90, 300), makeCall(ULTRA, 1900, 215, 1490),
];
