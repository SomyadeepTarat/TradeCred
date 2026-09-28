# Regulatory boundaries

1. TradeCred is a prototype, not a production-ready or regulator-approved service.
2. Foreign exchange movement is performed outside TradeCred.
3. Actual remittance is assumed to occur through regulated banking channels.
4. The settlement flow consumes authenticated payment confirmation only.
5. TradeCred does not issue legal e-BRC certificates.
6. TradeCred exposes eligibility/status for downstream exporter workflows, with self-certification pending.
7. Token state is not itself a legal assignment of a receivable.
8. Financing agreements remain conventional legal instruments. The ledger
   records the consortium-recognized financing and assignment state, with a cryptographic
   hash of the underlying financing agreement.
9. Integration with banks, TReDS, DGFT, RBI, and NPCI production infrastructure is future work.

TradeCred does not replace TReDS or guarantee prevention of off-network fraud. AD banks
and remittance providers remain regulated intermediaries. Actual DGFT and RBI workflows
are outside the prototype scope. No live payment connection exists. The Drunix gateway is implemented but live deployment remains unverified.
