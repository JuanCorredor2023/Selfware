export default function ProjectList({ projects }) {
  return (
    <section className="panel">
      <h2>Proyectos (PARA · datos falsos)</h2>
      <ul className="project-list">
        {projects.map((p) => (
          <li key={p.id} className={`project-item project-item--${p.status}`}>
            <div className="project-item__name">{p.name}</div>
            <div className="project-item__meta">
              <span className={`badge badge--${p.status}`}>{p.status}</span>
              <span>{p.emailCount} correos</span>
              <span>última actividad: {p.lastActivity}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
