export default function Home() {
  return (
    <main>
      <header>
        <span className="brand">TradeCred</span>
        <span className="badge">Milestone 2 · Documents</span>
      </header>
      <section aria-labelledby="title">
        <p className="eyebrow">FOR MSME TRADE FINANCE</p>
        <h1 id="title">Receivable trust infrastructure</h1>
        <p className="intro">
          A shared foundation for verified receivables, institutional financing,
          and authenticated settlement records.
        </p>
        <div className="panel">
          <h2>Invoice integrity</h2>
          <p>
            Exporters can upload invoice PDFs through the API, create draft
            receivables, and verify document integrity. Business fingerprints
            are independent of file hashes. Ledger registration arrives in the
            next milestone.
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
