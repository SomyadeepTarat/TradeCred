package main

import (
	"encoding/json"
	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

type OperationReceipt struct {
	Replayed    bool   `json:"replayed"`
	RequestHash string `json:"requestHash"`
	ActorOrgID  string `json:"actorOrgId"`
	ActorRole   string `json:"actorRole"`
	Asset       *Asset `json:"asset"`
}

// Execute records a committed business-operation receipt in the same Fabric transaction.
// Concurrent retries read/write the same key and are subject to normal MVCC validation.
func (c *TradeCredContract) Execute(ctx contractapi.TransactionContextInterface, operationID, method, arguments string) (*OperationReceipt, error) {
	org, role, err := identity(ctx)
	if err != nil {
		return nil, err
	}
	if !digestPattern.MatchString(operationID) {
		return nil, failure("INVALID_OPERATION_ID")
	}
	var args []string
	if len(arguments) > 16384 || json.Unmarshal([]byte(arguments), &args) != nil {
		return nil, failure("INVALID_INPUT")
	}
	transient, err := ctx.GetStub().GetTransient()
	if err != nil {
		return nil, err
	}
	raw, err := json.Marshal(struct {
		Method    string
		Arguments []string
		Transient map[string][]byte
	}{method, args, transient})
	if err != nil {
		return nil, err
	}
	hash := digest(raw)
	saved, err := ctx.GetStub().GetState("operation:" + operationID)
	if err != nil {
		return nil, err
	}
	if saved != nil {
		var receipt OperationReceipt
		if json.Unmarshal(saved, &receipt) != nil {
			return nil, failure("CORRUPT_LEDGER_STATE")
		}
		if receipt.ActorOrgID != org || receipt.ActorRole != role || receipt.RequestHash != hash {
			return nil, failure("OPERATION_CONFLICT")
		}
		receipt.Replayed = true
		return &receipt, nil
	}
	var asset *Asset
	if method == "LockReceivable" && len(args) == 3 {
		asset, err = c.LockReceivable(ctx, args[0], args[1], args[2])
	} else if len(args) == 1 {
		switch method {
		case "VerifyReceivable":
			asset, err = c.VerifyReceivable(ctx, args[0])
		case "RegisterReceivable":
			asset, err = c.RegisterReceivable(ctx, args[0])
		case "OpenForFinancing":
			asset, err = c.OpenForFinancing(ctx, args[0])
		case "RecordFinancing":
			asset, err = c.RecordFinancing(ctx, args[0])
		case "ReleaseLock":
			asset, err = c.ReleaseLock(ctx, args[0])
		case "ConfirmPayment":
			asset, err = c.ConfirmPayment(ctx, args[0])
		case "MarkRealized":
			asset, err = c.MarkRealized(ctx, args[0])
		case "MarkEbrcEligible":
			asset, err = c.MarkEbrcEligible(ctx, args[0])
		case "CloseReceivable":
			asset, err = c.CloseReceivable(ctx, args[0])
		case "RaiseDispute":
			asset, err = c.RaiseDispute(ctx, args[0])
		case "MarkOverdue":
			asset, err = c.MarkOverdue(ctx, args[0])
		default:
			return nil, failure("INVALID_OPERATION")
		}
	} else {
		return nil, failure("INVALID_OPERATION")
	}
	if err != nil {
		return nil, err
	}
	receipt := &OperationReceipt{RequestHash: hash, ActorOrgID: org, ActorRole: role, Asset: asset}
	encoded, err := json.Marshal(receipt)
	if err != nil {
		return nil, err
	}
	if err := ctx.GetStub().PutState("operation:"+operationID, encoded); err != nil {
		return nil, err
	}
	return receipt, nil
}

func (c *TradeCredContract) GetOperationReceipt(ctx contractapi.TransactionContextInterface, operationID string) (*OperationReceipt, error) {
	org, role, err := identity(ctx)
	if err != nil {
		return nil, err
	}
	if !digestPattern.MatchString(operationID) {
		return nil, failure("INVALID_OPERATION_ID")
	}
	raw, err := ctx.GetStub().GetState("operation:" + operationID)
	if err != nil {
		return nil, err
	}
	if raw == nil {
		return nil, failure("OPERATION_NOT_FOUND")
	}
	var receipt OperationReceipt
	if json.Unmarshal(raw, &receipt) != nil {
		return nil, failure("CORRUPT_LEDGER_STATE")
	}
	if receipt.ActorOrgID != org || receipt.ActorRole != role {
		return nil, failure("UNAUTHORIZED_ROLE")
	}
	return &receipt, nil
}
