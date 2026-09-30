import { formatDate, formatInt } from "../lib/format";
import { PARA_LABEL } from "../lib/para";

// Left rail: the four PARA categories with their items. When the rail is
// collapsed to an icon rail (laptop widths), only the dot and count remain.
export default function ParaTracker({ tree }) {
  return (
    <nav className="tracker" aria-label="PARA tracker">
      <h2 className="section-title tracker__title">PARA</h2>
      {tree.map((cat) => {
        const emails = cat.items.reduce((sum, i) => sum + i.email_count, 0);
        return (
          <section key={cat.key} className={`tracker__cat para-${cat.key}`} title={`${PARA_LABEL[cat.key]}: ${emails} emails`}>
            <h3 className="tracker__cat-head">
              <span className="tracker__dot" aria-hidden="true" />
              <span className="tracker__cat-name">{PARA_LABEL[cat.key]}</span>
              <span className="tracker__cat-count mono">{formatInt(emails)}<span className="sr-only"> emails</span></span>
            </h3>
            <ul className="tracker__items">
              {cat.items.map((item) => (
                <li key={item.id} className="tracker__item">
                  <span className="tracker__item-name">{item.name}</span>
                  <span className="tracker__item-meta">
                    {item.status && <span className={`status status--${item.status}`}>{item.status}</span>}
                    <span className="mono">{item.email_count} emails</span>
                    <span>{formatDate(item.last_activity)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </nav>
  );
}
