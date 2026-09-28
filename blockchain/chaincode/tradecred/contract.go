package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

func assetKey(id string) string       { return "asset:" + id }
func fingerprintKey(fp string) string { return "fingerprint:" + fp }

func readAsset(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	if !identifier.MatchString(id) {
		return nil, failure("INVALID_ASSET_ID")
	}
	raw, err := ctx.GetStub().GetState(assetKey(id))
	if err != nil {
		return nil, err
	}
	if raw == nil {
		return nil, failure("ASSET_NOT_FOUND")
	}
	var asset Asset
	if err := json.Unmarshal(raw, &asset); err != nil {
		return nil, failure("CORRUPT_LEDGER_STATE")
	}
	if asset.AssetID != id {
		return nil, failure("CORRUPT_LEDGER_STATE")
	}
	return &asset, nil
}

func writeAsset(ctx contractapi.TransactionContextInterface, asset *Asset) (*Asset, error) {
	now, err := transactionTime(ctx)
	if err != nil {
		return nil, err
	}
	asset.Revision++
	asset.UpdatedAt = now.Format(time.RFC3339Nano)
	asset.TransactionID = ctx.GetStub().GetTxID()
	raw, err := json.Marshal(asset)
	if err != nil {
		return nil, err
	}
	if err := ctx.GetStub().PutState(assetKey(asset.AssetID), raw); err != nil {
		return nil, err
	}
	if err := ctx.GetStub().SetEvent("ReceivableStateChanged", raw); err != nil {
		return nil, err
	}
	return asset, nil
}

func registrationMatches(a *Asset, r *Registration, privateHash string) bool {
	return a.AssetID == r.AssetID && a.InvoiceFingerprint == r.InvoiceFingerprint &&
		a.DocumentHash == r.DocumentHash && a.ExporterOrgID == r.ExporterOrgID &&
		a.Currency == r.Currency && a.DueDate == r.DueDate && a.PrivateDetailsHash == privateHash
}

// VerifyReceivable is the verifier's attestation, not automatic commercial verification.
// Reserves the fingerprint and creates VERIFIED; registration is a separate exporter action.
func (c *TradeCredContract) VerifyReceivable(ctx contractapi.TransactionContextInterface, input string) (*Asset, error) {
	_, role, err := identity(ctx)
	if err != nil || role != "ADMIN" {
		return nil, failure("UNAUTHORIZED_ROLE")
	}
	r, err := registration(input)
	if err != nil {
		return nil, err
	}
	raw, invoice, err := privateInvoice(ctx, r.AssetID, r.Currency)
	if err != nil {
		return nil, err
	}
	existingID, err := ctx.GetStub().GetState(fingerprintKey(r.InvoiceFingerprint))
	if err != nil {
		return nil, err
	}
	if existingID != nil && string(existingID) != r.AssetID {
		existing, err := readAsset(ctx, string(existingID))
		if err != nil {
			return nil, err
		}
		return nil, fmt.Errorf("DUPLICATE_RECEIVABLE: assetId=%s status=%s", existing.AssetID, existing.Status)
	}
	existing, err := ctx.GetStub().GetState(assetKey(r.AssetID))
	if err != nil {
		return nil, err
	}
	if existing != nil {
		a, err := readAsset(ctx, r.AssetID)
		if err != nil {
			return nil, err
		}
		if !registrationMatches(a, r, digest(raw)) {
			return nil, failure("REGISTRATION_CONFLICT")
		}
		return a, nil
	}
	asset := &Asset{AssetID: r.AssetID, InvoiceFingerprint: r.InvoiceFingerprint,
		DocumentHash: r.DocumentHash, ExporterOrgID: r.ExporterOrgID, Currency: r.Currency,
		DueDate: r.DueDate, FaceValueBucket: bucket(invoice.AmountMinor, r.Currency), Status: "VERIFIED",
		PrivateDetailsHash: digest(raw),
		PrivateCollection:  "_implicit_org_" + participants[r.ExporterOrgID].MSP}
	if err := ctx.GetStub().PutState(fingerprintKey(r.InvoiceFingerprint), []byte(r.AssetID)); err != nil {
		return nil, err
	}
	return writeAsset(ctx, asset)
}

func (c *TradeCredContract) RegisterReceivable(ctx contractapi.TransactionContextInterface, input string) (*Asset, error) {
	org, role, err := identity(ctx)
	if err != nil || role != "EXPORTER" {
		return nil, failure("UNAUTHORIZED_ROLE")
	}
	r, err := registration(input)
	if err != nil {
		return nil, err
	}
	if org != r.ExporterOrgID {
		return nil, failure("UNAUTHORIZED_ROLE")
	}
	index, err := ctx.GetStub().GetState(fingerprintKey(r.InvoiceFingerprint))
	if err != nil {
		return nil, err
	}
	if index != nil && string(index) != r.AssetID {
		existing, err := readAsset(ctx, string(index))
		if err != nil {
			return nil, err
		}
		return nil, fmt.Errorf("DUPLICATE_RECEIVABLE: assetId=%s status=%s", existing.AssetID, existing.Status)
	}
	asset, err := readAsset(ctx, r.AssetID)
	if err != nil {
		return nil, err
	}
	raw, _, err := privateInvoice(ctx, r.AssetID, r.Currency)
	if err != nil {
		return nil, err
	}
	if !registrationMatches(asset, r, digest(raw)) {
		return nil, failure("REGISTRATION_CONFLICT")
	}
	if asset.RegistrationTransactionID != "" {
		return asset, nil
	}
	if err := requireTransition(asset.Status, "REGISTERED"); err != nil {
		return nil, err
	}
	if !bytes.Equal(index, []byte(r.AssetID)) {
		return nil, failure("CORRUPT_LEDGER_STATE")
	}
	if err := ctx.GetStub().PutPrivateData(asset.PrivateCollection, assetKey(asset.AssetID), raw); err != nil {
		return nil, err
	}
	asset.Status = "REGISTERED"
	asset.RegistrationTransactionID = ctx.GetStub().GetTxID()
	return writeAsset(ctx, asset)
}

func (c *TradeCredContract) GetReceivable(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	if _, _, err := identity(ctx); err != nil {
		return nil, err
	}
	return readAsset(ctx, id)
}

func (c *TradeCredContract) GetReceivableByFingerprint(ctx contractapi.TransactionContextInterface, fp string) (*Asset, error) {
	if _, _, err := identity(ctx); err != nil {
		return nil, err
	}
	if !digestPattern.MatchString(fp) {
		return nil, failure("INVALID_FINGERPRINT")
	}
	id, err := ctx.GetStub().GetState(fingerprintKey(fp))
	if err != nil {
		return nil, err
	}
	if id == nil {
		return nil, failure("ASSET_NOT_FOUND")
	}
	return readAsset(ctx, string(id))
}

// Verify transient invoice against both verifier commitment and committed private data hash.
// Non-member settlement peers need no plaintext private database access.
func invoiceProof(ctx contractapi.TransactionContextInterface, asset *Asset) ([]byte, *PrivateInvoice, error) {
	raw, invoice, err := privateInvoice(ctx, asset.AssetID, asset.Currency)
	if err != nil {
		return nil, nil, err
	}
	hash, err := ctx.GetStub().GetPrivateDataHash("_implicit_org_"+participants[asset.ExporterOrgID].MSP, assetKey(asset.AssetID))
	if err != nil {
		return nil, nil, err
	}
	if digest(raw) != asset.PrivateDetailsHash || fmt.Sprintf("%x", hash) != asset.PrivateDetailsHash {
		return nil, nil, failure("PRIVATE_DETAILS_MISMATCH")
	}
	return raw, invoice, nil
}

func (c *TradeCredContract) LockReceivable(ctx contractapi.TransactionContextInterface, id, financierOrg, agreementHash string) (*Asset, error) {
	org, role, err := identity(ctx)
	if err != nil || role != "EXPORTER" {
		return nil, failure("UNAUTHORIZED_ROLE")
	}
	asset, err := readAsset(ctx, id)
	if err != nil {
		return nil, err
	}
	if asset.ExporterOrgID != org {
		return nil, failure("UNAUTHORIZED_ROLE")
	}
	collection := pairCollections[org][financierOrg]
	if collection == "" || !digestPattern.MatchString(agreementHash) {
		return nil, failure("INVALID_FINANCING_TERMS")
	}
	if asset.OwnerOrgID == financierOrg && asset.AgreementHash == agreementHash && asset.LockTransactionID != "" {
		return asset, nil
	}
	if err := requireTransition(asset.Status, "LOCKED"); err != nil {
		return nil, err
	}
	if asset.OwnerOrgID != "" {
		return nil, failure("RECEIVABLE_ALREADY_LOCKED")
	}
	rawInvoice, invoice, err := invoiceProof(ctx, asset)
	if err != nil {
		return nil, err
	}
	var agreement Agreement
	rawAgreement, err := transient(ctx, "agreement", &agreement)
	if err != nil {
		return nil, err
	}
	var offer Offer
	if _, err := transient(ctx, "offer", &offer); err != nil {
		return nil, err
	}
	now, err := transactionTime(ctx)
	if err != nil {
		return nil, err
	}
	expires, err := time.Parse(time.RFC3339Nano, offer.ExpiresAt)
	if err != nil || !expires.After(now) || !eventPattern.MatchString(offer.OfferID) {
		return nil, failure("OFFER_EXPIRED_OR_INVALID")
	}
	accepted, err := time.Parse(time.RFC3339Nano, agreement.AcceptedAt)
	if err != nil || accepted.Before(now.Add(-5*time.Minute)) || accepted.After(now.Add(5*time.Minute)) {
		return nil, failure("INVALID_AGREEMENT_TIME")
	}
	if digest(rawAgreement) != agreementHash || agreement.AgreementVersion != "TC-AGR-1" ||
		agreement.AssetID != id || agreement.ExporterOrgID != org || agreement.FinancierOrgID != financierOrg ||
		agreement.Currency != asset.Currency || agreement.AdvanceAmountMinor <= 0 || agreement.AdvanceAmountMinor > invoice.AmountMinor ||
		agreement.DiscountRateBps < 0 || agreement.DiscountRateBps > 10000 || agreement.TenorDays < 1 || agreement.TenorDays > 3650 ||
		agreement.TermsVersion != "demo-v1" || agreement.AssignmentStatus != "CONSORTIUM_FINANCING_LOCK" {
		return nil, failure("INVALID_FINANCING_TERMS")
	}
	if err := ctx.GetStub().PutPrivateData(collection, assetKey(id), rawInvoice); err != nil {
		return nil, err
	}
	if err := ctx.GetStub().PutPrivateData(collection, "agreement:"+id, rawAgreement); err != nil {
		return nil, err
	}
	asset.Status = "LOCKED"
	asset.OwnerOrgID = financierOrg
	asset.AgreementHash = agreementHash
	asset.PrivateCollection = collection
	asset.LockTransactionID = ctx.GetStub().GetTxID()
	return writeAsset(ctx, asset)
}

func (c *TradeCredContract) transition(ctx contractapi.TransactionContextInterface, id, target string) (*Asset, error) {
	org, role, err := identity(ctx)
	if err != nil {
		return nil, err
	}
	asset, err := readAsset(ctx, id)
	if err != nil {
		return nil, err
	}
	switch target {
	case "FINANCE_AVAILABLE":
		if role != "EXPORTER" || org != asset.ExporterOrgID {
			return nil, failure("UNAUTHORIZED_ROLE")
		}
	case "FINANCED", "RELEASED":
		if role != "FINANCIER" || org != asset.OwnerOrgID {
			return nil, failure("UNAUTHORIZED_ROLE")
		}
		if !digestPattern.MatchString(asset.AgreementHash) {
			return nil, failure("AGREEMENT_REQUIRED")
		}
	case "DISPUTED", "OVERDUE":
		if role != "ADMIN" && (role != "FINANCIER" || org != asset.OwnerOrgID) {
			return nil, failure("UNAUTHORIZED_ROLE")
		}
	case "REALIZED", "EBRC_ELIGIBLE", "CLOSED":
		if role != "ADMIN" {
			if err := settlementIdentity(ctx); err != nil {
				return nil, err
			}
		}
	default:
		return nil, failure("GUARDED_LEDGER_OPERATION")
	}
	if err := requireTransition(asset.Status, target); err != nil {
		return nil, err
	}
	if target == "OVERDUE" {
		now, err := transactionTime(ctx)
		if err != nil {
			return nil, err
		}
		due, err := time.Parse("2006-01-02", asset.DueDate)
		if err != nil {
			return nil, failure("CORRUPT_LEDGER_STATE")
		}
		if now.Before(due.Add(24 * time.Hour)) {
			return nil, failure("NOT_OVERDUE")
		}
	}
	asset.Status = target
	if target == "RELEASED" {
		asset.OwnerOrgID = ""
	}
	if target == "EBRC_ELIGIBLE" {
		asset.EbrcStatus = "SELF_CERTIFICATION_PENDING"
	}
	return writeAsset(ctx, asset)
}

func (c *TradeCredContract) OpenForFinancing(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "FINANCE_AVAILABLE")
}
func (c *TradeCredContract) RecordFinancing(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "FINANCED")
}
func (c *TradeCredContract) ReleaseLock(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "RELEASED")
}
func (c *TradeCredContract) MarkRealized(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "REALIZED")
}
func (c *TradeCredContract) MarkEbrcEligible(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "EBRC_ELIGIBLE")
}
func (c *TradeCredContract) CloseReceivable(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "CLOSED")
}
func (c *TradeCredContract) RaiseDispute(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "DISPUTED")
}
func (c *TradeCredContract) MarkOverdue(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	return c.transition(ctx, id, "OVERDUE")
}

func (c *TradeCredContract) ConfirmPayment(ctx contractapi.TransactionContextInterface, id string) (*Asset, error) {
	if err := settlementIdentity(ctx); err != nil {
		return nil, err
	}
	asset, err := readAsset(ctx, id)
	if err != nil {
		return nil, err
	}
	var payment Payment
	raw, err := transient(ctx, "payment", &payment)
	if err != nil {
		return nil, err
	}
	if !eventPattern.MatchString(payment.EventID) || !referencePattern.MatchString(payment.Reference) ||
		!digestPattern.MatchString(payment.Salt) {
		return nil, failure("INVALID_PAYMENT_EVENT")
	}
	// Public index is a digest; no raw bank reference or event ID enters world state.
	key := "payment:" + digest([]byte(payment.EventID))
	consumed, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if consumed != nil {
		return nil, failure("PAYMENT_EVENT_REPLAY")
	}
	if err := requireTransition(asset.Status, "PAYMENT_CONFIRMED"); err != nil {
		return nil, err
	}
	_, invoice, err := invoiceProof(ctx, asset)
	if err != nil {
		return nil, err
	}
	if payment.AmountMinor != invoice.AmountMinor {
		return nil, failure("PAYMENT_AMOUNT_MISMATCH")
	}
	if payment.Currency != asset.Currency {
		return nil, failure("PAYMENT_CURRENCY_MISMATCH")
	}
	asset.Status = "PAYMENT_CONFIRMED"
	asset.SettlementHash = digest(raw)
	if err := ctx.GetStub().PutState(key, []byte(id)); err != nil {
		return nil, err
	}
	return writeAsset(ctx, asset)
}

func (c *TradeCredContract) GetHistory(ctx contractapi.TransactionContextInterface, id string) ([]HistoryEntry, error) {
	if _, _, err := identity(ctx); err != nil {
		return nil, err
	}
	if _, err := readAsset(ctx, id); err != nil {
		return nil, err
	}
	iterator, err := ctx.GetStub().GetHistoryForKey(assetKey(id))
	if err != nil {
		return nil, err
	}
	defer iterator.Close()
	history := []HistoryEntry{}
	for iterator.HasNext() {
		change, err := iterator.Next()
		if err != nil {
			return nil, err
		}
		if change.IsDelete {
			return nil, failure("CORRUPT_LEDGER_HISTORY")
		}
		var asset Asset
		if err := json.Unmarshal(change.Value, &asset); err != nil {
			return nil, failure("CORRUPT_LEDGER_HISTORY")
		}
		if change.Timestamp == nil || change.Timestamp.CheckValid() != nil {
			return nil, failure("CORRUPT_LEDGER_HISTORY")
		}
		history = append(history, HistoryEntry{TransactionID: change.TxId, Timestamp: change.Timestamp.AsTime().UTC().Format(time.RFC3339Nano), Asset: &asset})
	}
	return history, nil
}
