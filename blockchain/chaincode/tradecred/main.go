package main

import (
	"log"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

func newChaincode() (*contractapi.ContractChaincode, error) {
	return contractapi.NewChaincode(&TradeCredContract{})
}

func main() {
	cc, err := newChaincode()
	if err != nil {
		log.Fatal(err)
	}
	if err := cc.Start(); err != nil {
		log.Fatal(err)
	}
}
