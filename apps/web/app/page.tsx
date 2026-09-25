export default function Home() {
  return (
    <main>
      <header>
        <span className="brand">TradeCred</span>
        <span className="badge">Milestone 0 · Bootstrap</span>
      </header>
      <section aria-labelledby="title">
        <p className="eyebrow">FOR MSME TRADE FINANCE</p>
        <h1 id="title">Receivable trust infrastructure</h1>
        <p className="intro">
          A shared foundation for verified receivables, institutional financing,
          and authenticated settlement records.
        </p>
        <div className="panel">
          <h2>Development foundation</h2>
          <p>
            The Next.js frontend, FastAPI service, and PostgreSQL configuration
            are in place. Authentication and receivable workflows arrive in
            later milestones.
          </p>
          <p className="notice">
            Prototype only. No live ledger or payment connection.
          </p>
        </div>
      </section>
      <footer>
        Drunix is the target ledger platform. TradeCred does not move foreign
        currency, issue e-BRC certificates, or establish legal ownership through
        token state.
      </footer>
    </main>
  );
}
