const dateFormat = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

// Accepts "2026-09-17" or a full ISO timestamp.
export function formatDate(value) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : dateFormat.format(d);
}

export function formatUsd(value) {
  return `$${value.toFixed(4)}`;
}

export function formatMs(value) {
  return `${Math.round(value)}ms`;
}

export function formatPercent(fraction) {
  return `${Math.round(fraction * 100)}%`;
}

export function formatInt(value) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}
