package main

import (
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/v2/pkg/cid"
	"github.com/hyperledger/fabric-chaincode-go/v2/shim"
	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
	"github.com/hyperledger/fabric-protos-go-apiv2/ledger/queryresult"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// This harness models successful commit/rollback, not Fabric endorsement or MVCC.
type testStub struct {
	shim.ChaincodeStubInterface
	state     map[string][]byte
	private   map[string][]byte
	transient map[string][]byte
	history   map[string][]*queryresult.KeyModification
	tx        string
	now       time.Time
	fail      string
	actor     *testIdentity
	function  string
	args      []string
}

func (s *testStub) GetState(key string) ([]byte, error) {
	if s.fail == "read" {
		return nil, errors.New("read failed")
	}
	return s.state[key], nil
}
func (s *testStub) PutState(key string, value []byte) error {
	if s.fail == "write" {
		return errors.New("write failed")
	}
	s.state[key] = append([]byte(nil), value...)
	s.history[key] = append(s.history[key], &queryresult.KeyModification{TxId: s.tx, Value: append([]byte(nil), value...), Timestamp: timestamppb.New(s.now)})
	return nil
}
func (s *testStub) PutPrivateData(collection, key string, value []byte) error {
	if s.fail == "private" {
		return errors.New("private write failed")
	}
	s.private[collection+"/"+key] = append([]byte(nil), value...)
	return nil
}
func (s *testStub) GetPrivateDataHash(collection, key string) ([]byte, error) {
	if s.fail == "privateHash" {
		return nil, errors.New("private hash unavailable")
	}
	raw := s.private[collection+"/"+key]
	if raw == nil {
		return nil, nil
	}
	sum := sha256.Sum256(raw)
	return sum[:], nil
}
func (s *testStub) GetTransient() (map[string][]byte, error) {
	if s.fail == "transient" {
		return nil, errors.New("transient unavailable")
	}
	return s.transient, nil
}
func (s *testStub) GetTxID() string { return s.tx }
func (s *testStub) GetTxTimestamp() (*timestamppb.Timestamp, error) {
	if s.fail == "timestamp" {
		return nil, errors.New("timestamp unavailable")
	}
	return timestamppb.New(s.now), nil
}
func (s *testStub) SetEvent(_ string, _ []byte) error {
	if s.fail == "event" {
		return errors.New("event unavailable")
	}
	return nil
}
func (s *testStub) GetHistoryForKey(key string) (shim.HistoryQueryIteratorInterface, error) {
	if s.fail == "history" {
		return nil, errors.New("history disabled")
	}
	return &historyIterator{values: s.history[key]}, nil
}
func (s *testStub) GetFunctionAndParameters() (string, []string) { return s.function, s.args }
func (s *testStub) GetCreator() ([]byte, error)                  { return nil, nil }

type historyIterator struct {
	values   []*queryresult.KeyModification
	position int
}

func (i *historyIterator) HasNext() bool { return i.position < len(i.values) }
func (i *historyIterator) Next() (*queryresult.KeyModification, error) {
	if !i.HasNext() {
		return nil, errors.New("end")
	}
	v := i.values[i.position]
	i.position++
	return v, nil
}
func (i *historyIterator) Close() error { return nil }

type testIdentity struct {
	cid.ClientIdentity
	org, role, msp string
	service        bool
}

func (i *testIdentity) GetMSPID() (string, error) { return i.msp, nil }
func (i *testIdentity) GetAttributeValue(name string) (string, bool, error) {
	switch name {
	case "tradecred.org":
		return i.org, i.org != "", nil
	case "tradecred.role":
		return i.role, i.role != "", nil
	case "tradecred.settlement":
		return "true", i.service, nil
	}
	return "", false, nil
}

type dispatchContext struct{ contractapi.TransactionContext }

func (c *dispatchContext) GetClientIdentity() cid.ClientIdentity {
	return c.GetStub().(*testStub).actor
}

type harness struct {
	t         *testing.T
	stub      *testStub
	ctx       *contractapi.TransactionContext
	contract  *TradeCredContract
	reg       Registration
	invoice   []byte
	agreement []byte
	counter   int
}

func marshal(value any) []byte {
	raw, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	return raw
}
func newHarness(t *testing.T) *harness {
	stub := &testStub{state: map[string][]byte{}, private: map[string][]byte{},
		transient: map[string][]byte{}, history: map[string][]*queryresult.KeyModification{},
		now: time.Date(2026, 9, 27, 12, 0, 0, 0, time.UTC)}
	h := &harness{t: t, stub: stub, ctx: new(contractapi.TransactionContext), contract: new(TradeCredContract)}
	h.ctx.SetStub(stub)
	h.reg = Registration{"TC-001", strings.Repeat("a", 64), strings.Repeat("b", 64), "ORG_EXPORTER_ALPHA", "EUR", "2026-11-25"}
	h.invoice = marshal(PrivateInvoice{"TC-001", 1080000, "EUR", strings.Repeat("c", 64)})
	h.stub.transient["invoice"] = h.invoice
	h.as("ORG_CONSORTIUM_ADMIN")
	return h
}
func (h *harness) as(org string) {
	p := participants[org]
	actor := &testIdentity{org: org, role: p.Role, msp: p.MSP, service: true}
	h.stub.actor = actor
	h.ctx.SetClientIdentity(actor)
}
func (h *harness) invoke(fn func() (*Asset, error)) (*Asset, error) {
	h.counter++
	h.stub.tx = fmt.Sprintf("tx-%d", h.counter)
	state, private, history := maps.Clone(h.stub.state), maps.Clone(h.stub.private), maps.Clone(h.stub.history)
	asset, err := fn()
	if err != nil {
		h.stub.state, h.stub.private, h.stub.history = state, private, history
	}
	return asset, err
}
func (h *harness) must(fn func() (*Asset, error)) *Asset {
	h.t.Helper()
	asset, err := h.invoke(fn)
	if err != nil {
		h.t.Fatal(err)
	}
	return asset
}
func (h *harness) rejected(code string, fn func() (*Asset, error)) {
	h.t.Helper()
	before, _ := json.Marshal([]any{h.stub.state, h.stub.private, h.stub.history})
	_, err := h.invoke(fn)
	if err == nil || !strings.Contains(err.Error(), code) {
		h.t.Fatalf("expected %s; got %v", code, err)
	}
	after, _ := json.Marshal([]any{h.stub.state, h.stub.private, h.stub.history})
	if !reflect.DeepEqual(before, after) {
		h.t.Fatal("rejected transaction changed committed state")
	}
}
func (h *harness) verify() *Asset {
	return h.must(func() (*Asset, error) { return h.contract.VerifyReceivable(h.ctx, string(marshal(h.reg))) })
}
func (h *harness) registered() {
	h.as("ORG_CONSORTIUM_ADMIN")
	h.verify()
	h.as(h.reg.ExporterOrgID)
	h.must(func() (*Asset, error) { return h.contract.RegisterReceivable(h.ctx, string(marshal(h.reg))) })
}
func (h *harness) available() {
	h.registered()
	h.must(func() (*Asset, error) { return h.contract.OpenForFinancing(h.ctx, h.reg.AssetID) })
}
func (h *harness) terms(bank string) {
	agreement := Agreement{"TC-AGR-1", h.reg.AssetID, h.reg.ExporterOrgID, bank, 975000, h.reg.Currency, 250, 60,
		h.stub.now.Format(time.RFC3339Nano), "demo-v1", "CONSORTIUM_FINANCING_LOCK"}
	h.agreement = marshal(agreement)
	h.stub.transient["agreement"] = h.agreement
	h.stub.transient["offer"] = marshal(Offer{"OFFER-1", h.stub.now.Add(time.Hour).Format(time.RFC3339)})
}
func (h *harness) lock(bank string) *Asset {
	h.as(h.reg.ExporterOrgID)
	h.terms(bank)
	return h.must(func() (*Asset, error) {
		return h.contract.LockReceivable(h.ctx, h.reg.AssetID, bank, digest(h.agreement))
	})
}
func (h *harness) financed() {
	h.available()
	h.lock("ORG_BANK_CITI_DEMO")
	h.as("ORG_BANK_CITI_DEMO")
	h.must(func() (*Asset, error) { return h.contract.RecordFinancing(h.ctx, h.reg.AssetID) })
}
func (h *harness) payment(event string) {
	h.as("ORG_SETTLEMENT_BANK")
	h.stub.transient["payment"] = marshal(Payment{event, 1080000, "EUR", "IRM-PRIVATE", strings.Repeat("d", 64)})
}

func TestLifecycleAndSanitizedHistory(t *testing.T) {
	h := newHarness(t)
	h.financed()
	h.payment("PAY-1")
	confirmed := h.must(func() (*Asset, error) { return h.contract.ConfirmPayment(h.ctx, "TC-001") })
	if confirmed.Status != "PAYMENT_CONFIRMED" {
		t.Fatal(confirmed)
	}
	h.must(func() (*Asset, error) { return h.contract.MarkRealized(h.ctx, "TC-001") })
	eligible := h.must(func() (*Asset, error) { return h.contract.MarkEbrcEligible(h.ctx, "TC-001") })
	if eligible.EbrcStatus != "SELF_CERTIFICATION_PENDING" {
		t.Fatal(eligible)
	}
	closed := h.must(func() (*Asset, error) { return h.contract.CloseReceivable(h.ctx, "TC-001") })
	if closed.Status != "CLOSED" || closed.Revision != 9 {
		t.Fatal(closed)
	}
	history, err := h.contract.GetHistory(h.ctx, "TC-001")
	if err != nil || len(history) != 9 {
		t.Fatalf("%v %v", history, err)
	}
	for index, item := range history {
		if item.Asset.Revision != int64(index+1) || item.TransactionID == "" {
			t.Fatal(item)
		}
	}
	global := string(marshal(history))
	for _, raw := range h.stub.state {
		global += string(raw)
	}
	for _, secret := range []string{"1080000", "975000", "amountMinor", "discountRateBps", "IRM-PRIVATE", strings.Repeat("c", 64)} {
		if strings.Contains(global, secret) {
			t.Fatalf("world state/history leaks %s", secret)
		}
	}
	if !bytesEqual(h.stub.private["ExporterBankCollectionAlphaCiti/agreement:TC-001"], h.agreement) {
		t.Fatal("agreement not private")
	}
	if _, ok := h.stub.private["ExporterBankCollectionAlphaNbfc/asset:TC-001"]; ok {
		t.Fatal("competitor received private invoice")
	}
	h.rejected("INVALID_STATE_TRANSITION", func() (*Asset, error) { return h.contract.MarkRealized(h.ctx, "TC-001") })
	h.as(h.reg.ExporterOrgID)
	h.rejected("INVALID_STATE_TRANSITION", func() (*Asset, error) { return h.contract.OpenForFinancing(h.ctx, "TC-001") })
}
func bytesEqual(a, b []byte) bool { return string(a) == string(b) }

func TestRegistryAndRegistrationRetries(t *testing.T) {
	h := newHarness(t)
	h.financed()
	h.as(h.reg.ExporterOrgID)
	replay := h.must(func() (*Asset, error) { return h.contract.RegisterReceivable(h.ctx, string(marshal(h.reg))) })
	if replay.Status != "FINANCED" || replay.Revision != 5 || replay.RegistrationTransactionID != "tx-2" {
		t.Fatal(replay)
	}
	found, err := h.contract.GetReceivableByFingerprint(h.ctx, h.reg.InvoiceFingerprint)
	if err != nil || found.AssetID != "TC-001" {
		t.Fatal(found, err)
	}
	h.reg.AssetID = "TC-DUPLICATE"
	h.rejected("DUPLICATE_RECEIVABLE", func() (*Asset, error) { return h.contract.RegisterReceivable(h.ctx, string(marshal(h.reg))) })
	h.as("ORG_CONSORTIUM_ADMIN")
	h.stub.transient["invoice"] = marshal(PrivateInvoice{"TC-DUPLICATE", 1080000, "EUR", strings.Repeat("c", 64)})
	h.rejected("DUPLICATE_RECEIVABLE", func() (*Asset, error) { return h.contract.VerifyReceivable(h.ctx, string(marshal(h.reg))) })
	h.reg.AssetID = "TC-001"
	h.reg.DocumentHash = strings.Repeat("e", 64)
	h.stub.transient["invoice"] = h.invoice
	h.rejected("REGISTRATION_CONFLICT", func() (*Asset, error) { return h.contract.VerifyReceivable(h.ctx, string(marshal(h.reg))) })
}

func TestLockOwnershipAndIdempotency(t *testing.T) {
	h := newHarness(t)
	h.available()
	lock := h.lock("ORG_BANK_CITI_DEMO")
	h.rejected("INVALID_STATE_TRANSITION", func() (*Asset, error) {
		return h.contract.LockReceivable(h.ctx, "TC-001", "ORG_BANK_NBFC_DEMO", strings.Repeat("f", 64))
	})
	h.as("ORG_BANK_NBFC_DEMO")
	h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.RecordFinancing(h.ctx, "TC-001") })
	h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.ReleaseLock(h.ctx, "TC-001") })
	h.as("ORG_BANK_CITI_DEMO")
	h.must(func() (*Asset, error) { return h.contract.RecordFinancing(h.ctx, "TC-001") })
	h.as(h.reg.ExporterOrgID)
	retry := h.must(func() (*Asset, error) {
		return h.contract.LockReceivable(h.ctx, "TC-001", "ORG_BANK_CITI_DEMO", digest(h.agreement))
	})
	if retry.Status != "FINANCED" || retry.LockTransactionID != lock.LockTransactionID || retry.Revision != 5 {
		t.Fatal(retry)
	}
}

func TestAuthorization(t *testing.T) {
	for _, org := range []string{"ORG_EXPORTER_ALPHA", "ORG_EXPORTER_BETA", "ORG_BANK_CITI_DEMO", "ORG_SETTLEMENT_BANK", "UNKNOWN"} {
		t.Run("verify-"+org, func(t *testing.T) {
			h := newHarness(t)
			h.as(org)
			h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.VerifyReceivable(h.ctx, string(marshal(h.reg))) })
		})
	}
	for _, kind := range []string{"missing", "msp", "role", "org"} {
		t.Run("identity-"+kind, func(t *testing.T) {
			h := newHarness(t)
			h.registered()
			switch kind {
			case "missing":
				h.stub.actor.org = ""
			case "msp":
				h.stub.actor.msp = "OtherMSP"
			case "role":
				h.stub.actor.role = "ADMIN"
			case "org":
				h.stub.actor.org = "ORG_EXPORTER_BETA"
			}
			h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.GetReceivable(h.ctx, "TC-001") })
		})
	}
	h := newHarness(t)
	h.registered()
	h.as("ORG_EXPORTER_BETA")
	h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.OpenForFinancing(h.ctx, "TC-001") })
	h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.RegisterReceivable(h.ctx, string(marshal(h.reg))) })
}

func TestPaymentValidationAndReplayAcrossAssets(t *testing.T) {
	for _, kind := range []string{"amount", "currency", "reference", "service", "role", "proof", "missing"} {
		t.Run(kind, func(t *testing.T) {
			h := newHarness(t)
			h.financed()
			h.payment("PAY-1")
			payment := Payment{"PAY-1", 1080000, "EUR", "IRM-PRIVATE", strings.Repeat("d", 64)}
			code := "INVALID_PAYMENT_EVENT"
			switch kind {
			case "amount":
				payment.AmountMinor = 975000
				code = "PAYMENT_AMOUNT_MISMATCH"
			case "currency":
				payment.Currency = "INR"
				code = "PAYMENT_CURRENCY_MISMATCH"
			case "reference":
				payment.Reference = ""
			case "service":
				h.stub.actor.service = false
				code = "UNAUTHORIZED_ROLE"
			case "role":
				h.as("ORG_CONSORTIUM_ADMIN")
				code = "UNAUTHORIZED_ROLE"
			case "proof":
				h.stub.transient["invoice"] = marshal(PrivateInvoice{"TC-001", 1, "EUR", strings.Repeat("c", 64)})
				code = "PRIVATE_DETAILS_MISMATCH"
			case "missing":
				delete(h.stub.private, "_implicit_org_ExporterAlphaMSP/asset:TC-001")
				code = "PRIVATE_DETAILS_MISMATCH"
			}
			h.stub.transient["payment"] = marshal(payment)
			h.rejected(code, func() (*Asset, error) { return h.contract.ConfirmPayment(h.ctx, "TC-001") })
		})
	}
	h := newHarness(t)
	h.financed()
	h.payment("PAY-REPLAY")
	h.must(func() (*Asset, error) { return h.contract.ConfirmPayment(h.ctx, "TC-001") })
	h.rejected("PAYMENT_EVENT_REPLAY", func() (*Asset, error) { return h.contract.ConfirmPayment(h.ctx, "TC-001") })
	// Reuse an event against a distinct, otherwise valid financed asset.
	h.reg.AssetID = "TC-002"
	h.reg.InvoiceFingerprint = strings.Repeat("e", 64)
	h.invoice = marshal(PrivateInvoice{"TC-002", 1080000, "EUR", strings.Repeat("f", 64)})
	h.stub.transient["invoice"] = h.invoice
	h.financed()
	h.payment("PAY-REPLAY")
	h.rejected("PAYMENT_EVENT_REPLAY", func() (*Asset, error) { return h.contract.ConfirmPayment(h.ctx, "TC-002") })
	h.payment("PAY-NEW")
	h.must(func() (*Asset, error) { return h.contract.ConfirmPayment(h.ctx, "TC-002") })
}

func TestReleaseDisputeAndOverdue(t *testing.T) {
	t.Run("release", func(t *testing.T) {
		h := newHarness(t)
		h.available()
		h.lock("ORG_BANK_CITI_DEMO")
		h.as("ORG_BANK_CITI_DEMO")
		asset := h.must(func() (*Asset, error) { return h.contract.ReleaseLock(h.ctx, "TC-001") })
		if asset.Status != "RELEASED" || asset.OwnerOrgID != "" {
			t.Fatal(asset)
		}
		h.rejected("UNAUTHORIZED_ROLE", func() (*Asset, error) { return h.contract.RecordFinancing(h.ctx, "TC-001") })
	})
	t.Run("dispute", func(t *testing.T) {
		h := newHarness(t)
		h.financed()
		asset := h.must(func() (*Asset, error) { return h.contract.RaiseDispute(h.ctx, "TC-001") })
		if asset.Status != "DISPUTED" {
			t.Fatal(asset)
		}
	})
	t.Run("overdue", func(t *testing.T) {
		h := newHarness(t)
		h.financed()
		h.rejected("NOT_OVERDUE", func() (*Asset, error) { return h.contract.MarkOverdue(h.ctx, "TC-001") })
		h.stub.now = time.Date(2026, 11, 26, 0, 0, 0, 0, time.UTC)
		asset := h.must(func() (*Asset, error) { return h.contract.MarkOverdue(h.ctx, "TC-001") })
		if asset.Status != "OVERDUE" {
			t.Fatal(asset)
		}
	})
}

func TestStorageErrorsNeverSucceed(t *testing.T) {
	for _, failure := range []string{"read", "write", "private", "transient", "timestamp", "event", "privateHash"} {
		t.Run(failure, func(t *testing.T) {
			h := newHarness(t)
			h.available()
			h.terms("ORG_BANK_CITI_DEMO")
			h.stub.fail = failure
			h.rejected("", func() (*Asset, error) {
				return h.contract.LockReceivable(h.ctx, "TC-001", "ORG_BANK_CITI_DEMO", digest(h.agreement))
			})
		})
	}
	h := newHarness(t)
	h.registered()
	h.stub.fail = "history"
	if _, err := h.contract.GetHistory(h.ctx, "TC-001"); err == nil {
		t.Fatal("history failure concealed")
	}
}

func TestContractMetadataAndDispatch(t *testing.T) {
	if _, err := newChaincode(); err != nil {
		t.Fatal(err)
	}
	h := newHarness(t)
	cc, err := contractapi.NewChaincode(&TradeCredContract{Contract: contractapi.Contract{TransactionContextHandler: &dispatchContext{}}})
	if err != nil {
		t.Fatal(err)
	}
	h.stub.function = "VerifyReceivable"
	h.stub.args = []string{string(marshal(h.reg))}
	h.stub.tx = "dispatch"
	response := cc.Invoke(h.stub)
	if response.Status != 200 {
		t.Fatalf("%d %s", response.Status, response.Message)
	}
	h.as(h.reg.ExporterOrgID)
	h.stub.function = "GetReceivable"
	h.stub.args = []string{"TC-001"}
	response = cc.Invoke(h.stub)
	if response.Status != 200 || !strings.Contains(string(response.Payload), "VERIFIED") {
		t.Fatal(response)
	}
	h.stub.function = "transition"
	h.stub.args = []string{"TC-001", "CLOSED"}
	if cc.Invoke(h.stub).Status == 200 {
		t.Fatal("private transition helper was exposed")
	}
}

func TestTransitionMatrixAndCurrencyBounds(t *testing.T) {
	raw, err := os.ReadFile("state_transitions.json")
	if err != nil {
		t.Fatal(err)
	}
	var expected map[string][]string
	if err := json.Unmarshal(raw, &expected); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(transitions, expected) {
		t.Fatal("state matrix changed")
	}
	statuses := []string{"DRAFT", "SUBMITTED", "VERIFIED", "REGISTERED", "FINANCE_AVAILABLE", "LOCKED", "FINANCED", "PAYMENT_CONFIRMED", "REALIZED", "EBRC_ELIGIBLE", "CLOSED", "REJECTED_DUPLICATE", "RELEASED", "OVERDUE", "DISPUTED"}
	for _, from := range statuses {
		for _, to := range statuses {
			allowed := false
			for _, target := range expected[from] {
				if target == to {
					allowed = true
				}
			}
			if (requireTransition(from, to) == nil) != allowed {
				t.Fatalf("%s -> %s", from, to)
			}
		}
	}
	for _, test := range []struct {
		amount         int64
		currency, want string
	}{
		{999999, "EUR", "0-10000"}, {1000000, "EUR", "10000-25000"},
		{2500000, "EUR", "25000-100000"}, {9999, "JPY", "0-10000"},
		{10000000, "KWD", "10000-25000"}, {9223372036854775807, "EUR", "1000000+"},
	} {
		if actual := bucket(test.amount, test.currency); actual != test.want {
			t.Fatalf("%+v: %s", test, actual)
		}
	}
}

func TestMalformedRegistrationAndPrivateInput(t *testing.T) {
	for _, kind := range []string{"asset", "fingerprint", "document", "exporter", "currency", "date", "amount", "salt", "unknown", "duplicate", "trailing", "large", "missing"} {
		t.Run(kind, func(t *testing.T) {
			h := newHarness(t)
			raw := string(marshal(h.reg))
			switch kind {
			case "asset":
				h.reg.AssetID = "../asset"
			case "fingerprint":
				h.reg.InvoiceFingerprint = "short"
			case "document":
				h.reg.DocumentHash = "bad"
			case "exporter":
				h.reg.ExporterOrgID = "ORG_BANK_CITI_DEMO"
			case "currency":
				h.reg.Currency = "XXX"
			case "date":
				h.reg.DueDate = "2026-02-30"
			case "amount":
				h.stub.transient["invoice"] = marshal(PrivateInvoice{"TC-001", 0, "EUR", strings.Repeat("c", 64)})
			case "salt":
				h.stub.transient["invoice"] = marshal(PrivateInvoice{"TC-001", 1080000, "EUR", "guessable"})
			case "unknown":
				raw = raw[:len(raw)-1] + `,"buyerName":"must-not-be-public"}`
			case "duplicate":
				raw = raw[:len(raw)-1] + `,"assetId":"TC-001"}`
			case "trailing":
				raw += " {}"
			case "large":
				raw = strings.Repeat(" ", 8193)
			case "missing":
				delete(h.stub.transient, "invoice")
			}
			if kind == "asset" || kind == "fingerprint" || kind == "document" || kind == "exporter" || kind == "currency" || kind == "date" {
				raw = string(marshal(h.reg))
			}
			h.rejected("", func() (*Asset, error) { return h.contract.VerifyReceivable(h.ctx, raw) })
		})
	}
	h := newHarness(t)
	h.as(h.reg.ExporterOrgID)
	h.rejected("ASSET_NOT_FOUND", func() (*Asset, error) { return h.contract.RegisterReceivable(h.ctx, string(marshal(h.reg))) })
}

func TestInvalidOfferAgreementAndOtherOrganization(t *testing.T) {
	for _, kind := range []string{"expired", "bad_expiry", "amount", "currency", "financier", "hash", "accepted", "tenor", "rate", "proof", "foreign_exporter", "unknown_bank"} {
		t.Run(kind, func(t *testing.T) {
			h := newHarness(t)
			h.available()
			h.terms("ORG_BANK_CITI_DEMO")
			var agreement Agreement
			if err := json.Unmarshal(h.agreement, &agreement); err != nil {
				t.Fatal(err)
			}
			switch kind {
			case "expired":
				h.stub.transient["offer"] = marshal(Offer{"offer", h.stub.now.Format(time.RFC3339Nano)})
			case "bad_expiry":
				h.stub.transient["offer"] = marshal(Offer{"offer", "not-a-date"})
			case "amount":
				agreement.AdvanceAmountMinor = 1080001
			case "currency":
				agreement.Currency = "INR"
			case "financier":
				agreement.FinancierOrgID = "ORG_BANK_NBFC_DEMO"
			case "accepted":
				agreement.AcceptedAt = h.stub.now.Add(time.Hour).Format(time.RFC3339)
			case "tenor":
				agreement.TenorDays = 0
			case "rate":
				agreement.DiscountRateBps = 10001
			case "proof":
				h.stub.transient["invoice"] = marshal(PrivateInvoice{"TC-001", 1080001, "EUR", strings.Repeat("c", 64)})
			case "foreign_exporter":
				h.as("ORG_EXPORTER_BETA")
			}
			h.agreement = marshal(agreement)
			h.stub.transient["agreement"] = h.agreement
			hash := digest(h.agreement)
			if kind == "hash" {
				hash = strings.Repeat("f", 64)
			}
			bank := "ORG_BANK_CITI_DEMO"
			if kind == "unknown_bank" {
				bank = "UNREGISTERED"
			}
			h.rejected("", func() (*Asset, error) { return h.contract.LockReceivable(h.ctx, "TC-001", bank, hash) })
		})
	}
}

func TestCollectionPoliciesMatchParticipantPairs(t *testing.T) {
	raw, err := os.ReadFile("collections_config.json")
	if err != nil {
		t.Fatal(err)
	}
	var collections []struct {
		Name              string
		Policy            string
		MemberOnlyRead    bool
		MemberOnlyWrite   bool
		EndorsementPolicy struct{ SignaturePolicy string }
	}
	if err := json.Unmarshal(raw, &collections); err != nil {
		t.Fatal(err)
	}
	if len(collections) != 4 {
		t.Fatal("expected four isolated pair collections")
	}
	for exporter, banks := range pairCollections {
		for bank, name := range banks {
			found := false
			for _, collection := range collections {
				if collection.Name != name {
					continue
				}
				found = true
				exporterMSP, bankMSP := participants[exporter].MSP, participants[bank].MSP
				want := fmt.Sprintf("OR('%s.member','%s.member')", exporterMSP, bankMSP)
				endorsement := fmt.Sprintf("AND('%s.peer','%s.peer')", exporterMSP, bankMSP)
				if collection.Policy != want || collection.EndorsementPolicy.SignaturePolicy != endorsement ||
					!collection.MemberOnlyRead || !collection.MemberOnlyWrite {
					t.Fatal(collection)
				}
			}
			if !found {
				t.Fatal("missing pair collection", name)
			}
		}
	}
}
