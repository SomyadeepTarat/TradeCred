#!/usr/bin/env bash
# Uses an administrator's already-configured peer CLI/MSP environment.
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
command -v peer >/dev/null || { echo "Fabric peer CLI is required." >&2; exit 1; }
: "${DRUNIX_CHANNEL:?Set the provisioned channel}"
: "${DRUNIX_CHAINCODE_NAME:=tradecred}"
: "${CORE_PEER_LOCALMSPID:?Select the approving administrator MSP}"
: "${CORE_PEER_MSPCONFIGPATH:?Select the administrator MSP directory}"
: "${CORE_PEER_ADDRESS:?Select the TLS peer endpoint}"
: "${CORE_PEER_TLS_ROOTCERT_FILE:?Select the peer TLS CA file}"
export CORE_PEER_TLS_ENABLED=true
phase="${1:?Use install, approve, check, commit or query}"
case "$phase" in
 install)
  : "${CHAINCODE_PACKAGE:?Set the packaged chaincode path}"
  exec peer lifecycle chaincode install "$CHAINCODE_PACKAGE"
  ;;
 query)
  exec peer lifecycle chaincode querycommitted --channelID "$DRUNIX_CHANNEL" --name "$DRUNIX_CHAINCODE_NAME"
  ;;
 approve|check|commit)
  : "${CHAINCODE_VERSION:?Set CHAINCODE_VERSION}"
  : "${CHAINCODE_SEQUENCE:?Set CHAINCODE_SEQUENCE}"
  : "${CHAINCODE_ENDORSEMENT_POLICY:?Set the reviewed consortium endorsement policy}"
  flags=(--channelID "$DRUNIX_CHANNEL" --name "$DRUNIX_CHAINCODE_NAME" --version "$CHAINCODE_VERSION"
   --sequence "$CHAINCODE_SEQUENCE" --signature-policy "$CHAINCODE_ENDORSEMENT_POLICY"
   --collections-config "$root/blockchain/chaincode/tradecred/collections_config.json")
  if [[ "$phase" == check ]]; then
   exec peer lifecycle chaincode checkcommitreadiness "${flags[@]}" --output json
  fi
  : "${ORDERER_ADDRESS:?Set ORDERER_ADDRESS}"
  : "${ORDERER_TLS_CA:?Set ORDERER_TLS_CA}"
  : "${ORDERER_TLS_HOSTNAME:?Set ORDERER_TLS_HOSTNAME}"
  flags+=(-o "$ORDERER_ADDRESS" --tls --cafile "$ORDERER_TLS_CA" --ordererTLSHostnameOverride "$ORDERER_TLS_HOSTNAME")
  if [[ "$phase" == approve ]]; then
   : "${CHAINCODE_PACKAGE_ID:?Set the installed package ID}"
   exec peer lifecycle chaincode approveformyorg "${flags[@]}" --package-id "$CHAINCODE_PACKAGE_ID"
  fi
  # Extra CLI args supply one --peerAddresses/--tlsRootCertFiles pair per required organization.
  shift
  test "$#" -gt 0 || { echo "Commit requires explicit endorsing peer addresses and TLS roots." >&2; exit 1; }
  exec peer lifecycle chaincode commit "${flags[@]}" "$@"
  ;;
 *) echo "Unknown lifecycle phase" >&2; exit 1 ;;
esac
