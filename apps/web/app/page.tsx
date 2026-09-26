export default function Home() {
  return (
    <main>
      <header>
        <span className="brand">TradeCred</span>
        <span className="badge">Milestone 3 · Mock ledger</span>
      </header>
      <section aria-labelledby="title">
        <p className="eyebrow">FOR MSME TRADE FINANCE</p>
        <h1 id="title">Receivable trust infrastructure</h1>
        <p className="intro">
          A shared foundation for verified receivables, institutional financing,
          and authenticated settlement records.
        </p>
        <div className="panel">
          <h2>Mock registry and audit history</h2>
          <p>
            The API supports invoice submission, administrator verification,
            registration in the mock ledger, duplicate checks, and audit
            history. Mock transactions are explicitly identified. The
            receivables interface arrives in the next milestone.
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
