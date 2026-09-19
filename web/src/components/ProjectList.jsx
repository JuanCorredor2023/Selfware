export default function ProjectList({ projects }) {
  return (
    <section className="panel">
      <h2>Projects (PARA · mock data)</h2>
      <ul className="project-list">
        {projects.map((p) => (
          <li key={p.id} className={`project-item project-item--${p.status}`}>
            <div className="project-item__name">{p.name}</div>
            <div className="project-item__meta">
              <span className={`badge badge--${p.status}`}>{p.status}</span>
              <span>{p.emailCount} emails</span>
              <span>last activity: {p.lastActivity}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
