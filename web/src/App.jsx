import "./App.css";
import ProjectList from "./ProjectList";
import AskBox from "./AskBox";
import { mockProjects } from "./mockProjects";

function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>Selfware</h1>
        <p>Dashboard — Persona 4 (producto y observabilidad)</p>
      </header>
      <main className="app__main">
        <ProjectList projects={mockProjects} />
        <AskBox />
      </main>
    </div>
  );
}

export default App;
