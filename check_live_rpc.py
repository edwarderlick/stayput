import requests
url = "https://studio-dev.genlayer.com/api"

payload = {
    "jsonrpc": "2.0",
    "method": "gen_getTransaction",
    "params": ["0xa17721c9ec2f8540f7172aa4beb71b1156ed6eed7d49aef9fddada7d30448fa6"],
    "id": 1
}

response = requests.post(url, json=payload)
print("gen_getTransaction:", response.json())
