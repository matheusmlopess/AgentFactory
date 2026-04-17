import { featureCards, lifecycleSteps } from "./data/harness";
import { HarnessExplorer } from "./components/HarnessExplorer";
import { CompletenessViewer } from "./components/CompletenessViewer";
import { RegistryBrowser } from "./components/RegistryBrowser";

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

      <section className="split">
        <article className="surface">
          <p className="section-label">Phase 1 foundation</p>
          <h2>What this scaffold already provides</h2>
          <ul className="checklist">
            <li>React 19 + TypeScript strict-mode baseline</li>
            <li>CSS variable design tokens for light and dark themes</li>
            <li>Static data module for issue-driven UI work</li>
            <li>GitHub Pages deployment workflow on release tags</li>
          </ul>
        </article>

        <article className="surface">
          <p className="section-label">Lifecycle snapshot</p>
          <h2>Core CLI flow</h2>
          <ol className="steps">
            {lifecycleSteps.map((step) => (
              <li key={step.command}>
                <code>{step.command}</code>
                <strong>{step.title}</strong>
                <span>{step.detail}</span>
              </li>
            ))}
          </ol>
        </article>
      </section>
    </main>
  );
}

export default App;
