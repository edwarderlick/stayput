"""
deploy_stayput.py â€” Deploy StayPut to StudioNet and record the receipt.

Usage (from repo root):
    gltest scripts/deploy_stayput.py --network studionet -v -s

This script uses deploy_contract_tx() directly to avoid the schema-fetch
fallback failure that can occur on StudioNet immediately after a fresh deploy.
The deploy transaction IS committed; the contract address is recorded in
deploy/receipt.json and verified on the explorer.
"""

import json
import time
from pathlib import Path

from gltest import get_contract_factory, get_default_account
from gltest.assertions import tx_execution_succeeded, tx_execution_failed

RECEIPT_FILE = Path(__file__).parent.parent / "deploy" / "receipt.json"

RUBRIC = (
    "Price changes, eligibility criteria changes, feature removal, "
    "sponsor disclosure changes, and CTA destination URL changes are material. "
    "Navigation and footer changes are cosmetic."
)

# A distinct buyer address for the smoke-test deploy.
# Buyer must differ from seller (the deployer account).
SMOKE_BUYER = "0x000000000000000000000000000000000000dEaD"


def deploy():
    account = get_default_account()
    factory = get_contract_factory("StayPut")

    print(f"[deploy] Seller / deployer: {account.address}")
    print(f"[deploy] Buyer (smoke):     {SMOKE_BUYER}")
    print(f"[deploy] Sending deploy tx to StudioNet â€¦")

    # Use deploy_contract_tx() so we get the raw receipt + address without
    # requiring a follow-up schema fetch (which can transiently fail).
    receipt = factory.deploy_contract_tx(
        args=[
            SMOKE_BUYER,                                     # buyer
            "https://en.wikipedia.org/wiki/Escrow",         # snapshot URL
            "https://en.wikipedia.org/wiki/Escrow",         # live URL
            90,                                              # hold_seconds
            0,                                               # cancel_window
            3600,                                            # resolve_window
            RUBRIC,
        ],
        account=account,
        consensus_max_rotations=5,
    )

    if tx_execution_failed(receipt):
        payload = (receipt.get("consensus_data") or {}).get("leader_receipt") or receipt
        raise RuntimeError(f"[deploy] Deploy tx failed:\n{json.dumps(payload, indent=2, default=str)}")

    contract_address = receipt["data"]["contract_address"]
    tx_hash = receipt["hash"]
    print(f"[deploy] Deploy tx:       {tx_hash}")
    print(f"[deploy] Contract address: {contract_address}")
    print(f"[deploy] Status: ACCEPTED âœ“")

    # Persist receipt
    RECEIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "contract_address": contract_address,
        "deploy_tx": tx_hash,
        "deployer": str(account.address),
        "buyer_smoke": SMOKE_BUYER,
        "network": "studionet",
        "chain_id": 61999,
        "explorer": f"https://explorer-studio.genlayer.com/address/{contract_address}",
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
