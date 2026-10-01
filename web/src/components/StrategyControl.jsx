// Segmented control for the retrieval strategy. Built on native radio inputs
// so arrow-key navigation and screen-reader semantics come for free.
const OPTIONS = [
  { value: "para", label: "PARA" },
  { value: "flat", label: "Flat" },
];

export default function StrategyControl({ value, onChange, disabled }) {
  return (
    <fieldset className="segmented" disabled={disabled}>
      <legend className="sr-only">Retrieval strategy</legend>
      {OPTIONS.map((o) => (
        <label key={o.value} className={`segmented__item${value === o.value ? " is-selected" : ""}`}>
          <input
            type="radio"
            name="strategy"
            value={o.value}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
          />
          <span>{o.label}</span>
        </label>
      ))}
    </fieldset>
  );
}
