package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type testInvoker struct {
	called  bool
	request Request
	submit  bool
	err     error
	result  []byte
}

func (i *testInvoker) Invoke(_ context.Context, r Request, submit bool) ([]byte, error) {
	i.called = true
	i.request = r
	i.submit = submit
	if i.err != nil {
		return nil, i.err
	}
	if i.result != nil {
		return i.result, nil
	}
	return []byte(`{"asset":{"status":"REGISTERED"}}`), nil
}
func TestHTTPBoundary(t *testing.T) {
	token := strings.Repeat("x", 32)
	config := Config{NetworkID: "test-network", Channel: "tradecred", Chaincode: "tradecred"}
	for _, test := range []struct {
		name, path, auth, method, network string
		want                              int
	}{
		{"evaluate", "/evaluate", "Bearer " + token, "GetReceivable", "test-network", 200},
		{"submit", "/submit", "Bearer " + token, "ConfirmPayment", "test-network", 200},
		{"unauthorized", "/submit", "", "ConfirmPayment", "test-network", 401},
		{"network", "/submit", "Bearer " + token, "ConfirmPayment", "wrong", 400},
		{"method", "/submit", "Bearer " + token, "DeleteAsset", "test-network", 400},
		{"query-mutation", "/evaluate", "Bearer " + token, "ConfirmPayment", "test-network", 400},
		{"path", "/unknown", "Bearer " + token, "GetReceivable", "test-network", 404},
	} {
		t.Run(test.name, func(t *testing.T) {
			invocation := &testInvoker{}
			input := Request{NetworkID: test.network, Channel: "tradecred", Chaincode: "tradecred", OrgID: "ORG_SETTLEMENT_BANK",
				Role: "SETTLEMENT_OPERATOR", Method: test.method, Arguments: []string{"TC-001"},
				OperationID: strings.Repeat("a", 64), EndorserOrgs: []string{"ORG_SETTLEMENT_BANK"}}
			body, _ := json.Marshal(input)
			request := httptest.NewRequest("POST", test.path, strings.NewReader(string(body)))
			request.Header.Set("Authorization", test.auth)
			response := httptest.NewRecorder()
			handler(config, token, invocation).ServeHTTP(response, request)
			if response.Code != test.want {
				t.Fatal(response.Code, response.Body.String())
			}
			if (test.want == 200) != invocation.called {
				t.Fatal("unexpected SDK invocation")
			}
			if response.Header().Get("Cache-Control") != "no-store" {
				t.Fatal("cacheable financial response")
			}
			if test.want == 200 {
				var envelope struct {
					Backend   string
					Committed bool
				}
				if err := json.Unmarshal(response.Body.Bytes(), &envelope); err != nil {
					t.Fatal(err)
				}
				if envelope.Backend != "drunix" || envelope.Committed != (test.path == "/submit") {
					t.Fatal(envelope)
				}
			}
		})
	}
}
func TestErrorsAndUnknownCommitNeverReturnSuccess(t *testing.T) {
	config := Config{NetworkID: "network", Channel: "channel", Chaincode: "tradecred"}
	token := strings.Repeat("x", 32)
	for _, test := range []struct {
		err  error
		want int
		code string
	}{
		{errors.New("commit status timeout with SECRET"), 503, "LEDGER_UNAVAILABLE"},
		{errors.New("endorsement INVALID_STATE_TRANSITION SECRET"), 409, "INVALID_STATE_TRANSITION"},
		{errors.New("ASSET_NOT_FOUND SECRET"), 404, "ASSET_NOT_FOUND"},
		{errors.New("UNAUTHORIZED_ROLE SECRET"), 403, "UNAUTHORIZED_ROLE"},
	} {
		invocation := &testInvoker{err: test.err}
		body, _ := json.Marshal(Request{NetworkID: "network", Channel: "channel", Chaincode: "tradecred",
			Method: "ConfirmPayment", OperationID: strings.Repeat("a", 64)})
		request := httptest.NewRequest("POST", "/submit", strings.NewReader(string(body)))
		request.Header.Set("Authorization", "Bearer "+token)
		response := httptest.NewRecorder()
		handler(config, token, invocation).ServeHTTP(response, request)
		if response.Code != test.want || !strings.Contains(response.Body.String(), test.code) ||
			strings.Contains(response.Body.String(), "SECRET") {
			t.Fatal(response.Body.String())
		}
	}
}
func TestMalformedAndOversizedRequests(t *testing.T) {
	for _, body := range []string{"invalid", strings.Repeat("x", 65537), `{"unexpected":true}`, `{} {}`} {
		invocation := &testInvoker{}
		request := httptest.NewRequest("POST", "/submit", strings.NewReader(body))
		request.Header.Set("Authorization", "Bearer "+strings.Repeat("x", 32))
		response := httptest.NewRecorder()
		handler(Config{}, strings.Repeat("x", 32), invocation).ServeHTTP(response, request)
		if response.Code != 400 || invocation.called {
			t.Fatal(response.Code)
		}
	}
}

func TestConfigurationFailsClosed(t *testing.T) {
	path := filepath.Join(t.TempDir(), "gateway.json")
	entry := IdentityConfig{OrgID: "ORG", Role: "EXPORTER", MSPID: "MSP", Certificate: "/missing/cert", PrivateKey: "/missing/key", Endpoint: "peer:7051", TLSCertificate: "/missing/tls", TLSServerName: "peer"}
	valid := Config{NetworkID: "network", Channel: "channel", Chaincode: "tradecred", Identities: []IdentityConfig{entry}}
	raw, _ := json.Marshal(valid)
	for _, input := range []string{`{}`, `{"unknown":true}`, string(raw) + ` {}`, strings.Replace(string(raw), `"network"`, `""`, 1)} {
		if err := os.WriteFile(path, []byte(input), 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := loadConfig(path); err == nil {
			t.Fatal("invalid config accepted")
		}
	}
	if err := os.WriteFile(path, raw, 0600); err != nil {
		t.Fatal(err)
	}
	loaded, err := loadConfig(path)
	if err != nil {
		t.Fatal(err)
	}
	if checkFiles(loaded) == nil {
		t.Fatal("missing credentials accepted")
	}
	invoker := &fabricInvoker{config: loaded}
	if _, err := invoker.Invoke(context.Background(), Request{OrgID: "OTHER", Role: "EXPORTER"}, true); err == nil {
		t.Fatal("unknown identity accepted")
	}
	if _, err := invoker.Invoke(context.Background(), Request{OrgID: "ORG", Role: "EXPORTER"}, true); err == nil {
		t.Fatal("missing credentials accepted by SDK adapter")
	}
	valid.Identities = append(valid.Identities, entry)
	raw, _ = json.Marshal(valid)
	if err := os.WriteFile(path, raw, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := loadConfig(path); err == nil {
		t.Fatal("duplicate identity accepted")
	}
}
