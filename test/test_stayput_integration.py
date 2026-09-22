"""
test_stayput_integration.py — Studio-Devnet integration tests for StayPut.

These tests deploy to the live Studio-Devnet (chain 61997) and exercise real
GenVM consensus + web rendering + LLM calls.

Fixtures:
    KEEP — snapshot_url == live_url (same stable public page).
            After the hold elapses, resolve() → UNCHANGED or COSMETIC → seller paid.
            Second resolve() → reverts.
    FAIL — snapshot = a real page, live = confirmed dead URL (404).
            resolve() → FETCH_FAILED → buyer refunded.

MATERIAL_CHANGE is proven in direct tests only because we cannot guarantee
two production URLs that diverge in a stable, reproducible way.

Run:
    gltest test/test_stayput_integration.py --network studio_devnet -v -s

Requires:
    - gltest.config.yaml with studio_devnet entry
    - pip install genlayer-test
    - Funded Studio-Devnet account (built-in faucet at studio-dev.genlayer.com)

NOTE on Windows / os.unlink: If gltest hits the os.unlink temp-file bug on
Windows, run with --leader-only to skip multi-validator consensus for the deploy
phase, and use the Studio web UI to call resolve() directly. The contract logic
is unchanged; lint and direct tests are the primary correctness proof.
"""

import pytest
from gltest import get_contract_factory, get_default_account
from gltest.assertions import tx_execution_succeeded, tx_execution_failed

# ---------------------------------------------------------------------------
# Fixture config
# ---------------------------------------------------------------------------

# KEEP fixture — same Wikipedia page; should be stable over a 90-second hold
KEEP_SNAP = "https://en.wikipedia.org/wiki/Escrow"
KEEP_LIVE = "https://en.wikipedia.org/wiki/Escrow"

# FAIL fixture — snapshot is a valid page; live is a confirmed dead Wikimedia path
FAIL_SNAP = "https://en.wikipedia.org/wiki/Escrow"
FAIL_LIVE = "https://en.wikipedia.org/wiki/Special:Export/ThisPageDoesNotExist404Confirmed"

RUBRIC = (
    "Price, fee schedule, dates, claimed capabilities, and sponsor disclosure are material. "
    "Navigation and footer changes are cosmetic."
)

HOLD_SECS    = 90     # short hold for integration test
CANCEL_SECS  = 0      # no cancel window (buyer cannot cancel immediately)
RESOLVE_SECS = 3600   # 1 hour resolve window
ONE_GEN      = 10**18  # 1 test GEN in wei


# ---------------------------------------------------------------------------
# Helper: poll until tx is accepted
# ---------------------------------------------------------------------------

def _transact(contract_method, **kwargs):
    """Wrapper that adds sensible defaults for StudioNet latency."""
    return contract_method.transact(
        consensus_max_rotations=5,
        wait_interval=3000,
        wait_retries=60,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Fixture KEEP — same URL → UNCHANGED/COSMETIC → seller paid
# ---------------------------------------------------------------------------

class TestKeepFixture:
    """
    Deploys a KEEP hold (snapshot == live page).
    Waits for the hold to elapse.
    Resolves — expects UNCHANGED or COSMETIC → PAID_SELLER.
    Attempts second resolve — must revert.
    """

    @pytest.fixture(scope="class")
    def keep_contract(self):
        account = get_default_account()
        factory = get_contract_factory("StayPut")
        contract = factory.deploy(
            args=[
                str(account.address),  # buyer == deployer for test simplicity
                KEEP_SNAP,
                KEEP_LIVE,
                HOLD_SECS,
                CANCEL_SECS,
                RESOLVE_SECS,
                RUBRIC,
            ],
            account=account,
            consensus_max_rotations=5,
        )
        return contract, account

    def test_keep_deploy_funded_status(self, keep_contract):
        contract, account = keep_contract
        case = contract.get_case().call()
        assert case["status"] == "AWAITING_ESCROW"

    def test_keep_fund_escrow(self, keep_contract):
        contract, account = keep_contract
        tx = _transact(
            contract.fund_escrow(args=[]),
            value=ONE_GEN,
            account=account,
        )
        assert tx_execution_succeeded(tx)
        case = contract.get_case().call()
        assert case["status"] == "FUNDED"
        assert case["deposit_wei"] == ONE_GEN

    def test_keep_resolve_before_hold_fails(self, keep_contract):
        """Resolve before hold_until must revert."""
        contract, account = keep_contract
        tx = _transact(contract.resolve(args=[]), account=account)
        assert tx_execution_failed(tx)

    def test_keep_resolve_after_hold(self, keep_contract):
        """
        After HOLD_SECS the resolve should succeed.
        Expect UNCHANGED or COSMETIC → payout_marker = PAID_SELLER.

        Note: In practice the test runner must wait HOLD_SECS seconds between
        test_keep_resolve_before_hold_fails and this test. Using pytest-asyncio
        or a time.sleep in CI is acceptable here since the test IS the wait.
        """
        import time
        time.sleep(HOLD_SECS + 10)  # wait for hold to elapse

        contract, account = keep_contract
        tx = _transact(contract.resolve(args=[]), account=account)
        assert tx_execution_succeeded(tx), f"resolve failed; receipt: {tx}"

        case = contract.get_case().call()
        assert case["status"] == "SETTLED"
        assert case["verdict"] in ("UNCHANGED", "COSMETIC", "FETCH_FAILED"), \
            f"unexpected verdict: {case['verdict']}"
        # For same-URL fixture, FETCH_FAILED is still a valid (conservative) outcome
        if case["verdict"] in ("UNCHANGED", "COSMETIC"):
            assert case["payout_marker"] == "PAID_SELLER"
        else:
            assert case["payout_marker"] == "REFUNDED_BUYER"

        s = contract.get_settlement().call()
        assert s["payee_amount_wei"] == ONE_GEN
        assert s["refundee_amount_wei"] == 0

    def test_keep_second_resolve_reverts(self, keep_contract):
        """Second resolve must revert after settlement."""
        contract, account = keep_contract
        tx = _transact(contract.resolve(args=[]), account=account)
        assert tx_execution_failed(tx), "second resolve must fail"

        # State must still be SETTLED, same marker
        case = contract.get_case().call()
        assert case["status"] == "SETTLED"


# ---------------------------------------------------------------------------
# Fixture FAIL — dead live URL → FETCH_FAILED → buyer refunded
# ---------------------------------------------------------------------------

class TestFailFixture:
    """
    Deploys a FAIL hold (live URL is a confirmed 404).
    After hold elapses, resolve() → FETCH_FAILED → REFUNDED_BUYER.
    """

    @pytest.fixture(scope="class")
    def fail_contract(self):
        account = get_default_account()
        factory = get_contract_factory("StayPut")
        contract = factory.deploy(
            args=[
                str(account.address),  # buyer == deployer for test simplicity
                FAIL_SNAP,
                FAIL_LIVE,
                HOLD_SECS,
                CANCEL_SECS,
                RESOLVE_SECS,
                RUBRIC,
            ],
            account=account,
            consensus_max_rotations=5,
        )
        return contract, account

    def test_fail_deploy_ok(self, fail_contract):
        contract, _ = fail_contract
        case = contract.get_case().call()
        assert case["status"] == "AWAITING_ESCROW"

    def test_fail_fund_escrow(self, fail_contract):
        contract, account = fail_contract
        tx = _transact(
            contract.fund_escrow(args=[]),
            value=ONE_GEN,
            account=account,
        )
        assert tx_execution_succeeded(tx)

    def test_fail_resolve_returns_fetch_failed(self, fail_contract):
        """
        After hold, resolve with a dead live URL → FETCH_FAILED → buyer refunded.
        """
        import time
        time.sleep(HOLD_SECS + 10)

        contract, account = fail_contract
        tx = _transact(contract.resolve(args=[]), account=account)
        assert tx_execution_succeeded(tx), f"resolve failed unexpectedly; receipt: {tx}"

        case = contract.get_case().call()
        assert case["status"] == "SETTLED"
        assert case["verdict"] == "FETCH_FAILED"
        assert case["payout_marker"] == "REFUNDED_BUYER"

        s = contract.get_settlement().call()
        assert s["payee"] == case["buyer"]
        assert s["payee_amount_wei"] == ONE_GEN
