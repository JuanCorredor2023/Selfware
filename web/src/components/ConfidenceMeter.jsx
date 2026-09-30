import { BAND_LABEL, BAND_SEGMENTS, bandFor } from "../lib/confidence";
import { formatPercent } from "../lib/format";
import Icon from "./Icon";

// 3-segment meter + text label + exact percentage. Color is used only for the
// Low band; the label and the number carry the meaning for everyone else.
export default function ConfidenceMeter({ confidence }) {
  const band = bandFor(confidence);
  const filled = BAND_SEGMENTS[band];
  const percent = formatPercent(confidence);
  return (
    <div className={`confidence confidence--${band}`} role="img" aria-label={`${BAND_LABEL[band]}, ${percent}`}>
      <span className="confidence__segments" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={`confidence__seg${n <= filled ? " is-on" : ""}`} />
        ))}
      </span>
      {band === "low" && <Icon name="warning" size={14} />}
      <span className="confidence__label" aria-hidden="true">{BAND_LABEL[band]}</span>
      <span className="confidence__value" aria-hidden="true">{percent}</span>
    </div>
  );
}
