package main

import (
	"bytes"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"slices"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

//go:embed currency_exponents.json
var currencyJSON []byte
var currencyExponents = func() map[string]int {
	result := map[string]int{}
	if err := json.Unmarshal(currencyJSON, &result); err != nil {
		panic(err)
	}
	return result
}()

var identifier = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)
var digestPattern = regexp.MustCompile(`^[a-f0-9]{64}$`)
var eventPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,160}$`)
var referencePattern = regexp.MustCompile(`^[A-Za-z0-9_./-]{1,160}$`)

func failure(code string) error { return fmt.Errorf("%s", code) }
func digest(raw []byte) string {
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// Strict decoding rejects unknown fields, duplicate keys, oversized objects and trailing JSON.
func decode(raw []byte, target any) error {
	if len(raw) == 0 || len(raw) > 8192 {
		return failure("INVALID_INPUT")
	}
	fields := json.NewDecoder(bytes.NewReader(raw))
	token, err := fields.Token()
	if err != nil || token != json.Delim('{') {
		return failure("INVALID_INPUT")
	}
	seen := map[string]bool{}
	for fields.More() {
		token, err := fields.Token()
		if err != nil {
			return failure("INVALID_INPUT")
		}
		key, ok := token.(string)
		if !ok || seen[key] {
			return failure("INVALID_INPUT")
		}
		seen[key] = true
		var value json.RawMessage
		if err := fields.Decode(&value); err != nil {
			return failure("INVALID_INPUT")
		}
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return failure("INVALID_INPUT")
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return failure("INVALID_INPUT")
	}
	return nil
}

func identity(ctx contractapi.TransactionContextInterface) (string, string, error) {
	ci := ctx.GetClientIdentity()
	org, found, err := ci.GetAttributeValue("tradecred.org")
	if err != nil || !found {
		return "", "", failure("UNAUTHORIZED_ROLE")
	}
	role, found, err := ci.GetAttributeValue("tradecred.role")
	if err != nil || !found {
		return "", "", failure("UNAUTHORIZED_ROLE")
	}
	msp, err := ci.GetMSPID()
	expected, ok := participants[org]
	if err != nil || !ok || expected.MSP != msp || expected.Role != role {
		return "", "", failure("UNAUTHORIZED_ROLE")
	}
	return org, role, nil
}

func settlementIdentity(ctx contractapi.TransactionContextInterface) error {
	_, role, err := identity(ctx)
	if err != nil || role != "SETTLEMENT_OPERATOR" {
		return failure("UNAUTHORIZED_ROLE")
	}
	// Only a backend service certificate may confirm events already verified by the API.
	value, found, err := ctx.GetClientIdentity().GetAttributeValue("tradecred.settlement")
	if err != nil || !found || value != "true" {
		return failure("UNAUTHORIZED_ROLE")
	}
	return nil
}

func transactionTime(ctx contractapi.TransactionContextInterface) (time.Time, error) {
	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return time.Time{}, err
	}
	if ts == nil || ts.CheckValid() != nil {
		return time.Time{}, failure("INVALID_TIMESTAMP")
	}
	return ts.AsTime().UTC(), nil
}

func requireTransition(current, target string) error {
	if !slices.Contains(transitions[current], target) {
		return failure("INVALID_STATE_TRANSITION")
	}
	return nil
}

func transient(ctx contractapi.TransactionContextInterface, key string, target any) ([]byte, error) {
	values, err := ctx.GetStub().GetTransient()
	if err != nil {
		return nil, err
	}
	raw := values[key]
	if err := decode(raw, target); err != nil {
		return nil, err
	}
	return raw, nil
}

func privateInvoice(ctx contractapi.TransactionContextInterface, assetID, currency string) ([]byte, *PrivateInvoice, error) {
	var details PrivateInvoice
	raw, err := transient(ctx, "invoice", &details)
	if err != nil {
		return nil, nil, err
	}
	if details.AssetID != assetID || details.Currency != currency || details.AmountMinor <= 0 || !digestPattern.MatchString(details.Salt) {
		return nil, nil, failure("INVALID_PRIVATE_DETAILS")
	}
	return raw, &details, nil
}

func registration(raw string) (*Registration, error) {
	var r Registration
	if err := decode([]byte(raw), &r); err != nil {
		return nil, err
	}
	exporter, exists := participants[r.ExporterOrgID]
	if !identifier.MatchString(r.AssetID) || !digestPattern.MatchString(r.InvoiceFingerprint) ||
		!digestPattern.MatchString(r.DocumentHash) || !exists || exporter.Role != "EXPORTER" {
		return nil, failure("INVALID_REGISTRATION")
	}
	if _, exists := currencyExponents[r.Currency]; !exists {
		return nil, failure("INVALID_CURRENCY")
	}
	if _, err := time.Parse("2006-01-02", r.DueDate); err != nil {
		return nil, failure("INVALID_DUE_DATE")
	}
	return &r, nil
}

func bucket(amount int64, currency string) string {
	scale := int64(1)
	for range currencyExponents[currency] {
		scale *= 10
	}
	major := amount / scale
	for _, pair := range [][2]int64{{0, 10000}, {10000, 25000}, {25000, 100000}, {100000, 1000000}} {
		if major >= pair[0] && major < pair[1] {
			return fmt.Sprintf("%d-%d", pair[0], pair[1])
		}
	}
	return "1000000+"
}
