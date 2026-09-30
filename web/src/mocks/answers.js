// Mock of what GET /ask returns (contract C3: Answer). Flat and PARA return
// plausibly DIFFERENT answers on purpose, so the strategy control visibly
// changes something during the demo:
//   PARA -> fewer, on-topic chunks from the right folder, higher confidence
//   Flat -> mixed chunks (including stale or unrelated ones), lower confidence
// A question that matches no topic gets the low-confidence + web fallback.
//
// Special input for previewing the error state: start a question with "!error".
import { NANO, ULTRA, makeCall } from "./tierCalls";

export const EXAMPLE_QUESTIONS = [
  "When is my thesis defense?",
  "What is the status of the year-end trip?",
  "What is the hackathon submission deadline?",
  "How do I rotate a JWT signing key?",
];

const chunk = (text, item_id, para_path, ts, score) => ({ text, item_id, para_path, ts, score });

const TOPICS = [
  {
    match: /thesis|advisor|defen[cs]e|committee/i,
    para: {
      text: "Your thesis defense is on October 22, 2026 at 10:00. Dr. Ramirez confirmed the committee and asked for the final draft two weeks before the date.",
      confidence: 0.93,
      provenance: [
        chunk("Confirming the defense for Thursday, October 22 at 10:00 in room B-204. The committee is Ramirez, Ortiz and Vega.", "msg-3812", "projects/thesis", "2026-09-24T14:12:00Z", 0.94),
        chunk("Please send the final draft no later than October 8 so the committee can read it before the defense.", "msg-3790", "projects/thesis", "2026-09-19T09:40:00Z", 0.89),
        chunk("Reminder: the defense slides must be uploaded to the department portal 48 hours in advance.", "msg-3744", "projects/thesis", "2026-09-11T17:05:00Z", 0.81),
        chunk("Graduation paperwork opens the week after the defense; bring your student ID.", "msg-3611", "areas/university", "2026-09-02T11:30:00Z", 0.72),
      ],
    },
    flat: {
      text: "Your thesis defense appears to be in October, but the emails disagree: one mentions October 22 and an older one proposed a date in November. The most recent message says October 22.",
      confidence: 0.71,
      provenance: [
        chunk("Confirming the defense for Thursday, October 22 at 10:00 in room B-204.", "msg-3812", "projects/thesis", "2026-09-24T14:12:00Z", 0.86),
        chunk("We could tentatively schedule the defense for the second week of November, pending the committee.", "msg-3402", "areas/university", "2026-08-14T08:20:00Z", 0.79),
        chunk("Weekly digest: three new papers on retrieval evaluation and a defense-day checklist template.", "msg-3701", "resources/ml-papers", "2026-09-08T06:00:00Z", 0.68),
        chunk("Final presentation for the internship is scheduled for Friday at 15:00.", "msg-1954", "archive/summer-internship-2025", "2025-08-28T16:45:00Z", 0.61),
      ],
    },
    calls: {
      para: [makeCall(NANO, 610, 95, 310), makeCall(ULTRA, 1850, 210, 1400)],
      flat: [makeCall(ULTRA, 3120, 235, 1930)],
    },
  },
  {
    match: /trip|flight|hotel|travel|vacation/i,
    para: {
      text: "The year-end trip is on hold. The last email (July 2) has a round-trip flight quote of $412 that expired on August 15, and nothing has been booked since.",
      confidence: 0.88,
      provenance: [
        chunk("Flight quote: round trip, December 20 to January 3, $412 per person. Valid until August 15.", "msg-2988", "projects/year-end-trip", "2026-07-02T10:15:00Z", 0.92),
        chunk("Let's decide about the hotel once we know the flights. Holding off for now.", "msg-2971", "projects/year-end-trip", "2026-06-28T19:02:00Z", 0.84),
      ],
    },
    flat: {
      text: "There is a flight quote of $412 for December, but I also found an unrelated apartment listing and a hotel receipt from an old trip, so I can't tell whether anything is booked.",
      confidence: 0.63,
      provenance: [
        chunk("Flight quote: round trip, December 20 to January 3, $412 per person.", "msg-2988", "projects/year-end-trip", "2026-07-02T10:15:00Z", 0.83),
        chunk("Your hotel reservation has been confirmed. Check-in: March 3, 2024.", "msg-1102", "archive/apartment-2024", "2024-02-10T12:00:00Z", 0.70),
        chunk("Monthly statement: travel and lodging category totals.", "msg-3655", "areas/finances", "2026-09-05T07:30:00Z", 0.64),
      ],
    },
    calls: {
      para: [makeCall(NANO, 590, 90, 300), makeCall(ULTRA, 1420, 180, 1250)],
      flat: [makeCall(ULTRA, 2860, 210, 1780)],
    },
  },
  {
    match: /hackathon|atlas|nebius|nvidia|submission|deadline/i,
    para: {
      text: "The hackathon submission deadline is October 27. Your team agreed to freeze features on October 20 and record the demo video by October 24.",
      confidence: 0.9,
      provenance: [
        chunk("Reminder: submissions close October 27 at 23:59 UTC. Include the repo link, video and a short write-up.", "msg-3830", "projects/atlas-hackathon", "2026-09-29T08:00:00Z", 0.95),
        chunk("Proposed timeline: feature freeze Oct 20, demo video Oct 24, buffer for fixes until the 27th.", "msg-3821", "projects/atlas-hackathon", "2026-09-27T21:14:00Z", 0.88),
        chunk("Judges will review the repository, so keep it in English and document how to run it.", "msg-3760", "projects/atlas-hackathon", "2026-09-15T13:22:00Z", 0.79),
      ],
    },
    flat: {
      text: "The submission deadline seems to be October 27, but I also see a different deadline from a newsletter about another competition, so treat this with caution.",
      confidence: 0.74,
      provenance: [
        chunk("Reminder: submissions close October 27 at 23:59 UTC.", "msg-3830", "projects/atlas-hackathon", "2026-09-29T08:00:00Z", 0.87),
        chunk("Call for entries: the ML systems competition closes on November 3. Register now.", "msg-3699", "resources/ml-papers", "2026-09-07T06:00:00Z", 0.75),
        chunk("Deadline to file the university enrollment form is October 1.", "msg-3688", "areas/university", "2026-09-06T09:10:00Z", 0.66),
      ],
    },
    calls: {
      para: [makeCall(NANO, 620, 92, 305), makeCall(ULTRA, 1760, 190, 1330)],
      flat: [makeCall(ULTRA, 3300, 220, 1990)],
    },
  },
];

function fallback(question, strategy) {
  const web = (host, path, snippet, score) =>
    chunk(snippet, `web:${host}${path}`, "web", "2026-09-29T12:00:00Z", score);
  const isPara = strategy === "para";
  return {
    text: `I couldn't find this in your email, so I searched the web. The results below cover the topic in general terms; I could not check them against anything you wrote, so please verify before relying on them.`,
    confidence: isPara ? 0.38 : 0.31,
    used_web: true,
    provenance: [
      chunk(`Newsletter mentioning a topic related to “${question}”, without the details you asked about.`, "msg-3702", isPara ? "resources/ml-papers" : "areas/university", "2026-09-08T06:00:00Z", isPara ? 0.34 : 0.29),
      web("docs.example.org", "/guide", `Reference guide with a step-by-step explanation related to “${question}”.`, 0.81),
      web("stackoverflow.example.com", "/questions/1234", `Community answer summarizing the common approach and its caveats.`, 0.74),
    ],
    tier_calls: isPara
      ? [makeCall(NANO, 600, 90, 300), makeCall(ULTRA, 1500, 170, 1300), makeCall(ULTRA, 2300, 260, 1800)]
      : [makeCall(ULTRA, 3000, 210, 1850), makeCall(ULTRA, 2300, 260, 1800)],
  };
}

export function mockAnswer(question, strategy) {
  const topic = TOPICS.find((t) => t.match.test(question));
  if (!topic) return fallback(question, strategy);
  const variant = strategy === "flat" ? topic.flat : topic.para;
  return {
    ...variant,
    used_web: false,
    tier_calls: strategy === "flat" ? topic.calls.flat : topic.calls.para,
  };
}

// Simulates the network call so the loading state is visible.
export function askMock(question, strategy) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (question.trim().startsWith("!error")) {
        reject(new Error("Simulated failure"));
      } else {
        resolve(mockAnswer(question, strategy));
      }
    }, 900);
  });
}
