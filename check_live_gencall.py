import requests
url = "https://studio-dev.genlayer.com/api"
payload = {
    "jsonrpc": "2.0",
    "method": "gen_call",
    "params": [{
        "to": "0x1e080064845f404c0CB22D6ce3329c8C3Ba1d2BB",
        "data": [1] # Should return an error about 'type' or method not found if it exists, not 404
    }],
    "id": 1
}
response = requests.post(url, json=payload)
print("gen_call:", response.json())
