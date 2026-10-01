// PARA helpers shared by the tracker, chips and provenance list.
export const PARA_CATEGORIES = ["projects", "areas", "resources", "archive"];

export const PARA_LABEL = {
  projects: "Projects",
  areas: "Areas",
  resources: "Resources",
  archive: "Archive",
  web: "Web",
};

// "projects/thesis" -> "projects". Anything that is not a PARA folder
// (for example web results) is reported as "web".
export function categoryOf(paraPath) {
  const first = String(paraPath).split("/")[0];
  return PARA_CATEGORIES.includes(first) ? first : "web";
}

// MOCK CONVENTION: web results come back as chunks whose item_id starts
// with "web:". Confirm against the real agent's contract (C3) before
// wiring the API; if it differs, this is the only place to change.
export function isWebChunk(chunk) {
  return String(chunk.item_id).startsWith("web:");
}
