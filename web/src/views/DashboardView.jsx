import ProjectList from "../components/ProjectList";
import AskBox from "../components/AskBox";
import { mockProjects } from "../mocks/projects";

// The only view today. If a second one shows up later (e.g. a dedicated
// eval-report page), it lives next to this one in views/, and App.jsx
// picks between them.
export default function DashboardView() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>Selfware</h1>
        <p>Dashboard — Product &amp; Observability (Person 4)</p>
      </header>
      <main className="app__main">
        <ProjectList projects={mockProjects} />
        <AskBox />
      </main>
    </div>
  );
}
