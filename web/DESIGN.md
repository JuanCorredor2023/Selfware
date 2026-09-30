---
name: Atlas Technical Workspace
description: Design system for the Atlas (Selfware) dashboard. Dark-first, dense, technical. Source of truth for every mock and component in web/.
colors:
  dark:
    background: '#090D16'
    surface: '#0F172A'
    surface-raised: '#1E293B'
    surface-overlay: '#334155'
    border: 'rgba(148, 163, 184, 0.12)'
    border-strong: '#64748B'
    on-surface: '#E2E8F0'
    on-surface-muted: '#94A3B8'
    primary: '#4F46E5'
    on-primary: '#FFFFFF'
    accent: '#6366F1'
    accent-text: '#818CF8'
    para-projects: '#F59E0B'
    para-areas: '#10B981'
    para-resources: '#0EA5E9'
    para-archive: '#A78BFA'
    confidence-low: '#FB7185'
  light:
    background: '#F8FAFC'
    surface: '#FFFFFF'
    surface-raised: '#F1F5F9'
    surface-overlay: '#E2E8F0'
    border: '#CBD5E1'
    border-strong: '#64748B'
    on-surface: '#0F172A'
    on-surface-muted: '#475569'
    primary: '#4F46E5'
    on-primary: '#FFFFFF'
    accent: '#4F46E5'
    accent-text: '#4F46E5'
    para-projects: '#92400E'
    para-areas: '#047857'
    para-resources: '#0369A1'
    para-archive: '#6D28D9'
    confidence-low: '#BE123C'
typography:
  headline-xl: {fontFamily: Plus Jakarta Sans, fontSize: 36px, fontWeight: '700', lineHeight: 44px}
  headline-xl-mobile: {fontFamily: Plus Jakarta Sans, fontSize: 28px, fontWeight: '700', lineHeight: 36px}
  headline-lg: {fontFamily: Plus Jakarta Sans, fontSize: 28px, fontWeight: '600', lineHeight: 36px}
  headline-lg-mobile: {fontFamily: Plus Jakarta Sans, fontSize: 22px, fontWeight: '600', lineHeight: 30px}
  headline-md: {fontFamily: Plus Jakarta Sans, fontSize: 20px, fontWeight: '600', lineHeight: 28px}
  headline-sm: {fontFamily: Plus Jakarta Sans, fontSize: 16px, fontWeight: '600', lineHeight: 24px}
  body-lg: {fontFamily: Inter, fontSize: 16px, fontWeight: '400', lineHeight: 26px}
  body-md: {fontFamily: Inter, fontSize: 14px, fontWeight: '400', lineHeight: 22px}
  body-sm: {fontFamily: Inter, fontSize: 12px, fontWeight: '400', lineHeight: 18px}
  label-md: {fontFamily: Inter, fontSize: 13px, fontWeight: '500', lineHeight: 18px}
  label-sm: {fontFamily: Inter, fontSize: 11px, fontWeight: '600', lineHeight: 16px}
  telemetry-lg: {fontFamily: JetBrains Mono, fontSize: 18px, fontWeight: '600', lineHeight: 24px}
  telemetry-md: {fontFamily: JetBrains Mono, fontSize: 13px, fontWeight: '500', lineHeight: 18px}
  telemetry-sm: {fontFamily: JetBrains Mono, fontSize: 11px, fontWeight: '400', lineHeight: 14px}
rounded:
  sm: 0.25rem
  DEFAULT: 0.375rem
  lg: 0.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

# Atlas design system

Language: English only (code, UI copy, docs). The repo is reviewed by hackathon judges.

## Product context

Atlas is a personal email assistant. It organizes email into PARA (Projects,
Areas, Resources, Archive), answers questions with either PARA-aware or flat
retrieval, shows the evidence behind each answer, and reports what every AI
call cost. The dashboard exists to make the PARA-vs-flat difference visible
live, in front of a judge, within a minute.

The single job of the main screen: ask a question, pick a strategy, and see
the answer, its evidence, and its cost together.

## Brand and style

Corporate-modern rigor with technical minimalism: signal over noise.

- **Utilitarian balance**: clear structure, strict hierarchy, no ornament that carries no information.
- **Epistemic honesty**: confidence, latency, token use and provenance are first-class UI, not hidden in logs.
- **Calm velocity**: a subdued slate foundation; color is reserved for meaning.

## Colors

Dark mode is the default. Light mode is supported through the same semantic
tokens (see the front matter). Never hard-code hex values in components: use
tokens, so both appearances work. No in-app appearance switch; follow the system
setting (`prefers-color-scheme`).

### One color, one meaning

- **Indigo**: interaction only (focus ring, selected state, primary button, links).
- **PARA hues**: identify a PARA category and nothing else. Projects = amber, Areas = emerald, Resources = sky blue, Archive = violet.
- **Coral**: reserved for "low confidence" and errors. Never used decoratively.
- **Confidence is not a hue scale.** Green/amber are already taken by PARA. Confidence is shown as a 3-segment meter plus a text label (High / Moderate / Low) plus the exact percentage, in neutral `on-surface` tones. Only the Low state takes coral, plus a warning icon.

### Surfaces (dark / light)

| Layer | Dark | Light |
| --- | --- | --- |
| Canvas | `#090D16` | `#F8FAFC` |
| Base (cards, rails) | `#0F172A` | `#FFFFFF` |
| Raised (answer stage) | `#1E293B` | `#F1F5F9` |
| Overlay (modals) | `#334155` | `#E2E8F0` |

### Contrast rules (values below were computed, not estimated)

- Body text: at least 4.5:1. Graphical elements and control boundaries: at least 3:1.
- White text on `#6366F1` measures 4.47:1 and fails. Primary button fill is `#4F46E5` (white text 6.29:1). `#6366F1` is used for focus rings and indicators only (4.0:1 on `#0F172A`).
- Indigo text on dark uses `#818CF8` (5.98:1 on base).
- Dark PARA text on base: amber 8.31, emerald 7.04, sky 6.44, violet `#A78BFA` 6.56 (the original `#8B5CF6` was 4.22 and fails), coral `#FB7185` 6.63.
- Light PARA text on white: amber `#92400E` 7.09, emerald `#047857` 5.48, sky `#0369A1` 5.93, violet `#6D28D9` 7.10, coral `#BE123C` 6.29.
- Input and control borders must reach 3:1 (`border-strong`: 3.75:1 on dark base, 4.76:1 on white). The hairline `border` token is decorative only (card outlines), never the sole marker of an input.
- Chip and badge tints: at most 10% of the hue over the surface; text stays the full-strength hue.
- Never convey meaning by color alone: PARA chips carry the category name, confidence carries a label, status carries text.

## Typography

- **Plus Jakarta Sans**: headings, `-0.02em` letter spacing.
- **Inter**: body copy and interface text. Tabular figures (`tnum`) on for tables, metrics and aligned lists.
- **JetBrains Mono**: telemetry and provenance only (token counts, latencies, costs, model tags, PARA paths, scores).
- Minimum sizes: 11px for labels/telemetry, 14px for body. Text must reflow and remain usable at 200% browser zoom and larger system text.
- Prefer self-hosting the fonts (for example `@fontsource`) so the public demo never depends on a third-party CDN.

## Layout and responsive behavior

Desktop-first (live demo on a laptop or projector), degrading gracefully.

| Width | Layout |
| --- | --- |
| >= 1280px | Three columns. Left rail 280px (navigation + PARA tracker), center stage (flex, min 640px), right rail 320px (cost and telemetry). Outer margin 2rem, gutters 1.5rem. |
| 1024-1279px | Left rail collapses to an icon rail. Center stage takes the space. The right rail becomes a slide-over drawer, **and a one-line cost summary (total cost, cost per query, Nano/Ultra share) stays visible in the header** so the cost story is never hidden at laptop widths. |
| < 1024px | Single column. Bottom navigation bar (Ask, Projects, Cost). Ask box, strategy control and answer fill the first view. Outer margin 1rem, gutters 0.75rem. From 640px to 1023px the content is centered with a max width of 720px. No horizontal scrolling at any width. |

Primary controls sit within thumb reach on phones. Layouts survive large text sizes without truncating the answer or its provenance.

## Elevation and depth

Tonal layering plus 1px borders, not heavy shadows.

- **Layer 0**: canvas.
- **Layer 1**: base cards and rails, 1px border.
- **Layer 2**: the active answer card and expanded provenance, raised surface, `box-shadow: 0 4px 20px -2px rgba(0,0,0,0.25)`.
- **Layer 3**: modals and overlays; `backdrop-filter: blur(12px)` is allowed here only, never on content. Respect `prefers-reduced-transparency` by falling back to a solid overlay surface.

## Shapes

Soft corners: chips and badges 4px, controls 6px, cards and panels 8px, `full` only for status dots and circular icon toggles.

## Components

Every component lists the data it needs. If a field is not in the data contract below, the component does not show it.

### 1. Ask box

- Multiline, auto-growing textarea, placeholder "Ask something about your email...".
- Submit button labeled "Ask". Shortcut hint `Cmd/Ctrl + Enter` submits.
- Focus: border becomes indigo with a 2px ring.
- States: idle, loading (button becomes "Asking..." and is disabled, progress shown immediately), answered, error, empty.
- No model picker (the agent chooses the tier), no attachments.

### 2. Strategy control (Flat / PARA)

- Segmented control, two equal-width options, PARA selected by default.
- Selected state has a raised plate and a clear text label. A PARA-colored dot may accompany "PARA"; the label carries the meaning.
- The answer card always states which strategy produced it (for example "Answered with PARA"), so switching and re-asking makes the difference visible.
- Fully keyboard operable (arrow keys), announced as a radio group to screen readers.

### 3. Answer card

- Header: the question, and the confidence meter (label + percentage, coral with a warning icon when Low).
- "Web search used" tag whenever `used_web` is true. This is independent of the confidence value: it reflects what the agent did, not a threshold the UI guesses.
- Body: plain text at `body-md`. No markdown rendering, code blocks or inline citation markers unless the agent contract adds them.
- Low-confidence state: visibly different from a confident answer (coral meter, warning icon, short "I'm not sure" line), still readable without color.

### 4. Provenance list

- One collapsible card per source chunk, under the answer, collapsed by default, ordered by score.
- Collapsed row: PARA chip with the full path in mono (for example `projects/thesis`), date, score.
- Expanded: the snippet text in mono.
- Sources from the web are visually and textually separated from "From your email".

### 5. PARA chips and project tracker

- Chip: 6px dot + category name + path, in the PARA hue.
- Left-rail project item: name, status (`active` / `inactive`, always as text), email count, last activity date.
- The rail shows counts for all four PARA categories once the data exists (see the data contract).

### 6. Cost panel

- Glanceable first: total cost, cost per query, average latency, Nano vs Ultra share. Detail (tokens in/out per tier, per-call table) expands on demand.
- Numbers in `telemetry-lg` mono with small uppercase labels above.
- Model tags show the real tier names ("Nemotron Nano", "Nemotron Ultra"), not third-party model names.
- Values are session aggregates from the recorded calls, not a live stream.

### 7. Buttons and controls

- Primary: `primary` fill, `on-primary` text, weight 600, 6px radius.
- Secondary: transparent, `border-strong` outline. Ghost: text only.
- Minimum target 36px on desktop and 44px on touch. Visible keyboard focus on every interactive element.
- Labels say what happens ("Ask", "Retry"), never "Submit".

## Data contract (what the UI may show)

| Source | Fields |
| --- | --- |
| Answer (C3) | `text`, `confidence` (0-1), `provenance` (list of chunks), `used_web`, `tier_calls` |
| Chunk | `text`, `item_id`, `para_path`, `ts`, `score` |
| TierCall (C4) | `model`, `tokens_in`, `tokens_out`, `latency_ms`, `cost_usd` |
| Project (mock, future `/projects`) | `id`, `name`, `status`, `lastActivity`, `emailCount` |
| Cost aggregate (future `/cost`) | derived from TierCalls: per-tier cost and share, total, per query, average latency, tokens |

Confidence bands (High / Moderate / Low) are display groupings only. Their
cut-offs live in one constants file in `web/`, not in this document, because
the real abstain threshold is calibrated by the agent/eval side later.

## Out of scope until the data exists

Do not design or mock these; they have no backing data or belong to no owner yet:

- Sender and subject line on sources (not in `Chunk`; would require a contract change owned by other people).
- Inline citation chips `[1]`, highlighted matched spans, syntax-highlighted code.
- Model switcher, attachment clip, character counter.
- SLA health indicators, progress bars on projects.
- Real-time latency graph, financial run-rate, related-thread metadata.

## Interaction and accessibility

- Feedback lives in the interface: show progress immediately, keep the previous answer visible until the new one arrives, offer Retry on error. Errors say what failed and how to fix it.
- Screen readers: the answer region is a live region; every icon-only control has a text label.
- Motion is short and optional; honor `prefers-reduced-motion`.
- Empty states invite the next action ("Ask your first question" with two example questions).
