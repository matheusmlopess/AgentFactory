import { featureCards } from "./data/harness";
import { HarnessExplorer } from "./components/HarnessExplorer";
import { CompletenessViewer } from "./components/CompletenessViewer";
import { RegistryBrowser } from "./components/RegistryBrowser";
import { LifecycleStepper } from "./components/LifecycleStepper";
import { ManifestInspector } from "./components/ManifestInspector";

function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">AgentFactory Platform</p>
        <h1>Production-ready scaffold for the AgentFactory web experience.</h1>
        <p className="lede">
          This initial webapp establishes the Vite, React 19, and TypeScript
          baseline for the harness explorer, manifest inspector, and registry
          platform tracked under epic #77.
        </p>
        <div className="hero-actions">
          <a className="button primary" href="#roadmap">
            Explore roadmap
          </a>
          <a className="button secondary" href="https://github.com/matheusmlopess/AgentFactory">
            View repository
          </a>
        </div>
      </section>

      <section className="panel-grid" id="roadmap">
        {featureCards.map((card) => (
          <article className="panel-card" key={card.title}>
            <span className={`badge badge-${card.status}`}>{card.status}</span>
            <h2>{card.title}</h2>
            <p>{card.detail}</p>
          </article>
        ))}
      </section>

      <HarnessExplorer />

      <CompletenessViewer />

      <RegistryBrowser />

      <LifecycleStepper />

      <ManifestInspector />
    </main>
  );
}

export default App;
