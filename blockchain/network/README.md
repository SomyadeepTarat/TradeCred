# Drunix gateway — Milestone 8

The API supports an explicit choice: `LEDGER_BACKEND=mock` uses MockLedgerClient;
`LEDGER_BACKEND=drunix` uses the Go bridge and official Hyperledger Fabric Gateway SDK.
No Drunix network or credentials are bundled. This connector assumes a Fabric Gateway
compatible network; actual Drunix compatibility and deployment remain unverified.
Missing configuration, connection failures and unknown commit outcomes never select mock.

## Provisioning and deployment

1. Obtain a provisioned channel, TLS-enabled Gateway peers, orderer, network-compatible
   `peer` CLI and organization identities from your network administrator. Follow the
   [chaincode identity and collection profile](../chaincode/tradecred/README.md).
   Certificate `tradecred.org` / `tradecred.role` attributes and the settlement service
   attribute must match that profile. Enrollment, channel creation and consortium policy
   approval are external prerequisites, not simulated by these scripts.
2. Package with `CHAINCODE_LABEL=tradecred_0.8.0 make drunix-package`. This vendors Go
   dependencies, creates `data/drunix/tradecred_0.8.0.tar.gz` and prints its package ID.
   Use a new label for each package. Install the package on each required peer:
   `bash blockchain/network/scripts/lifecycle.sh install`.
3. Set the administrator's `CORE_PEER_LOCALMSPID`, `CORE_PEER_MSPCONFIGPATH`,
   `CORE_PEER_ADDRESS`, `CORE_PEER_TLS_ROOTCERT_FILE`, `DRUNIX_CHANNEL`,
   `DRUNIX_CHAINCODE_NAME`, `CHAINCODE_PACKAGE`, `CHAINCODE_PACKAGE_ID`,
   `CHAINCODE_VERSION`, `CHAINCODE_SEQUENCE`, and reviewed
   `CHAINCODE_ENDORSEMENT_POLICY`. For ordering also set `ORDERER_ADDRESS`,
   `ORDERER_TLS_CA`, `ORDERER_TLS_HOSTNAME`. Run `lifecycle.sh approve` for each org,
   then `lifecycle.sh check`. Commit with `lifecycle.sh commit` followed by explicit
   `--peerAddresses HOST:PORT --tlsRootCertFiles PATH` pairs for required organizations.
   `lifecycle.sh query` reads the committed definition. All phases propagate CLI failures.
   Review collection policies against the actual network before approval. Endorsement
   policies must permit the explicitly selected endorsers described below.
4. Copy `config/gateway.example.json` to `data/drunix/config/gateway.json`. Replace every
   `.example.invalid` endpoint and the network ID. Place enrollment certificates, private
   keys and TLS roots beneath `data/drunix/identities` at the paths in the configuration.
   These ignored directories mount read-only. Files must be readable by container UID
   10001; restrict access to that service account. Do not commit credentials.
5. Generate a random bearer token of at least 32 characters and set
   `DRUNIX_GATEWAY_TOKEN` in the private root `.env`. Set `DRUNIX_NETWORK_ID` to the
   exact JSON network ID, `DRUNIX_CHANNEL`, `DRUNIX_CHAINCODE_NAME=tradecred`, and
   `LEDGER_BACKEND=drunix`. For host API execution use
   `DRUNIX_GATEWAY_URL=http://127.0.0.1:8080`; Compose uses
   `DRUNIX_DOCKER_GATEWAY_URL=http://drunix-gateway:8080`.
6. Run `docker compose --profile drunix build drunix-gateway`, then
   `make drunix-preflight`. Preflight only parses configuration and credential files;
   success does **not** verify connectivity, certificate authorization or a transaction.
   Run `docker compose --profile drunix up --build --wait`, then `make seed` if needed.
   For a host API, run `make migrate` before `make api`.
7. Verify a fresh invoice through admin verification, exporter registration/opening,
   competing offers, acceptance, mock disbursement and signed settlement. Inspect real
   peer history and VALID transaction IDs. Test duplicate rejection, wrong identities,
   private collection isolation, peer outage and lost responses on the provisioned network.
   These live checks have not been performed in this repository's local verification.

The bridge binds to localhost by default, or the private Compose network. Bearer HTTP is
only allowed for the local connection; use a TLS reverse proxy for remote deployment and
`DRUNIX_GATEWAY_CA_PATH` for a private proxy CA. Never expose the internal bridge publicly:
its bearer token grants use of mapped organization signing identities. Peer TLS always
verifies a configured root and hostname. Peer TLS client-certificate authentication is not
currently configured; networks requiring mutual TLS need that addition before deployment.

## Commit, privacy and recovery semantics

[Fabric Gateway SubmitWithContext](https://pkg.go.dev/github.com/hyperledger/fabric-gateway/pkg/client)
waits for a valid commit. The bridge returns `committed: true` only after that call succeeds.
It accepts allowlisted methods and exact network/channel/chaincode binding, and sanitizes
errors rather than exposing proposals or private key paths. Gateway SDK v1.11.0 is pinned.

Mutation requests call the chaincode `Execute` wrapper. A deterministic operation ID,
request/transient hash, actor org/role and sanitized receipt are committed atomically with
the state change. Matching retries return the original transaction; changed requests fail.
API private invoice salts, acceptance timestamps and payment salts are durably journaled
in PostgreSQL before submission, independently of the local projection transaction. A
retry can reconcile a lost response or failed local commit only when the exact operation's
receipt matches current ledger state. It never infers success from a changed status alone.
Keep `ledger_artifacts` in protected backups alongside application data: it contains
private commercial inputs and is necessary for safe retries. There is no automatic repair
worker; repeat the same action after restoring availability. Do not prune pending artifacts.

Invoice, agreement and payment inputs travel in transient data, not public arguments.
Verification selects the admin's endorser, registration the exporter, and lock the exporter
and winning financier. Other actions select the actor's organization. The API therefore
supplies the saved invoice commitment when another authorized organization needs to verify
it. The application and bridge are trusted custodians of these private inputs. Certificate
MSP/attributes, chaincode ownership rules and PDC policy remain independent enforcement.

Existing assets are bound to their backend and network. For explicit fallback set
`LEDGER_BACKEND=mock` and restart the API, using fresh invoices or a separate database.
This does not migrate Drunix assets or manufacture mock confirmations for them.
Payment disbursement remains a labeled sandbox simulation in both ledger modes.
Signed settlement retains replay and five-minute timestamp checks. If recovery takes
longer, the bank must re-sign the same event terms with a fresh timestamp; a consumed
event remains rejected. `--replay` alone retains the original timestamp.

## Local validation

`make test-gateway`, `make test-chaincode`, `make test-integration`, `make lint`,
`make build-gateway` and `make test-e2e` exercise SDK boundaries, chaincode logic,
PostgreSQL projections/recovery, and the existing mock browser workflow. HTTP transport
and SDK invokers are test doubles only. Their success is not evidence of live Drunix
endorsement, private-data dissemination, ordering or commit behavior.
