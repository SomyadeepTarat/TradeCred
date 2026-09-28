package main

import "github.com/hyperledger/fabric-contract-api-go/v2/contractapi"

type TradeCredContract struct{ contractapi.Contract }

// No exact amount, buyer, invoice number, reference or commercial terms enter world state.
type Asset struct {
	ActorOrgID                string `json:"actorOrgId"`
	AssetID                   string `json:"assetId"`
	InvoiceFingerprint        string `json:"invoiceFingerprint"`
	DocumentHash              string `json:"documentHash"`
	ExporterOrgID             string `json:"exporterOrgId"`
	OwnerOrgID                string `json:"ownerOrgId"`
	Currency                  string `json:"currency"`
	FaceValueBucket           string `json:"faceValueBucket"`
	DueDate                   string `json:"dueDate"`
	Status                    string `json:"status"`
	AgreementHash             string `json:"agreementHash"`
	PrivateDetailsHash        string `json:"privateDetailsHash"`
	PrivateCollection         string `json:"privateCollection"`
	SettlementHash            string `json:"settlementHash"`
	EbrcStatus                string `json:"ebrcStatus"`
	Revision                  int64  `json:"revision"`
	UpdatedAt                 string `json:"updatedAt"`
	TransactionID             string `json:"transactionId"`
	RegistrationTransactionID string `json:"registrationTransactionId"`
	LockTransactionID         string `json:"lockTransactionId"`
}

type Registration struct {
	AssetID            string `json:"assetId"`
	InvoiceFingerprint string `json:"invoiceFingerprint"`
	DocumentHash       string `json:"documentHash"`
	ExporterOrgID      string `json:"exporterOrgId"`
	Currency           string `json:"currency"`
	DueDate            string `json:"dueDate"`
}

// Passed only in transient data. Salt prevents dictionary attacks on small amounts.
type PrivateInvoice struct {
	AssetID     string `json:"assetId"`
	AmountMinor int64  `json:"amountMinor"`
	Currency    string `json:"currency"`
	Salt        string `json:"salt"`
}

type Agreement struct {
	AgreementVersion   string `json:"agreementVersion"`
	AssetID            string `json:"assetId"`
	ExporterOrgID      string `json:"exporterOrgId"`
	FinancierOrgID     string `json:"financierOrgId"`
	AdvanceAmountMinor int64  `json:"advanceAmountMinor"`
	Currency           string `json:"currency"`
	DiscountRateBps    int64  `json:"discountRateBps"`
	TenorDays          int64  `json:"tenorDays"`
	AcceptedAt         string `json:"acceptedAt"`
	TermsVersion       string `json:"termsVersion"`
	AssignmentStatus   string `json:"assignmentStatus"`
}

type Offer struct {
	OfferID   string `json:"offerId"`
	ExpiresAt string `json:"expiresAt"`
}

type Payment struct {
	EventID     string `json:"eventId"`
	AmountMinor int64  `json:"amountMinor"`
	Currency    string `json:"currency"`
	Reference   string `json:"reference"`
	Salt        string `json:"salt"`
}

type HistoryEntry struct {
	TransactionID string `json:"transactionId"`
	Timestamp     string `json:"timestamp"`
	Asset         *Asset `json:"asset"`
}

type participant struct {
	MSP  string
	Role string
}

// Deployment profile, not runtime environment variables: every endorser uses identical rules.
var participants = map[string]participant{
	"ORG_EXPORTER_ALPHA":   {"ExporterAlphaMSP", "EXPORTER"},
	"ORG_EXPORTER_BETA":    {"ExporterBetaMSP", "EXPORTER"},
	"ORG_BANK_CITI_DEMO":   {"CitiDemoMSP", "FINANCIER"},
	"ORG_BANK_NBFC_DEMO":   {"NbfcDemoMSP", "FINANCIER"},
	"ORG_SETTLEMENT_BANK":  {"SettlementBankMSP", "SETTLEMENT_OPERATOR"},
	"ORG_CONSORTIUM_ADMIN": {"ConsortiumAdminMSP", "ADMIN"},
}

var transitions = map[string][]string{
	"DRAFT":             {"SUBMITTED"},
	"SUBMITTED":         {"VERIFIED"},
	"VERIFIED":          {"REGISTERED"},
	"REGISTERED":        {"FINANCE_AVAILABLE"},
	"FINANCE_AVAILABLE": {"LOCKED"},
	"LOCKED":            {"FINANCED", "RELEASED"},
	"FINANCED":          {"DISPUTED", "OVERDUE", "PAYMENT_CONFIRMED"},
	"PAYMENT_CONFIRMED": {"REALIZED"},
	"REALIZED":          {"EBRC_ELIGIBLE"},
	"EBRC_ELIGIBLE":     {"CLOSED"},
}

var pairCollections = map[string]map[string]string{
	"ORG_EXPORTER_ALPHA": {
		"ORG_BANK_CITI_DEMO": "ExporterBankCollectionAlphaCiti",
		"ORG_BANK_NBFC_DEMO": "ExporterBankCollectionAlphaNbfc",
	},
	"ORG_EXPORTER_BETA": {
		"ORG_BANK_CITI_DEMO": "ExporterBankCollectionBetaCiti",
		"ORG_BANK_NBFC_DEMO": "ExporterBankCollectionBetaNbfc",
	},
}
