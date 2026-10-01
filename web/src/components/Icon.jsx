// Minimal inline icon set (stroke icons, inherit currentColor). Icons are
// decorative: every control that uses one also has a text label.
const PATHS = {
  ask: "M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  cost: "M4 20V10m6 10V4m6 16v-7m4 7H2",
  warning: "M12 3 2 20h20zM12 10v4m0 3h.01",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9S9.5 5.6 12 3z",
  chevron: "m9 6 6 6-6 6",
  panel: "M3 5h18v14H3zM15 5v14",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
};

export default function Icon({ name, size = 16 }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
