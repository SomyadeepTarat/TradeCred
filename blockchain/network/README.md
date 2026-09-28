# Drunix network

Network provisioning and the application gateway remain Milestone 8. No Drunix network
is started by the Compose stack. Milestone 7 supplies the [Go contract](../chaincode/tradecred/README.md),
its tested lifecycle, explicit demo MSP/attribute profile and private collection definitions.
Actual Drunix API/runtime compatibility and endorsement/private-data behavior remain unverified.

The application continues to use MockLedgerClient explicitly. Drunix selection returns 503
without fallback until a real gateway is implemented. Never treat contract unit tests or
successful proposal endorsement as a confirmed Drunix ledger transaction.
