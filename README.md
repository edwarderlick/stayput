# StayPut

Escrow that pays the seller if a live public page stays equivalent to an approved snapshot, and refunds the buyer if the page materially changes or cannot be fetched.

Built on [GenLayer](https://genlayer.com) Studio-Devnet. Uses test GEN. Not a court, judge, or legal ruling.

---

## What it does

Seller deploys with:
- a snapshot URL (the reference state),
- a live URL (checked at resolution time),
- a hold length (how long before anyone may resolve),
- a cancel window (how long the buyer may back out after funding),
- a short material rubric (what counts as material for *this* hold).

Buyer funds the escrow with GEN. At funding time, the contract fetches and freezes the reference snapshot. After the hold elapses, anyone calls `resolve()`. Validators independently fetch the live page as plain text, compare it against the frozen snapshot, and agree on one enum:

```
UNCHANGED | COSMETIC | MATERIAL_CHANGE | FETCH_FAILED
```

The whole pot moves atomically from that verdict. The model never emits wei.

---

## What it is not

- Not a bounty grader - there is no deliverable, no milestone.
- Not a photo deposit - it compares live page text, not images.
- Not an ad-disclosure checker - though you can write a rubric that makes ad changes material.

---

## State machine

```
AWAITING_ESCROW ──fund_escrow()──► FUNDED ──resolve()──► SETTLED
                                     │
                         cancel() ───┤──► CANCELLED
                                     │
                         expire()  ──┴──► EXPIRED
```

**Cancel rules (from `stayput.py`):**
- Seller may cancel any time while `AWAITING_ESCROW` (no funds to return).
- Buyer may cancel while `FUNDED` and within `cancel_window_seconds` of `fund_ts`.
- After the cancel window, only `resolve()` or `expire()` can move the state.

**Resolve / expire rules:**
- `resolve()` is permissionless; requires `FUNDED` + hold elapsed + no payout yet.
- `expire()` is permissionless; requires `FUNDED` + resolve deadline elapsed.

---

## Methods

| Method | Callable by | Payable | When |
|--------|-------------|---------|------|
| `__init__(buyer, snapshot_url, live_url, hold_seconds, cancel_window_seconds, resolve_window_seconds, material_rubric)` | Seller | No | Deploy |
| `fund_escrow()` | Buyer | **Yes** | `AWAITING_ESCROW` |
| `cancel()` | Seller (unfunded) or Buyer (within cancel window) | No | Before hold elapses |
| `resolve()` | Anyone | No | After hold, before resolve deadline |
| `expire()` | Anyone | No | After resolve deadline |
| `withdraw()` | Anyone with credits | No | After failed `emit_transfer` |
| `get_case()` | View | No | Any time |
| `get_settlement()` | View | No | Any time |
| `get_credit(addr)` | View | No | Any time |

---

## Economics

| Outcome | Seller gets | Buyer gets | `payout_marker` |
|---------|------------|------------|-----------------|
| `UNCHANGED` / `COSMETIC` | 100 % | 0 | `PAID_SELLER` |
| `MATERIAL_CHANGE` | 0 | 100 % | `REFUNDED_BUYER` |
| `FETCH_FAILED` | 0 | 100 % | `REFUNDED_BUYER` |
| Buyer cancels in window | 0 | 100 % | `REFUNDED_BUYER` |
| `expire()` after resolve window | 0 | 100 % | `REFUNDED_BUYER` |
| Seller cancels (unfunded) | - | - | `NONE` |

No splits. No averages. No retry payout. A second `resolve()` call reverts.

---

## Cosmetic vs material

**Cosmetic (seller wins):** navigation changes, whitespace, tracker parameters, minor wording that doesn't change meaning, footer edits.

**Material (buyer wins):** price changes, eligibility criteria, feature removal, sponsor or disclosure line changes, CTA or destination URL changes, promised asset or section gone.

The **constructor rubric is authoritative for that hold**. Parties agree in writing at deploy time what counts as material. Any instruction embedded in either page body is explicitly ignored by the prompt.

`FETCH_FAILED` always refunds the buyer - a deleted or captcha-gated page cannot pay the seller.

---

## Studio-dev

| Field | Value |
|-------|-------|
| Network | Studio-dev |
| RPC | `https://studio-dev.genlayer.com/api` |
| Chain ID | 61997 |
| Explorer | [explorer-studio-dev.genlayer.com](https://explorer-studio-dev.genlayer.com/?chain=studio-devnet) |
| Studio | [studio-dev.genlayer.com](https://studio-dev.genlayer.com) |
| Contract | [0xC49BE22b71A430a1d3FBBFf1Eb880292D74ec1D1](https://explorer-studio-dev.genlayer.com/address/0xC49BE22b71A430a1d3FBBFf1Eb880292D74ec1D1?chain=studio-devnet) |
| Deploy tx | [0xc521671e2d587faf5dc383a5b725d829fe198be1437dec128c8ce0ad8a1ccb09](https://explorer-studio-dev.genlayer.com/transactions/0xc521671e2d587faf5dc383a5b725d829fe198be1437dec128c8ce0ad8a1ccb09?chain=studio-devnet) |
| Consensus | 5 / 5 validators AGREE on deploy |
| Resolve tx | Not run live - lifecycle proven in 34 direct tests (see below) |
| Second resolve | Not run live - revert proven in `TestDoubleResolve` direct test |

> The smoke deploy used `0xdEaD` as buyer (buyer != seller constraint). For a real hold, deploy
> fresh with an actual buyer EOA and call `fund_escrow()`.

---

## Fixtures used in tests

| Label | URL | Role |
|-------|-----|------|
| KEEP | `https://en.wikipedia.org/wiki/Escrow` | Stable page; validators return `UNCHANGED` |
| FAIL | `https://httpstat.us/404` | Returns 404; validators return `FETCH_FAILED` |
| SNAP mock | In-memory mock body (direct tests) | 200 chars identical snapshot |
| LIVE mock | In-memory mock body (direct tests) | Varied to produce each verdict |

KEEP and FAIL fixtures are defined in `test/test_stayput_integration.py`.
All four verdicts are exercised via mocked LLM in the 27 direct tests.

---

## Two-step deploy

The constructor is **not payable** - it only records configuration.

```python
# Step 1: deploy (no value)
contract = factory.deploy(args=[buyer, snap_url, live_url, hold_s, cancel_s, resolve_s, rubric])

# Step 2: buyer funds
tx = contract.fund_escrow(args=[]).transact(value=deposit_wei, account=buyer_account)
```

`buyer` in the constructor must differ from the deployer (seller). `buyer` must not be the zero address.

---

## Tests

```bash
# Install
pip install genlayer-test

# Direct mode - fast, in-memory, no network required
pytest test/test_stayput_direct.py -v
# -> 34 passed

# Integration mode - requires funded Studio-Devnet account
gltest test/test_stayput_integration.py --network studio_devnet -v -s
```

**Result:** `34 passed` - all constructor validations, fund, cancel, resolve (all 4 verdicts), double-resolve revert, expire, settlement amounts, and withdraw.

**Harness quirk (not a contract bug):** `VMContext.warp()` in gltest v0.29.2 updates `vm._datetime` but does not propagate the new timestamp into `gl.message_raw["datetime"]`. The `_advance()` helper in the test file patches `gl.message_raw["datetime"]` directly as a workaround.

---

## Limits

- Test GEN only (Studio-Devnet). No mainnet.
- Public HTTPS URLs only; text-mode fetch, up to 8 000 characters per side.
- If `emit_transfer` to an EOA fails (e.g. IC->EOA transfer restriction), funds are credited to `credits[addr]` and claimable via `withdraw()`.
- URL length: 12-256 characters. Rubric: <= 500 characters.
- Hold: 60 s - 30 days. Cancel window: 0 - 24 h (must be < hold). Resolve window: 60 s - 30 days.

---

## Repo layout

```
contracts/stayput.py              Intelligent Contract
test/test_stayput_direct.py       34 direct tests (mock network)
test/test_stayput_integration.py  Studio-Devnet integration tests
scripts/deploy_stayput.py         Deploy script (Studio-Devnet)
deploy/receipt.json               On-chain deploy receipt
gltest.config.yaml                Network config
requirements.txt                  Python deps
pytest.ini                        Test config
AGENT_LOG.md                      Build log (APIs, fixtures, results)
AGENTS.md                         Agent instructions
```

---

## License

MIT
