import { categoryOf } from "../lib/para";
import Icon from "./Icon";

// A PARA path shown as a chip: colored dot + the full path in mono.
// The path text is the meaning; the color is only a reinforcement.
export default function ParaChip({ path, label }) {
  const category = categoryOf(path);
  return (
    <span className={`para-chip para-chip--${category}`}>
      {category === "web" ? <Icon name="globe" size={12} /> : <span className="para-chip__dot" aria-hidden="true" />}
      <span className="para-chip__text">{label ?? path}</span>
    </span>
  );
}
