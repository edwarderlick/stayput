import json
import urllib.request

def run_gate():
    code = open('contracts/stayput.py', 'rb').read()
    req = urllib.request.Request(
        "https://studio-dev.genlayer.com/api",
        data=json.dumps({
            "jsonrpc": "2.0",
            "method": "gen_getContractSchemaForCode",
            "params": ["0x" + code.hex()],
            "id": 1
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "curl/7.68.0"
        }
    )
    r = json.load(urllib.request.urlopen(req))
    
    assert "result" in r, f"Schema validation failed: {r.get('error', {}).get('message', str(r))[:600]}"
    
    print("SEMANTIC VALIDATION PASSED")
    print(json.dumps(r["result"]["ctor"], indent=1))

if __name__ == "__main__":
    run_gate()
