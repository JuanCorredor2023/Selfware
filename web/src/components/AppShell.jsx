import { useState } from "react";
import Icon from "./Icon";

const TABS = [
  { id: "ask", label: "Ask", icon: "ask" },
  { id: "projects", label: "Projects", icon: "folder" },
  { id: "cost", label: "Cost", icon: "cost" },
];

// Responsive frame. The three regions are always in the DOM; CSS decides
// what is visible at each width (see DESIGN.md > Layout):
//   >= 1280px  three columns
//   1024-1279  icon rail + main, cost rail as a slide-over drawer
//   < 1024     one column, bottom tab bar switches between the regions
export default function AppShell({ left, main, right, strip }) {
  const [view, setView] = useState("ask");
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="shell" data-view={view} data-drawer={drawerOpen ? "open" : "closed"}>
      <aside className="shell__left" aria-label="PARA tracker">{left}</aside>

      <div className="shell__center">
        <header className="header">
          <h1 className="header__brand">Atlas</h1>
          {strip(() => setDrawerOpen(true))}
        </header>
        <main className="shell__main">{main}</main>
      </div>

      <aside className="shell__right" aria-label="Cost and telemetry">
        <button type="button" className="btn btn--ghost shell__close" onClick={() => setDrawerOpen(false)}>
          Close
        </button>
        {right}
      </aside>
      <div className="shell__scrim" onClick={() => setDrawerOpen(false)} aria-hidden="true" />

      <nav className="tabbar" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tabbar__item${view === t.id ? " is-active" : ""}`}
            aria-current={view === t.id ? "page" : undefined}
            onClick={() => setView(t.id)}
          >
            <Icon name={t.icon} size={20} />
            <span>{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
