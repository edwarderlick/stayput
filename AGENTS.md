# AGENTS.md - StayPut

This repository contains **StayPut**, a standalone GenLayer Intelligent Contract for live-page hold escrow.

## What Agents Should Know

StayPut is a single-contract, single-hold primitive. Each deployment escrows one page comparison.

### Repo Layout

```
D:\StayPut
├── contracts/
│   └── stayput.py           # The Intelligent Contract (Python, GenVM)
├── test/
│   ├── test_stayput_direct.py      # Direct-mode (in-memory) tests
│   └── test_stayput_integration.py # Studio-Devnet integration tests
├── deploy/                  # Deploy artifacts and receipts
├── gltest.config.yaml       # genlayer-test network config
├── requirements.txt         # Python dependencies
├── pytest.ini               # pytest configuration
├── .gitignore
├── README.md
├── AGENT_LOG.md             # Build log (this session)
└── AGENTS.md                # This file
```

### Contract Summary

- Seller deploys; sets buyer, snapshot URL, live URL, hold period, cancel window, resolve window, material rubric.
- Buyer calls `fund_escrow()` (payable) to lock GEN.
- After hold elapses, anyone calls `resolve()` - validators independently fetch the live page, compare against frozen snapshot, call LLM, return one of: `UNCHANGED | COSMETIC | MATERIAL_CHANGE | FETCH_FAILED`.
- Payout is 100% atomic: UNCHANGED/COSMETIC -> seller; MATERIAL_CHANGE/FETCH_FAILED -> buyer.
- `expire()` lets buyer reclaim funds if no resolver shows up before `resolve_deadline`.

### Key Constraints for Agents

3. **LLM never emits wei** - only the enum flows out of the nondet block.
4. **Credits fallback** - if `emit_transfer` to an EOA fails, credits[addr] is incremented and `withdraw()` is available.
5. **Constructors are NOT payable** - deploy then call `fund_escrow()`.
6. **Timestamps via** `gl.message_raw["datetime"]` converted to Unix seconds.
7. **Status enum**: `AWAITING_ESCROW | FUNDED | SETTLED | CANCELLED | EXPIRED`.

### Network

- **Studio-Devnet**: `https://studio-dev.genlayer.com/api`, chain 61997
- **Explorer**: `https://explorer-studio-dev.genlayer.com`

### Test Commands

```bash
# Install deps
pip install -r requirements.txt

# Direct tests (fast, in-memory, no network)
pytest test/test_stayput_direct.py -v

# Integration tests (requires Studio-Devnet)
gltest test/test_stayput_integration.py --network studio_devnet -v -s
```

### DO NOT

- Do not push to GitHub or create a remote.
- Do not build a frontend.
- Do not reference other contract names in code, tests, or docs.
- Do not weaken money assertions in tests.
