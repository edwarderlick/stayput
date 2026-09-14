"""
test_stayput_direct.py â€” Direct-mode tests for StayPut.

All 17 required cases. Uses genlayer-test direct_vm / direct_deploy fixtures.
Mock web and LLM responses; no network required.

Run:
    pytest test/test_stayput_direct.py -v
"""
import datetime
import pytest

# ---------------------------------------------------------------------------
# Fixtures: stable test defaults
# ---------------------------------------------------------------------------

SNAP_URL = "https://example.com/snapshot-v1"
LIVE_URL = "https://example.com/live-page"
RUBRIC   = "Price changes, feature removal, and sponsor disclosure changes are material."

HOLD_SECS   = 120    # 2 minutes (tests manipulate time via mocks)
CANCEL_SECS = 60     # 1 minute cancel window
RESOLVE_SECS = 300   # 5 minute resolve window
DEPOSIT     = 10**18  # 1 GEN in wei

MOCK_SNAP_BODY = "A" * 200  # 200 chars â€” well above thin threshold
MOCK_LIVE_BODY = "A" * 200  # identical â†’ UNCHANGED expected

MOCK_LIVE_CHANGED = "B" * 200  # different â†’ MATERIAL_CHANGE expected

# Minimal mocked web response pattern for direct_vm.mock_web
def _mock_web(vm, snap_body: str, live_body: str) -> None:
    vm.mock_web(r"example\.com/snapshot", {"status": 200, "body": snap_body})
    vm.mock_web(r"example\.com/live",     {"status": 200, "body": live_body})


# ---------------------------------------------------------------------------
# Address helper: gltest fixtures return bytes; contracts need 0x hex strings
# ---------------------------------------------------------------------------

def _addr(b) -> str:
    """Convert bytes address from gltest fixture to 0x-prefixed hex string."""
    if isinstance(b, bytes):
        return "0x" + b.hex()
    # already a string or has __str__
    s = str(b)
    if not s.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in s):
        return "0x" + s
    return s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deploy_default(direct_deploy, direct_bob, direct_owner):
    """Deploy with seller=owner, buyer=bob."""
    return direct_deploy(
        "contracts/stayput.py",
        _addr(direct_bob),
        SNAP_URL,
        LIVE_URL,
        HOLD_SECS,
        CANCEL_SECS,
        RESOLVE_SECS,
        RUBRIC,
    )


def _fund(vm, contract, sender, amount=DEPOSIT, mock_snap_body=MOCK_SNAP_BODY):
    """Send value as sender and call fund_escrow.
    Mocks the snapshot URL fetch which now happens during fund."""
    if mock_snap_body is not None:
        vm.mock_web(r"example\.com/snapshot", {"status": 200, "body": mock_snap_body})
    vm.sender = sender
    vm.value = amount
    contract.fund_escrow()
    vm.value = 0  # reset after payable call


def _advance(vm, seconds: int) -> None:
    """Advance the VM clock by `seconds`.

    VMContext.warp() sets vm._datetime but _refresh_gl_message() only updates
    sender/value in message_raw. We must also patch message_raw['datetime']
    directly so the contract's _now() â†’ gl.message_raw['datetime'] sees the
    new time.
    """
    import sys
    current = datetime.datetime.fromisoformat(
        vm._datetime.replace("Z", "+00:00")
    )
    new_dt = current + datetime.timedelta(seconds=seconds)
    vm.warp(new_dt.isoformat())

    # Also patch the cached message_raw so the contract sees the updated time.
    if "genlayer.message" in sys.modules:
        msg_mod = sys.modules["genlayer.message"]
        if hasattr(msg_mod, "raw") and msg_mod.raw is not None:
            msg_mod.raw["datetime"] = new_dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"



# ---------------------------------------------------------------------------
# 1. Constructor rejects invalid inputs
# ---------------------------------------------------------------------------

class TestConstructorValidation:
    def test_buyer_equals_seller_reverts(self, direct_vm, direct_deploy, direct_owner):
        with direct_vm.expect_revert("buyer must differ from seller"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_owner),  # buyer == sender
                SNAP_URL, LIVE_URL,
                HOLD_SECS, CANCEL_SECS, RESOLVE_SECS, RUBRIC,
            )

    def test_non_https_snapshot_reverts(self, direct_vm, direct_deploy, direct_bob):
        with direct_vm.expect_revert("must start with https"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                "http://example.com/snapshot",  # http not https
                LIVE_URL, HOLD_SECS, CANCEL_SECS, RESOLVE_SECS, RUBRIC,
            )

    def test_non_https_live_reverts(self, direct_vm, direct_deploy, direct_bob):
        with direct_vm.expect_revert("must start with https"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                SNAP_URL,
                "http://example.com/live",  # http
                HOLD_SECS, CANCEL_SECS, RESOLVE_SECS, RUBRIC,
            )

    def test_empty_rubric_reverts(self, direct_vm, direct_deploy, direct_bob):
        with direct_vm.expect_revert("material_rubric must not be empty"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                SNAP_URL, LIVE_URL,
                HOLD_SECS, CANCEL_SECS, RESOLVE_SECS,
                "",  # empty rubric
            )

    def test_whitespace_only_rubric_reverts(self, direct_vm, direct_deploy, direct_bob):
        with direct_vm.expect_revert("material_rubric must not be empty"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                SNAP_URL, LIVE_URL,
                HOLD_SECS, CANCEL_SECS, RESOLVE_SECS,
                "   ",  # only whitespace
            )

    def test_cancel_window_gte_hold_reverts(self, direct_vm, direct_deploy, direct_bob):
        with direct_vm.expect_revert("cancel_window_seconds must be < hold_seconds"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                SNAP_URL, LIVE_URL,
                HOLD_SECS,
                HOLD_SECS,  # cancel_window == hold â†’ invalid
                RESOLVE_SECS, RUBRIC,
            )

    def test_oversize_url_reverts(self, direct_vm, direct_deploy, direct_bob):
        long_url = "https://example.com/" + "x" * 300  # > 256 chars
        with direct_vm.expect_revert("must be"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                long_url, LIVE_URL,
                HOLD_SECS, CANCEL_SECS, RESOLVE_SECS, RUBRIC,
            )

    def test_oversize_rubric_reverts(self, direct_vm, direct_deploy, direct_bob):
        big_rubric = "r" * 501  # > 500 chars
        with direct_vm.expect_revert("500"):
            direct_deploy(
                "contracts/stayput.py",
                _addr(direct_bob),
                SNAP_URL, LIVE_URL,
                HOLD_SECS, CANCEL_SECS, RESOLVE_SECS,
                big_rubric,
            )


# ---------------------------------------------------------------------------
# 2. Non-buyer fund reverts; zero value reverts
# ---------------------------------------------------------------------------

class TestFundEscrow:
    def test_non_buyer_fund_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob, direct_charlie):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        direct_vm.sender = direct_charlie
        direct_vm.value = DEPOSIT
        with direct_vm.expect_revert("only the buyer may fund the escrow"):
            contract.fund_escrow()

    def test_zero_value_fund_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        direct_vm.sender = direct_bob
        direct_vm.value = 0
        with direct_vm.expect_revert("value must be > 0"):
            contract.fund_escrow()

    def test_fund_sets_funded_and_timestamps(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        case = contract.get_case()
        assert case["status"] == "FUNDED"
        assert case["deposit_wei"] == DEPOSIT
        assert case["fund_ts"] > 0, "fund_ts must be set"
        assert case["hold_until_ts"] == case["fund_ts"] + HOLD_SECS
        assert case["resolve_deadline_ts"] == case["hold_until_ts"] + RESOLVE_SECS


# ---------------------------------------------------------------------------
# 3 & 4. Cancel logic
# ---------------------------------------------------------------------------

class TestCancel:
    def test_seller_cancel_unfunded(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        direct_vm.sender = direct_owner
        contract.cancel()
        case = contract.get_case()
        assert case["status"] == "CANCELLED"

    def test_non_seller_cancel_unfunded_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        direct_vm.sender = direct_bob
        with direct_vm.expect_revert("only seller may cancel"):
            contract.cancel()

    def test_buyer_cancel_inside_window_refunds(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        # Cancel while inside the cancel window (no time advance needed
        # since block is set to fund time; cancel_window is 60s)
        direct_vm.sender = direct_bob
        contract.cancel()

        case = contract.get_case()
        assert case["status"] == "CANCELLED"
        assert case["payout_marker"] == "REFUNDED_BUYER"

    def test_buyer_cancel_after_window_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        """After the cancel window, cancel must revert."""
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        # Advance time past the cancel window (60s) but still before hold_until (120s)
        _advance(direct_vm, 70)

        direct_vm.sender = direct_bob
        with direct_vm.expect_revert("cancel window has passed"):
            contract.cancel()


# ---------------------------------------------------------------------------
# 5. Resolve before hold_until reverts
# ---------------------------------------------------------------------------

class TestResolveGate:
    def test_resolve_before_hold_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        # No time advance â€” hold has not elapsed
        direct_vm.sender = direct_owner
        with direct_vm.expect_revert("hold period has not elapsed yet"):
            contract.resolve()


# ---------------------------------------------------------------------------
# 6â€“9. Resolve with various LLM verdicts
# ---------------------------------------------------------------------------

class TestResolveVerdicts:
    def _prepare_and_resolve(self, direct_vm, contract, snap_body, live_body, llm_verdict):
        """Advance past hold, mock web + LLM, call resolve."""
        _mock_web(direct_vm, snap_body, live_body)
        direct_vm.mock_llm(r".*", f'{{"verdict": "{llm_verdict}"}}'.encode("utf-8"))

        # Advance time past hold_until
        _advance(direct_vm, HOLD_SECS + 5)
        contract.resolve()

    def test_resolve_unchanged_pays_seller(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        self._prepare_and_resolve(direct_vm, contract, MOCK_SNAP_BODY, MOCK_LIVE_BODY, "UNCHANGED")

        case = contract.get_case()
        assert case["verdict"] == "UNCHANGED"
        assert case["payout_marker"] == "PAID_SELLER"
        assert case["status"] == "SETTLED"

        s = contract.get_settlement()
        assert s["payee"] == case["seller"]
        assert s["payee_amount_wei"] == DEPOSIT
        assert s["refundee_amount_wei"] == 0

    def test_resolve_cosmetic_pays_seller(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        self._prepare_and_resolve(direct_vm, contract, MOCK_SNAP_BODY, MOCK_LIVE_BODY, "COSMETIC")

        case = contract.get_case()
        assert case["verdict"] == "COSMETIC"
        assert case["payout_marker"] == "PAID_SELLER"
        s = contract.get_settlement()
        assert s["payee"] == case["seller"]
        assert s["payee_amount_wei"] == DEPOSIT

    def test_resolve_material_change_refunds_buyer(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        self._prepare_and_resolve(direct_vm, contract, MOCK_SNAP_BODY, MOCK_LIVE_CHANGED, "MATERIAL_CHANGE")

        case = contract.get_case()
        assert case["verdict"] == "MATERIAL_CHANGE"
        assert case["payout_marker"] == "REFUNDED_BUYER"
        s = contract.get_settlement()
        assert s["payee"] == case["buyer"]
        assert s["payee_amount_wei"] == DEPOSIT

    def test_resolve_fetch_failed_refunds_buyer(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        # LLM says FETCH_FAILED
        self._prepare_and_resolve(direct_vm, contract, MOCK_SNAP_BODY, MOCK_LIVE_BODY, "FETCH_FAILED")

        case = contract.get_case()
        assert case["verdict"] == "FETCH_FAILED"
        assert case["payout_marker"] == "REFUNDED_BUYER"
        s = contract.get_settlement()
        assert s["payee"] == case["buyer"]
        assert s["payee_amount_wei"] == DEPOSIT


# ---------------------------------------------------------------------------
# 10. Double-resolve reverts (critical money safety test)
# ---------------------------------------------------------------------------

class TestDoubleResolve:
    def test_second_resolve_reverts_and_wei_unchanged(
        self, direct_vm, direct_deploy, direct_owner, direct_bob
    ):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        _mock_web(direct_vm, MOCK_SNAP_BODY, MOCK_LIVE_BODY)
        direct_vm.mock_llm(r".*", b'{"verdict": "UNCHANGED"}')
        _advance(direct_vm, HOLD_SECS + 5)
        contract.resolve()

        # Record deposit before second attempt
        case_before = contract.get_case()
        deposit_before = case_before["deposit_wei"]

        # Second resolve must revert
        with direct_vm.expect_revert():
            contract.resolve()

        # State must be unchanged
        case_after = contract.get_case()
        assert case_after["deposit_wei"] == deposit_before
        assert case_after["payout_marker"] == "PAID_SELLER"
        assert case_after["status"] == "SETTLED"


# ---------------------------------------------------------------------------
# 11â€“12. Expire
# ---------------------------------------------------------------------------

class TestExpire:
    def test_expire_before_deadline_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        # Advance just past hold but not past resolve deadline
        _advance(direct_vm, HOLD_SECS + 5)
        with direct_vm.expect_revert("resolve deadline has not passed yet"):
            contract.expire()

    def test_expire_after_deadline_refunds_buyer(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)

        # Advance past full resolve deadline (HOLD + RESOLVE + buffer)
        _advance(direct_vm, HOLD_SECS + RESOLVE_SECS + 10)
        contract.expire()

        case = contract.get_case()
        assert case["status"] == "EXPIRED"
        assert case["payout_marker"] == "REFUNDED_BUYER"

        s = contract.get_settlement()
        assert s["payee"] == case["buyer"]
        assert s["payee_amount_wei"] == DEPOSIT


# ---------------------------------------------------------------------------
# 13. get_settlement amounts add up correctly
# ---------------------------------------------------------------------------

class TestSettlementAmounts:
    def test_seller_payout_amounts_match_deposit(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)
        _mock_web(direct_vm, MOCK_SNAP_BODY, MOCK_LIVE_BODY)
        direct_vm.mock_llm(r".*", b'{"verdict": "UNCHANGED"}')
        _advance(direct_vm, HOLD_SECS + 5)
        contract.resolve()

        case = contract.get_case()
        s = contract.get_settlement()
        assert s["payee_amount_wei"] == case["deposit_wei"]
        assert s["refundee_amount_wei"] == 0

    def test_buyer_payout_amounts_match_deposit(self, direct_vm, direct_deploy, direct_owner, direct_bob):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)
        _mock_web(direct_vm, MOCK_SNAP_BODY, MOCK_LIVE_BODY)
        direct_vm.mock_llm(r".*", b'{"verdict": "MATERIAL_CHANGE"}')
        _advance(direct_vm, HOLD_SECS + 5)
        contract.resolve()

        case = contract.get_case()
        s = contract.get_settlement()
        assert s["payee_amount_wei"] == case["deposit_wei"]
        assert s["refundee_amount_wei"] == 0


# ---------------------------------------------------------------------------
# 14. Withdraw with no credit reverts
# ---------------------------------------------------------------------------

class TestWithdraw:
    def test_withdraw_no_credit_reverts(self, direct_vm, direct_deploy, direct_owner, direct_bob, direct_charlie):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        direct_vm.sender = direct_charlie
        with direct_vm.expect_revert("no credits to withdraw"):
            contract.withdraw()

    def test_get_credit_returns_zero_for_unknown(self, direct_vm, direct_deploy, direct_owner, direct_bob, direct_charlie):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        credit = contract.get_credit(_addr(direct_charlie))
        assert credit == 0

# ---------------------------------------------------------------------------
# 10. Test Resolve Deadline Gate
# ---------------------------------------------------------------------------

class TestResolveDeadlineGate:
    def test_resolve_after_deadline_reverts_even_if_unchanged(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)
        
        # mock identical
        _mock_web(direct_vm, MOCK_SNAP_BODY, MOCK_LIVE_BODY)
        direct_vm.mock_llm(r".*", b'{"verdict": "UNCHANGED"}')
        
        _advance(direct_vm, HOLD_SECS + RESOLVE_SECS + 10)
        
        with direct_vm.expect_revert("resolve deadline has passed"):
            contract.resolve()
            
        case = contract.get_case()
        assert case["status"] == "FUNDED"
        assert case["payout_marker"] == "NONE"
        assert contract.get_credit(_addr(direct_owner)) == 0
        
    def test_expire_after_deadline_refunds_buyer_not_seller(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)
        
        _advance(direct_vm, HOLD_SECS + RESOLVE_SECS + 10)
        contract.expire()
        
        case = contract.get_case()
        assert case["status"] == "EXPIRED"
        assert case["payout_marker"] == "REFUNDED_BUYER"
        
        settle = contract.get_settlement()
        assert settle["payee"].lower() == _addr(direct_bob).lower()
        assert settle["payee_amount_wei"] == DEPOSIT
        assert settle["refundee"].lower() == _addr(direct_owner).lower()
        assert settle["refundee_amount_wei"] == 0
        
    def test_resolve_still_works_inside_window(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)
        
        _mock_web(direct_vm, MOCK_SNAP_BODY, MOCK_LIVE_BODY)
        direct_vm.mock_llm(r".*", b'{"verdict": "UNCHANGED"}')
        
        _advance(direct_vm, HOLD_SECS + 10)  # past hold, before deadline
        contract.resolve()
        
        case = contract.get_case()
        assert case["status"] == "SETTLED"
        assert case["payout_marker"] == "PAID_SELLER"

# ---------------------------------------------------------------------------
# 11. Test Frozen Snapshot
# ---------------------------------------------------------------------------

class TestFrozenSnapshot:
    def test_fund_freezes_snapshot_body_and_hash(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob)
        
        case = contract.get_case()
        assert case["status"] == "FUNDED"
        assert case["frozen_snapshot"] == MOCK_SNAP_BODY
        assert case["snapshot_frozen"] is True
        
        import hashlib
        expected_hash = hashlib.sha256(MOCK_SNAP_BODY.encode("utf-8")).hexdigest()
        assert case["frozen_snapshot_hash"] == expected_hash

    def test_fund_reverts_if_snapshot_cannot_be_fetched(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        
        direct_vm.mock_web(r"example\.com/snapshot", {"status": 404, "body": "Not found"})
        direct_vm.sender = direct_bob
        direct_vm.value = DEPOSIT
        
        with direct_vm.expect_revert("failed to fetch snapshot"):
            contract.fund_escrow()
            
        case = contract.get_case()
        assert case["status"] == "AWAITING_ESCROW"
        assert case["deposit_wei"] == 0
        assert case["frozen_snapshot"] == ""
        assert case["snapshot_frozen"] is False

    def test_mutated_snapshot_url_is_ignored_when_live_matches_frozen(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob) # fetches MOCK_SNAP_BODY
        
        # Now mutate the snapshot mock - this should be IGNORED
        direct_vm.mock_web(r"example\.com/snapshot", {"status": 200, "body": "B"*200})
        # Live matches the ORIGINAL frozen body
        direct_vm.mock_web(r"example\.com/live", {"status": 200, "body": MOCK_SNAP_BODY})
        direct_vm.mock_llm(r".*", b'{"verdict": "UNCHANGED"}')
        
        _advance(direct_vm, HOLD_SECS + 10)
        contract.resolve()
        
        case = contract.get_case()
        assert case["status"] == "SETTLED"
        assert case["payout_marker"] == "PAID_SELLER"
        pass

    def test_mutated_snapshot_url_cannot_launder_a_seller_payout(self, direct_vm, direct_deploy, direct_bob, direct_owner):
        contract = _deploy_default(direct_deploy, direct_bob, direct_owner)
        _fund(direct_vm, contract, direct_bob) # fetches MOCK_SNAP_BODY
        
        # Mutate the snapshot mock
        direct_vm.mock_web(r"example\.com/snapshot", {"status": 200, "body": "B"*200})
        # Live matches the MUTATED snapshot mock, but NOT the frozen snapshot
        direct_vm.mock_web(r"example\.com/live", {"status": 200, "body": "B"*200})
        direct_vm.mock_llm(r".*", b'{"verdict": "MATERIAL_CHANGE"}')
        
        _advance(direct_vm, HOLD_SECS + 10)
        contract.resolve()
        
        case = contract.get_case()
        assert case["status"] == "SETTLED"
        assert case["payout_marker"] == "REFUNDED_BUYER"
        pass
