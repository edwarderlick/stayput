"""
deploy_stayput.py - Deploy StayPut to Studio-Devnet and record the receipt.

Usage (from repo root):
    gltest scripts/deploy_stayput.py --network studio_devnet -v -s
"""

import json
from pathlib import Path
from gltest import get_contract_factory
from gltest.assertions import tx_execution_failed

RECEIPT_FILE = Path(__file__).parent.parent / "deploy" / "receipt.json"

SMOKE_BUYER = "0x000000000000000000000000000000000000dEaD"

def deploy():
    import os
    import time
    from eth_account import Account
    key = os.environ.get("PRIVATE_KEY")
    if not key:
        raise ValueError("PRIVATE_KEY environment variable is not set")
    account = Account.from_key(key)
    factory = get_contract_factory("StayPut")

    print(f"[deploy] Seller / deployer: {account.address}")
    print(f"[deploy] Buyer (smoke):     {SMOKE_BUYER}")
    print(f"[deploy] Sending deploy tx to Studio-Devnet ...")

    receipt = factory.deploy_contract_tx(
        args=[SMOKE_BUYER, "https://example.com/snap", "https://example.com/live", 86400, 3600, 604800, "Must be substantially the same content."],
        account=account,
        fees={
            "distribution": {
                "leaderTimeunitsAllocation": 100,
                "validatorTimeunitsAllocation": 200,
                "appealRounds": 0,
                "executionBudgetPerRound": 100000000000000000,
                "executionConsumed": 0,
                "totalMessageFees": 0,
                "rotations": [3],
                "maxPriceGenPerTimeUnit": 2,
                "storageFeeMaxGasPrice": 300000000,
                "receiptFeeMaxGasPrice": 300000000
            }
        },
        fee_value=500000000000010352,
    )

    if tx_execution_failed(receipt):
        payload = (receipt.get("consensus_data") or {}).get("leader_receipt") or receipt
        raise RuntimeError(f"[deploy] Deploy tx failed:\n{json.dumps(payload, indent=2, default=str)}")

    contract_address = receipt["data"]["contract_address"]
    tx_hash = receipt["hash"]
    print(f"[deploy] Deploy tx:       {tx_hash}")
    print(f"[deploy] Contract address: {contract_address}")
    print(f"[deploy] Status: ACCEPTED âœ“")

    # Give it a small sleep to allow consensus to process
    time.sleep(30)

    # Persist receipt
    RECEIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "contract_address": contract_address,
        "deploy_tx": tx_hash,
        "deployer": str(account.address),
        "buyer_smoke": SMOKE_BUYER,
        "network": "studio_devnet",
        "chain_id": 61997,
        "explorer": f"https://explorer-studio-dev.genlayer.com/address/{contract_address}?chain=studio-devnet",
        "note": (
            "Smoke deploy only â€” buyer is the dead address. "
            "For a real hold, deploy fresh with the actual buyer address and call fund_escrow()."
        ),
    }
    RECEIPT_FILE.write_text(json.dumps(output, indent=2))
    print(f"[deploy] Receipt saved â†’ {RECEIPT_FILE}")
    print(f"[deploy] Explorer: {output['explorer']}")
    print(f"[deploy] Done.")
    return contract_address

def test_smoke_deploy():
    """pytest entry point â€” called by gltest."""
    addr = deploy()
    assert addr.startswith("0x"), f"expected 0x-prefixed address, got: {addr}"
    print(f"[deploy] âœ“  StayPut live at {addr}")
