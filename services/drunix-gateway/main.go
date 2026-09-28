// Authenticated internal HTTP bridge to the official Fabric Gateway gRPC client.
// It never substitutes mock results for a failed proposal, submission or commit.
package main

import (
	"context"
	"crypto/subtle"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"github.com/hyperledger/fabric-gateway/pkg/identity"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

type IdentityConfig struct {
	OrgID          string `json:"orgId"`
	Role           string `json:"role"`
	MSPID          string `json:"mspId"`
	Certificate    string `json:"certificate"`
	PrivateKey     string `json:"privateKey"`
	Endpoint       string `json:"endpoint"`
	TLSCertificate string `json:"tlsCertificate"`
	TLSServerName  string `json:"tlsServerName"`
}
type Config struct {
	NetworkID  string           `json:"networkId"`
	Channel    string           `json:"channel"`
	Chaincode  string           `json:"chaincode"`
	Identities []IdentityConfig `json:"identities"`
}
type Request struct {
	NetworkID    string            `json:"networkId"`
	Channel      string            `json:"channel"`
	Chaincode    string            `json:"chaincode"`
	OrgID        string            `json:"orgId"`
	Role         string            `json:"role"`
	Method       string            `json:"method"`
	Arguments    []string          `json:"arguments"`
	Transient    map[string]string `json:"transient"`
	OperationID  string            `json:"operationId"`
	EndorserOrgs []string          `json:"endorserOrgs"`
}
type Invoker interface {
	Invoke(context.Context, Request, bool) ([]byte, error)
}
type fabricInvoker struct{ config Config }

func loadConfig(path string) (Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	var config Config
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&config); err != nil {
		return config, err
	}
	if decoder.Decode(new(any)) != io.EOF {
		return config, errors.New("trailing configuration data")
	}
	if config.NetworkID == "" || config.Channel == "" || config.Chaincode == "" || len(config.Identities) == 0 {
		return config, errors.New("network, channel, chaincode and identities are required")
	}
	seen := map[string]bool{}
	for _, entry := range config.Identities {
		key := entry.OrgID + "/" + entry.Role
		if seen[key] || entry.OrgID == "" || entry.Role == "" || entry.MSPID == "" ||
			entry.Endpoint == "" || entry.TLSServerName == "" || entry.Certificate == "" || entry.PrivateKey == "" || entry.TLSCertificate == "" {
			return config, errors.New("invalid or duplicate identity mapping")
		}
		seen[key] = true
	}
	return config, nil
}

func (f *fabricInvoker) Invoke(ctx context.Context, request Request, submit bool) ([]byte, error) {
	var selected *IdentityConfig
	orgMSP := map[string]string{}
	for _, entry := range f.config.Identities {
		orgMSP[entry.OrgID] = entry.MSPID
		if entry.OrgID == request.OrgID && entry.Role == request.Role {
			value := entry
			selected = &value
		}
	}
	if selected == nil {
		return nil, errors.New("UNAUTHORIZED_ROLE")
	}
	certBytes, err := os.ReadFile(selected.Certificate)
	if err != nil {
		return nil, err
	}
	certificate, err := identity.CertificateFromPEM(certBytes)
	if err != nil {
		return nil, err
	}
	id, err := identity.NewX509Identity(selected.MSPID, certificate)
	if err != nil {
		return nil, err
	}
	keyBytes, err := os.ReadFile(selected.PrivateKey)
	if err != nil {
		return nil, err
	}
	key, err := identity.PrivateKeyFromPEM(keyBytes)
	if err != nil {
		return nil, err
	}
	signer, err := identity.NewPrivateKeySign(key)
	if err != nil {
		return nil, err
	}
	rootBytes, err := os.ReadFile(selected.TLSCertificate)
	if err != nil {
		return nil, err
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(rootBytes) {
		return nil, errors.New("invalid TLS root")
	}
	conn, err := grpc.NewClient(selected.Endpoint, grpc.WithTransportCredentials(credentials.NewTLS(
		&tls.Config{RootCAs: roots, ServerName: selected.TLSServerName, MinVersion: tls.VersionTLS12})))
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	gateway, err := client.Connect(id, client.WithSign(signer), client.WithClientConnection(conn),
		client.WithEvaluateTimeout(10*time.Second), client.WithEndorseTimeout(15*time.Second),
		client.WithSubmitTimeout(10*time.Second), client.WithCommitStatusTimeout(20*time.Second))
	if err != nil {
		return nil, err
	}
	defer gateway.Close()
	contract := gateway.GetNetwork(f.config.Channel).GetContract(f.config.Chaincode)
	transient := map[string][]byte{}
	for k, v := range request.Transient {
		transient[k] = []byte(v)
	}
	endorsers := []string{}
	for _, org := range request.EndorserOrgs {
		msp, ok := orgMSP[org]
		if !ok {
			return nil, errors.New("UNAUTHORIZED_ROLE")
		}
		endorsers = append(endorsers, msp)
	}
	if len(endorsers) == 0 {
		return nil, errors.New("explicit endorsers required")
	}
	options := []client.ProposalOption{client.WithArguments(request.Arguments...), client.WithTransient(transient), client.WithEndorsingOrganizations(endorsers...)}
	if !submit {
		return contract.EvaluateWithContext(ctx, request.Method, options...)
	}
	args, err := json.Marshal(request.Arguments)
	if err != nil {
		return nil, err
	}
	options[0] = client.WithArguments(request.OperationID, request.Method, string(args))
	// SubmitWithContext returns only after a VALID commit, not merely endorsement.
	return contract.SubmitWithContext(ctx, "Execute", options...)
}

var evaluateMethods = map[string]bool{"GetReceivable": true, "GetReceivableByFingerprint": true, "GetHistory": true, "GetOperationReceipt": true}
var submitMethods = map[string]bool{"VerifyReceivable": true, "RegisterReceivable": true, "OpenForFinancing": true, "LockReceivable": true, "RecordFinancing": true, "ReleaseLock": true, "ConfirmPayment": true, "MarkRealized": true, "MarkEbrcEligible": true, "CloseReceivable": true, "RaiseDispute": true, "MarkOverdue": true}

func errorCode(err error) string {
	// Allowlisted code only: never forward SDK errors containing proposals or local key paths.
	for _, code := range []string{"ASSET_NOT_FOUND", "OPERATION_NOT_FOUND", "UNAUTHORIZED_ROLE", "DUPLICATE_RECEIVABLE", "OPERATION_CONFLICT", "REGISTRATION_CONFLICT", "INVALID_STATE_TRANSITION", "PAYMENT_EVENT_REPLAY", "PAYMENT_AMOUNT_MISMATCH", "PAYMENT_CURRENCY_MISMATCH", "PRIVATE_DETAILS_MISMATCH", "INVALID_FINANCING_TERMS", "OFFER_EXPIRED_OR_INVALID", "INVALID_AGREEMENT_TIME"} {
		if strings.Contains(err.Error(), code) {
			return code
		}
	}
	return "LEDGER_UNAVAILABLE"
}

func handler(config Config, token string, invoker Invoker) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		fail := func(status int, code string) {
			w.WriteHeader(status)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": code})
		}
		if subtle.ConstantTimeCompare([]byte(r.Header.Get("Authorization")), []byte("Bearer "+token)) != 1 {
			fail(401, "GATEWAY_AUTHENTICATION_REQUIRED")
			return
		}
		if r.Method != "POST" || (r.URL.Path != "/evaluate" && r.URL.Path != "/submit") {
			fail(404, "NOT_FOUND")
			return
		}
		decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 65536))
		decoder.DisallowUnknownFields()
		var request Request
		if decoder.Decode(&request) != nil {
			fail(400, "INVALID_REQUEST")
			return
		}
		var extra any
		if decoder.Decode(&extra) != io.EOF {
			fail(400, "INVALID_REQUEST")
			return
		}
		submit := r.URL.Path == "/submit"
		if request.NetworkID != config.NetworkID || request.Channel != config.Channel || request.Chaincode != config.Chaincode ||
			(submit && (!submitMethods[request.Method] || len(request.OperationID) != 64)) ||
			(!submit && (!evaluateMethods[request.Method] || len(request.Transient) != 0)) {
			fail(400, "INVALID_REQUEST")
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 45*time.Second)
		defer cancel()
		result, err := invoker.Invoke(ctx, request, submit)
		if err != nil {
			code := errorCode(err)
			status := 409
			if code == "LEDGER_UNAVAILABLE" {
				status = 503
			}
			if code == "UNAUTHORIZED_ROLE" {
				status = 403
			}
			if code == "ASSET_NOT_FOUND" || code == "OPERATION_NOT_FOUND" {
				status = 404
			}
			fail(status, code)
			return
		}
		if !json.Valid(result) {
			fail(503, "LEDGER_UNAVAILABLE")
			return
		}
		_ = json.NewEncoder(w).Encode(struct {
			Backend   string          `json:"backend"`
			Committed bool            `json:"committed"`
			Result    json.RawMessage `json:"result"`
		}{"drunix", submit, result})
	})
}

func checkFiles(config Config) error {
	for _, entry := range config.Identities {
		certBytes, err := os.ReadFile(entry.Certificate)
		if err != nil {
			return err
		}
		if _, err := identity.CertificateFromPEM(certBytes); err != nil {
			return err
		}
		keyBytes, err := os.ReadFile(entry.PrivateKey)
		if err != nil {
			return err
		}
		key, err := identity.PrivateKeyFromPEM(keyBytes)
		if err != nil {
			return err
		}
		if _, err := identity.NewPrivateKeySign(key); err != nil {
			return err
		}
		roots, err := os.ReadFile(entry.TLSCertificate)
		if err != nil {
			return err
		}
		if !x509.NewCertPool().AppendCertsFromPEM(roots) {
			return errors.New("invalid TLS root")
		}
	}
	return nil
}

func main() {
	if len(os.Args) == 2 && os.Args[1] == "--check-config" {
		config, err := loadConfig(os.Getenv("DRUNIX_GATEWAY_CONFIG"))
		if err != nil || checkFiles(config) != nil {
			log.Fatal("Configuration or identity/TLS files are invalid")
		}
		fmt.Println("Configuration and key files parse successfully; network connectivity is not verified")
		return
	}
	token := os.Getenv("DRUNIX_GATEWAY_TOKEN")
	if len(token) < 32 {
		log.Fatal("DRUNIX_GATEWAY_TOKEN must contain at least 32 characters")
	}
	config, err := loadConfig(os.Getenv("DRUNIX_GATEWAY_CONFIG"))
	if err != nil {
		log.Fatal("Gateway configuration unavailable or invalid")
	}
	address := os.Getenv("DRUNIX_LISTEN")
	if address == "" {
		address = "127.0.0.1:8080"
	}
	server := &http.Server{Addr: address, Handler: handler(config, token, &fabricInvoker{config}),
		ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 50 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 8192}
	fmt.Println("TradeCred Fabric gateway listening; no mock backend")
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal("Gateway stopped")
	}
}
