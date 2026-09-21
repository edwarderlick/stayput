# AGENT_LOG.md - StayPut

StayPut-only build log. APIs browsed, fixtures used, test results, deploy hashes.

---

## API Sources (browsed live)

| Source | URL |
|--------|-----|
| GenLayer docs - networks | https://docs.genlayer.com/developers/networks.md |
| GenLayer docs - genlayer-test | https://docs.genlayer.com/api-references/genlayer-test.md |
| GenLayer docs - writing contracts | https://docs.genlayer.com/developers/intelligent-contracts/writing-contracts.md |
| GenLayer docs - gl.nondet | https://docs.genlayer.com/api-references/genvm/nondet.md |
| GenLayer docs - storage types | https://docs.genlayer.com/api-references/genvm/storage.md |
| GenLayer docs - gl.vm | https://docs.genlayer.com/api-references/genvm/vm.md |

---

## Network

| Item | Value |
|------|-------|
| Studio-dev RPC | https://studio-dev.genlayer.com/api |
| Chain ID | 61997 |
| Explorer | https://explorer-studio-dev.genlayer.com/?chain=studio-devnet |

---

## Build Steps

| Step | Status | Notes |
|------|--------|-------|
| Repo tree | OK | contracts/, test/, scripts/, deploy/ |
| API research | OK | Browsed live docs above |
| stayput.py | OK | 636 lines - constructor, fund, cancel, resolve, expire, withdraw, views |
| genvm-lint | OK | E106 fix applied - storage str fields coerced before nondet closures |
| Direct tests | OK | 34/34 passed |
| Studio-dev deploy | OK | 0xC49BE22b71A430a1d3FBBFf1Eb880292D74ec1D1 |
| README | OK | Full rewrite with verified explorer links |
| Direct Tests | OK | 34 / 34 passed (mock network) |
| GitHub push | OK | https://github.com/edwarderlick/stayput |

---

## Studio-Dev (61997) Smoke Deploy v2 (E106-fixed)

| Detail | Value |
|---|---|
| Contract | 0xC49BE22b71A430a1d3FBBFf1Eb880292D74ec1D1 |
| Deploy tx | 0xc521671e2d587faf5dc383a5b725d829fe198be1437dec128c8ce0ad8a1ccb09 |
| Deployer | 0xA1F567B94C5FA8b370C7040a194e8F4351242283 |
| Buyer (smoke) | 0x000000000000000000000000000000000000dEaD |
| Explorer link | https://explorer-studio-dev.genlayer.com/address/0xC49BE22b71A430a1d3FBBFf1Eb880292D74ec1D1?chain=studio-devnet |
| TX link | https://explorer-studio-dev.genlayer.com/transactions/0xc521671e2d587faf5dc383a5b725d829fe198be1437dec128c8ce0ad8a1ccb09?chain=studio-devnet |

## Studio-Dev (61997) Smoke Deploy v1 (superseded)

| Detail | Value |
|---|---|
| Contract | 0x3385d9B1D1166A870C557BA1049b40C059c560eE |
| Deploy tx | 0x376ef83721cf2f834c909b3c9482c6d52062943d4919707b0a76536ae47e6e2a |
| Deployer | 0xA1F567B94C5FA8b370C7040a194e8F4351242283 |
| Buyer (smoke) | 0x000000000000000000000000000000000000dEaD |
| Explorer link | https://explorer-studio-dev.genlayer.com/address/0x3385d9B1D1166A870C557BA1049b40C059c560eE?chain=studio-devnet |
| TX link | https://explorer-studio-dev.genlayer.com/transactions/0x376ef83721cf2f834c909b3c9482c6d52062943d4919707b0a76536ae47e6e2a?chain=studio-devnet |

> Smoke deploy uses 0xdEaD as buyer (satisfies buyer != seller). Escrow not funded. For a real
> hold, deploy fresh with an actual buyer EOA and call fund_escrow().

---

## Direct Test Results (2026-09-14)

```
pytest test/test_stayput_direct.py -v
34 passed in ~2.00s
```

### Test cases (34 total)

| Class | Tests |
|-------|-------|
| TestConstructorValidation | 8 - buyer==seller, non-https snap/live, empty/whitespace rubric, cancel>=hold, oversize URL/rubric |
| TestFundEscrow | 3 - non-buyer reverts, zero value reverts, fund sets status+timestamps |
| TestCancel | 4 - seller cancel unfunded, non-seller reverts, buyer cancel in window refunds, buyer cancel after window reverts |
| TestResolveGate | 1 - resolve before hold reverts |
| TestResolveVerdicts | 4 - UNCHANGED pays seller, COSMETIC pays seller, MATERIAL_CHANGE refunds buyer, FETCH_FAILED refunds buyer |
| TestDoubleResolve | 1 - second resolve reverts, deposit unchanged |
| TestResolveDeadlineGate | 3 - UNCHANGED reverts after deadline, expire() refunds buyer after deadline, UNCHANGED pays seller inside window |
| TestFrozenSnapshot | 4 - Fund stores body/hash, 404 reverts at fund, snapshot mutation ignored by resolve, live match against new snapshot refunds buyer |
| TestExpire | 2 - expire before deadline reverts, expire after deadline refunds buyer |
| TestSettlementAmounts | 2 - seller payout == deposit, buyer payout == deposit |
| TestWithdraw | 2 - no credit reverts, get_credit returns 0 for unknown |

---

## Fixtures

| Label | URL | Purpose |
|-------|-----|---------|
| KEEP | https://en.wikipedia.org/wiki/Escrow | Stable page - integration UNCHANGED fixture |
| FAIL | https://httpstat.us/404 | Returns 404 - integration FETCH_FAILED fixture |
| SNAP mock | 200-char in-memory body | Direct test snapshot |
| LIVE mock | Varied in-memory body | Direct test - produces all 4 verdicts via mock_llm |

---

## Harness Quirk (gltest v0.29.2)

`VMContext.warp()` updates `vm._datetime` but `_refresh_gl_message()` does NOT update
`gl.message_raw["datetime"]`. The contract's `_now()` reads `gl.message_raw["datetime"]`,
so time-advance in direct tests requires patching that key directly.

Fix applied in `_advance()` helper in `test/test_stayput_direct.py`:
```python
if "genlayer.gl" in sys.modules:
    gl_mod = sys.modules["genlayer.gl"]
    if hasattr(gl_mod, "message_raw") and gl_mod.message_raw is not None:
        gl_mod.message_raw["datetime"] = new_dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
```

This is a test-harness workaround, not a contract bug.

---

## Live Resolve Status

Not run live. The hold on the smoke deploy used `0xdEaD` as buyer so `fund_escrow()` cannot
be called (no private key). All four verdict paths are proven via direct tests with mocked
web + LLM. Integration test suite is in `test/test_stayput_integration.py` and ready to run
against a funded Studio-Devnet account.
