#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
command -v peer >/dev/null || { echo "Install the network-compatible Fabric peer CLI first." >&2; exit 1; }
: "${CHAINCODE_LABEL:?Set CHAINCODE_LABEL to a versioned label, for example tradecred_0.8.0}"
mkdir -p "$root/data/drunix"
package="$root/data/drunix/$CHAINCODE_LABEL.tar.gz"
test ! -e "$package" || { echo "Package exists; use a new label." >&2; exit 1; }
bash "$root/scripts/chaincode.sh" go mod vendor
peer lifecycle chaincode package "$package" --path "$root/blockchain/chaincode/tradecred" --lang golang --label "$CHAINCODE_LABEL"
peer lifecycle chaincode calculatepackageid "$package"
