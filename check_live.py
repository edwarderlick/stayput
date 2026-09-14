import json
from genlayer_py.client import GenLayerClient

client = GenLayerClient("https://studio-dev.genlayer.com/api")

try:
    tx_hash = "0xa17721c9ec2f8540f7172aa4beb71b1156ed6eed7d49aef9fddada7d30448fa6"
    receipt = client.get_transaction(tx_hash)
    print(f"Receipt for tx {tx_hash}:")
    print(receipt)
except Exception as e:
    print(f"Error fetching tx {tx_hash}: {e}")

try:
    contract_addr = "0x3C2d872e35003f009960B5b481DE6bB9853b2a5B"
    state = client.get_contract_state(contract_addr)
    print(f"State for contract {contract_addr}:")
    print(state)
except Exception as e:
    print(f"Error fetching contract {contract_addr}: {e}")
