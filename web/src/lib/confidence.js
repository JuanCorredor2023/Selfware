// Display bands for the confidence meter. These are DISPLAY groupings only.
// The real abstain threshold (when the agent goes to the web) is calibrated
// by the agent/eval side later; when it is known, change the numbers here
// and nowhere else.
export const CONFIDENCE_BANDS = { high: 0.85, moderate: 0.6 };

export function bandFor(confidence) {
  if (confidence >= CONFIDENCE_BANDS.high) return "high";
  if (confidence >= CONFIDENCE_BANDS.moderate) return "moderate";
  return "low";
}

export const BAND_LABEL = {
  high: "High confidence",
  moderate: "Moderate confidence",
  low: "Low confidence",
};

// How many of the 3 meter segments are filled.
export const BAND_SEGMENTS = { high: 3, moderate: 2, low: 1 };
