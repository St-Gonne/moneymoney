"""
Tier 6: Milestones, Concierge, Inbound Statement Gateway & RBAC Test Suite
Comprehensive verification covering:
1. Inbound statement webhook routing & broker detection (NSDL, Zerodha, HDFC, CAMS, Schwab).
2. Payload validation error handling (missing sender, invalid email format).
3. Sovereign Gold Bond (SGB) Sep 2031 maturity math & semi-annual interest calculation verification.
4. Liquid emergency fund runway calculations & stress-testing.
5. RBAC permission matrix checks across Admin, Member, Advisor, and Guest tiers.
6. Concierge alert dispatch & family milestone progress tracking.
"""

import asyncio
import os
import sys
import unittest
from datetime import date, datetime
from decimal import Decimal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.api.inbound import (
    InboundEmailPayload,
    classify_broker,
    resolve_target_portfolio,
    handle_inbound_email_webhook,
    inbound_gateway_health,
)
from backend.app.engines.milestones_engine import (
    SGB_SEP_2031_SPEC,
    UserRole,
    VaultAction,
    calculate_sgb_semi_annual_interest,
    calculate_sgb_annual_interest,
    calculate_sgb_lifecycle_interest,
    calculate_sgb_redemption_payout,
    calculate_sgb_tax_position,
    calculate_liquid_emergency_fund,
    calculate_emergency_runway,
    stress_test_emergency_runway,
    check_rbac_permission,
    get_accessible_portfolios,
    ConciergeRequest,
    dispatch_concierge_alert,
    calculate_milestone_progress,
)


class TestTier6MilestonesAndConcierge(unittest.TestCase):
    """
    Tier 6 Test Suite: Inbound Statement Webhook Gateway, SGB Math,
    Emergency Fund Runway, RBAC Permissions, and Concierge Workflows.
    """

    # ==========================================================================
    # 1. INBOUND STATEMENT WEBHOOK ROUTING & BROKER DETECTION
    # ==========================================================================

    def test_f01_tc01_inbound_routing_nsdl_broker_detection_via_sender(self):
        """Detects NSDL broker institution from official NSDL sender email."""
        broker = classify_broker(sender_email="cas@nsdl.co.in", subject="Your Monthly e-CAS", filename="statement.pdf")
        self.assertEqual(broker, "NSDL")

    def test_f01_tc02_inbound_routing_nsdl_broker_detection_via_subject(self):
        """Detects NSDL from e-CAS keywords in the subject line."""
        broker = classify_broker(sender_email="notification@depository.in", subject="NSDL e-CAS Statement for August 2026", filename="doc.pdf")
        self.assertEqual(broker, "NSDL")

    def test_f01_tc03_inbound_routing_nsdl_broker_detection_via_filename(self):
        """Detects NSDL from attachment filename prefix."""
        broker = classify_broker(sender_email="alerts@mailer.com", subject="Statement Attached", filename="NSDL_CAS_Aug2026.pdf")
        self.assertEqual(broker, "NSDL")

    def test_f01_tc04_inbound_routing_zerodha_broker_detection_via_sender(self):
        """Detects Zerodha from official contracts@zerodha.com sender."""
        broker = classify_broker(sender_email="contracts@zerodha.com", subject="Contract Note", filename="doc.pdf")
        self.assertEqual(broker, "ZERODHA")

    def test_f01_tc05_inbound_routing_zerodha_broker_detection_via_subject(self):
        """Detects Zerodha from contract note keywords in subject."""
        broker = classify_broker(sender_email="forwarded@mail.com", subject="Contract Note for Trades on 14-Aug-2026", filename="trade.pdf")
        self.assertEqual(broker, "ZERODHA")

    def test_f01_tc06_inbound_routing_zerodha_broker_detection_via_filename(self):
        """Detects Zerodha from CN_ prefix in contract note filename."""
        broker = classify_broker(sender_email="user@mail.com", subject="Fwd: Trades", filename="CN_884920194.pdf")
        self.assertEqual(broker, "ZERODHA")

    def test_f01_tc07_inbound_routing_hdfc_broker_detection_via_sender(self):
        """Detects HDFC Securities from services@hdfcsec.com sender."""
        broker = classify_broker(sender_email="services@hdfcsec.com", subject="Daily Statement", filename="doc.pdf")
        self.assertEqual(broker, "HDFC")

    def test_f01_tc08_inbound_routing_hdfc_broker_detection_via_subject(self):
        """Detects HDFC from subject line naming HDFC Securities."""
        broker = classify_broker(sender_email="user@mail.com", subject="HDFC Securities Trade Confirmation", filename="stmt.pdf")
        self.assertEqual(broker, "HDFC")

    def test_f01_tc09_inbound_routing_hdfc_broker_detection_via_filename(self):
        """Detects HDFC from filename pattern."""
        broker = classify_broker(sender_email="user@mail.com", subject="Fwd: Trade", filename="HDFC_CN_20260814.pdf")
        self.assertEqual(broker, "HDFC")

    def test_f01_tc10_inbound_routing_cams_broker_detection_via_sender(self):
        """Detects CAMS / KFintech from official camsonline sender."""
        broker = classify_broker(sender_email="donotreply@camsonline.com", subject="Consolidated Statement", filename="cas.pdf")
        self.assertEqual(broker, "CAMS")

    def test_f01_tc11_inbound_routing_kfintech_broker_detection(self):
        """Detects CAMS / KFintech from kfintech sender address."""
        broker = classify_broker(sender_email="statements@kfintech.com", subject="CAS Statement", filename="cas.pdf")
        self.assertEqual(broker, "CAMS")

    def test_f01_tc12_inbound_routing_cams_cas_subject_detection(self):
        """Detects CAMS from mutual fund CAS subject line."""
        broker = classify_broker(sender_email="user@mail.com", subject="Mutual Fund Consolidated Account Statement - CAMS", filename="CAS_2026.pdf")
        self.assertEqual(broker, "CAMS")

    def test_f01_tc13_inbound_routing_schwab_broker_detection_via_sender(self):
        """Detects Charles Schwab from official schwab.com sender."""
        broker = classify_broker(sender_email="donotreply@schwab.com", subject="Account Statement", filename="stmt.pdf")
        self.assertEqual(broker, "SCHWAB")

    def test_f01_tc14_inbound_routing_schwab_broker_detection_via_subject(self):
        """Detects Charles Schwab from subject line."""
        broker = classify_broker(sender_email="user@mail.com", subject="Charles Schwab Monthly Brokerage Statement", filename="stmt.pdf")
        self.assertEqual(broker, "SCHWAB")

    def test_f01_tc15_inbound_routing_schwab_broker_detection_via_filename(self):
        """Detects Charles Schwab from filename pattern."""
        broker = classify_broker(sender_email="user@mail.com", subject="Statement", filename="SchwabStatement_202608.pdf")
        self.assertEqual(broker, "SCHWAB")

    def test_f01_tc16_inbound_routing_unknown_broker_fallback(self):
        """Returns UNKNOWN when broker cannot be identified from metadata."""
        broker = classify_broker(sender_email="random@unknownbroker.com", subject="Generic Invoice", filename="invoice.pdf")
        self.assertEqual(broker, "UNKNOWN")

    def test_f01_tc17_inbound_portfolio_routing_alex(self):
        """Routes statements from Alex to port_primary."""
        port = resolve_target_portfolio(sender_email="alex.taylor@example.com")
        self.assertEqual(port, "port_primary")

    def test_f01_tc18_inbound_portfolio_routing_father(self):
        """Routes statements from Robert / Father to port_father."""
        port = resolve_target_portfolio(sender_email="robert.taylor@example.com")
        self.assertEqual(port, "port_father")

    def test_f01_tc19_inbound_portfolio_routing_margaret(self):
        """Routes statements from Margaret to port_mother."""
        port = resolve_target_portfolio(sender_email="margaret.taylor@example.com")
        self.assertEqual(port, "port_mother")

    def test_f01_tc20_inbound_portfolio_routing_huf_via_subject(self):
        """Routes statements with HUF references or PAN PQRST3456Q to port_trust."""
        port = resolve_target_portfolio(sender_email="alex.taylor@example.com", subject="Taylor Family Trust Account Statement PQRST3456Q")
        self.assertEqual(port, "port_trust")

    def test_f01_tc21_inbound_endpoint_webhook_execution(self):
        """Verifies asynchronous webhook execution returning structured success response."""
        payload = InboundEmailPayload(
            sender_email="contracts@zerodha.com",
            recipient_email="alex.taylor@example.com",
            subject="Zerodha Contract Note CN_991823",
            attachment_filename="CN_991823.pdf",
            attachment_base64_or_url="base64content...",
            timestamp="2026-08-15T14:30:00Z",
        )
        response = asyncio.run(handle_inbound_email_webhook(payload))
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["broker_detected"], "ZERODHA")
        self.assertEqual(response["target_portfolio"], "port_primary")
        self.assertTrue(response["queued"])

    def test_f01_tc22_inbound_gateway_health_check(self):
        """Verifies inbound gateway health endpoint returns HEALTHY status."""
        health = inbound_gateway_health()
        self.assertEqual(health["status"], "HEALTHY")
        self.assertEqual(health["gateway"], "inbound-statement-processor")
        self.assertIn("timestamp", health)

    # ==========================================================================
    # 2. PAYLOAD VALIDATION ERROR HANDLING
    # ==========================================================================

    def test_f02_tc01_payload_validation_missing_sender_raises_value_error(self):
        """Fails validation when sender_email is empty string."""
        with self.assertRaises(ValueError):
            InboundEmailPayload(sender_email="")

    def test_f02_tc02_payload_validation_none_sender_raises_value_error(self):
        """Fails validation when sender_email is None or whitespace."""
        with self.assertRaises(ValueError):
            InboundEmailPayload(sender_email="   ")

    def test_f02_tc03_payload_validation_missing_at_symbol_raises_error(self):
        """Fails validation when sender_email is missing @ symbol."""
        with self.assertRaises(ValueError):
            InboundEmailPayload(sender_email="invalid_email_no_at.com")

    def test_f02_tc04_payload_validation_missing_domain_raises_error(self):
        """Fails validation when sender_email has no domain part."""
        with self.assertRaises(ValueError):
            InboundEmailPayload(sender_email="user@")

    def test_f02_tc05_payload_validation_missing_tld_raises_error(self):
        """Fails validation when sender_email has no top-level domain."""
        with self.assertRaises(ValueError):
            InboundEmailPayload(sender_email="user@nodomain")

    def test_f02_tc06_payload_validation_invalid_recipient_format_raises_error(self):
        """Fails validation when recipient_email is malformed."""
        with self.assertRaises(ValueError):
            InboundEmailPayload(sender_email="valid@broker.com", recipient_email="invalid_recipient")

    def test_f02_tc07_payload_validation_valid_email_sanitization(self):
        """Accepts valid emails with plus-addressing, subdomains, and trims whitespace."""
        payload = InboundEmailPayload(
            sender_email="  alex.taylor+vault@sub.gmail.com  ",
            recipient_email="  vault-inbound@moneymoney.in  ",
            subject="Valid Test",
        )
        self.assertEqual(payload.sender_email, "alex.taylor+vault@sub.gmail.com")
        self.assertEqual(payload.recipient_email, "vault-inbound@moneymoney.in")

    # ==========================================================================
    # 3. SGB SEP 2031 MATURITY MATH & INTEREST CALCULATION VERIFICATION
    # ==========================================================================

    def test_f03_tc01_sgb_semi_annual_coupon_exact_calculation(self):
        """
        Verifies exact semi-annual coupon calculation for SGB Sep 2031:
        Holding: 50 grams @ ₹5,923.00 subscription nominal = ₹2,96,150.00
        Semi-annual interest @ 1.25% (2.50% p.a. / 2) = ₹3,701.88
        """
        quantity = Decimal("50")
        issue_price = Decimal("5923.00")
        semi_interest = calculate_sgb_semi_annual_interest(quantity, issue_price)
        expected = (quantity * issue_price * Decimal("0.0125")).quantize(Decimal("0.01"))
        self.assertEqual(semi_interest, Decimal("3701.88"))
        self.assertEqual(semi_interest, expected)

    def test_f03_tc02_sgb_annual_coupon_exact_calculation(self):
        """
        Verifies annual coupon (2 semi-annual payments):
        2 * ₹3,701.88 = ₹7,403.76
        """
        quantity = Decimal("50")
        issue_price = Decimal("5923.00")
        annual_interest = calculate_sgb_annual_interest(quantity, issue_price)
        self.assertEqual(annual_interest, Decimal("7403.76"))

    def test_f03_tc03_sgb_8_year_lifecycle_total_interest_payout(self):
        """
        Verifies total cumulative interest across 8 years (16 semi-annual coupons):
        16 * ₹3,701.88 = ₹59,230.08 (exact 20.00% gross nominal interest yield).
        """
        quantity = Decimal("50")
        issue_price = Decimal("5923.00")
        lifecycle_interest = calculate_sgb_lifecycle_interest(quantity, issue_price, tenor_years=8)
        self.assertEqual(lifecycle_interest, Decimal("59230.08"))

    def test_f03_tc04_sgb_maturity_redemption_gross_payout(self):
        """
        Verifies gross maturity redemption payout at RBI gold rate:
        50 grams @ ₹8,500.00/g = ₹4,25,000.00.
        """
        quantity = Decimal("50")
        redemption_gold_rate = Decimal("8500.00")
        payout = calculate_sgb_redemption_payout(quantity, redemption_gold_rate)
        self.assertEqual(payout, Decimal("425000.00"))

    def test_f03_tc05_sgb_maturity_tax_exemption_under_section_47_viic(self):
        """
        Verifies Section 47(viic) 100% Tax Exemption on maturity redemption:
        Principal: ₹2,96,150.00 | Redemption: ₹4,25,000.00 | Capital Gain: ₹1,28,850.00
        Tax Liability: ₹0.00 (Exempt).
        """
        quantity = Decimal("50")
        issue_price = Decimal("5923.00")
        redemption_price = Decimal("8500.00")
        tax_pos = calculate_sgb_tax_position(quantity, issue_price, redemption_price, is_maturity_redemption=True)
        self.assertTrue(tax_pos["is_maturity_redemption"])
        self.assertEqual(tax_pos["capital_gain"], Decimal("128850.00"))
        self.assertEqual(tax_pos["tax_liability"], Decimal("0.00"))
        self.assertEqual(tax_pos["taxable_gain"], Decimal("0.00"))
        self.assertEqual(tax_pos["exemption_section"], "Section 47(viic)")
        self.assertEqual(tax_pos["tax_status"], "TAX_EXEMPT_AT_MATURITY")

    def test_f03_tc06_sgb_secondary_market_ltcg_tax_under_finance_act_2024(self):
        """
        Verifies secondary market sale after 24 months under Finance Act 2024:
        50 grams sold @ ₹7,000.00/g -> Capital Gain: ₹53,850.00
        LTCG Tax @ 12.5% = ₹6,731.25.
        """
        quantity = Decimal("50")
        issue_price = Decimal("5923.00")
        sale_price = Decimal("7000.00")
        tax_pos = calculate_sgb_tax_position(quantity, issue_price, sale_price, is_maturity_redemption=False, holding_months=24)
        self.assertFalse(tax_pos["is_maturity_redemption"])
        self.assertEqual(tax_pos["capital_gain"], Decimal("53850.00"))
        self.assertEqual(tax_pos["tax_rate_pct"], Decimal("12.50"))
        self.assertEqual(tax_pos["tax_liability"], Decimal("6731.25"))

    def test_f03_tc07_sgb_secondary_market_stcg_tax_under_12_months(self):
        """
        Verifies secondary market sale within 6 months taxed at slab rate (30%):
        50 grams sold @ ₹6,500.00/g -> Gain: ₹28,850.00 -> Tax: ₹8,655.00.
        """
        quantity = Decimal("50")
        issue_price = Decimal("5923.00")
        sale_price = Decimal("6500.00")
        tax_pos = calculate_sgb_tax_position(quantity, issue_price, sale_price, is_maturity_redemption=False, holding_months=6)
        self.assertEqual(tax_pos["capital_gain"], Decimal("28850.00"))
        self.assertEqual(tax_pos["tax_rate_pct"], Decimal("30.00"))
        self.assertEqual(tax_pos["tax_liability"], Decimal("8655.00"))

    def test_f03_tc08_sgb_zero_and_negative_quantity_handling(self):
        """Guards against invalid negative or zero quantities."""
        self.assertEqual(calculate_sgb_semi_annual_interest(Decimal("0")), Decimal("0.00"))
        self.assertEqual(calculate_sgb_semi_annual_interest(Decimal("-10")), Decimal("0.00"))
        self.assertEqual(calculate_sgb_redemption_payout(Decimal("0"), Decimal("8500")), Decimal("0.00"))

    # ==========================================================================
    # 4. LIQUID EMERGENCY FUND RUNWAY CALCULATIONS
    # ==========================================================================

    def test_f04_tc01_emergency_runway_baseline_6_months_surplus(self):
        """
        Verifies emergency runway calculation with 9 months of liquidity (Surplus):
        Liquid Capital: ₹18,00,000 | Monthly Burn: ₹2,00,000 | Target: 6 months (₹12,00,000)
        Runway: 9.0 months | Surplus: +₹6,00,000 | Funded Ratio: 150.0%
        """
        liquid_capital = Decimal("1800000.00")
        burn_rate = Decimal("200000.00")
        res = calculate_emergency_runway(liquid_capital, burn_rate, target_months=6)
        self.assertEqual(res["runway_months"], Decimal("9.0"))
        self.assertEqual(res["target_fund_amount"], Decimal("1200000.00"))
        self.assertEqual(res["variance_amount"], Decimal("600000.00"))
        self.assertEqual(res["funded_ratio_pct"], Decimal("150.0"))
        self.assertEqual(res["status"], "SURPLUS")
        self.assertTrue(res["is_target_met"])

    def test_f04_tc02_emergency_runway_critical_deficit_below_3_months(self):
        """
        Verifies critical deficit alert when liquid capital provides < 3 months runway:
        Liquid Capital: ₹4,00,000 | Monthly Burn: ₹2,00,000 -> Runway: 2.0 months (CRITICAL_DEFICIT)
        """
        res = calculate_emergency_runway(Decimal("400000.00"), Decimal("200000.00"), target_months=6)
        self.assertEqual(res["runway_months"], Decimal("2.0"))
        self.assertEqual(res["status"], "CRITICAL_DEFICIT")
        self.assertFalse(res["is_target_met"])

    def test_f04_tc03_emergency_runway_moderate_deficit_between_3_and_6_months(self):
        """
        Verifies moderate deficit status between 3 and 6 months runway:
        Liquid Capital: ₹8,00,000 | Monthly Burn: ₹2,00,000 -> Runway: 4.0 months (MODERATE_DEFICIT)
        """
        res = calculate_emergency_runway(Decimal("800000.00"), Decimal("200000.00"), target_months=6)
        self.assertEqual(res["runway_months"], Decimal("4.0"))
        self.assertEqual(res["status"], "MODERATE_DEFICIT")
        self.assertFalse(res["is_target_met"])

    def test_f04_tc04_emergency_runway_asset_classification_filtering(self):
        """
        Verifies liquid asset aggregator includes instant/near-liquid assets and excludes illiquid/locked assets:
        Includes: Savings (₹3L), FDs (₹5L), Liquid MFs (₹4L), Ultra Short (₹2L * 0.95 = ₹1.9L) = ₹13.9L
        Excludes: Equity Stocks (₹20L), ELSS (₹5L), PPF (₹10L), Real Estate (₹1Cr), SGB (₹15L), US Stocks (₹30L)
        """
        assets = [
            {"category": "SAVINGS_BANK", "amount": Decimal("300000.00")},
            {"category": "FIXED_DEPOSIT_SWEEP", "amount": Decimal("500000.00")},
            {"category": "LIQUID_MF", "amount": Decimal("400000.00")},
            {"category": "ULTRA_SHORT_MF", "amount": Decimal("200000.00")},
            {"category": "EQUITY_STOCKS", "amount": Decimal("2000000.00")},
            {"category": "ELSS", "amount": Decimal("500000.00")},
            {"category": "PPF", "amount": Decimal("1000000.00")},
            {"category": "REAL_ESTATE", "amount": Decimal("10000000.00")},
            {"category": "SGB", "amount": Decimal("1500000.00")},
            {"category": "US_STOCKS", "amount": Decimal("3000000.00")},
        ]
        total_liquid = calculate_liquid_emergency_fund(assets)
        self.assertEqual(total_liquid, Decimal("1390000.00"))

    def test_f04_tc05_emergency_runway_stress_test_simulation(self):
        """
        Verifies resilience stress test under +25% monthly burn rate surge and 5% liquidation haircut:
        Baseline: ₹18L / ₹2L = 9.0 months
        Stressed: (₹18L * 0.95 = ₹17.1L) / (₹2L * 1.25 = ₹2.5L) = 6.8 months (Resilience Pass)
        """
        res = stress_test_emergency_runway(Decimal("1800000.00"), Decimal("200000.00"))
        self.assertEqual(res["baseline_runway_months"], Decimal("9.0"))
        self.assertEqual(res["stressed_runway_months"], Decimal("6.8"))
        self.assertEqual(res["runway_delta_months"], Decimal("-2.2"))
        self.assertTrue(res["resilience_pass"])

    def test_f04_tc06_emergency_runway_zero_or_negative_burn_raises_error(self):
        """Fails closed when monthly burn rate is zero or negative."""
        with self.assertRaises(ValueError):
            calculate_emergency_runway(Decimal("1000000"), Decimal("0"))
        with self.assertRaises(ValueError):
            calculate_emergency_runway(Decimal("1000000"), Decimal("-50000"))

    # ==========================================================================
    # 5. RBAC PERMISSION MATRIX CHECKS
    # ==========================================================================

    def test_f05_tc01_rbac_admin_full_privileges(self):
        """Admin (Alex) has unrestricted authorization across all vault operations."""
        admin = UserRole.ADMIN
        self.assertTrue(check_rbac_permission(admin, VaultAction.VIEW_CONSOLIDATED_VAULT))
        self.assertTrue(check_rbac_permission(admin, VaultAction.VIEW_INDIVIDUAL_PORTFOLIO, "port_father"))
        self.assertTrue(check_rbac_permission(admin, VaultAction.INGEST_STATEMENT))
        self.assertTrue(check_rbac_permission(admin, VaultAction.VIEW_TAX_DOSSIER))
        self.assertTrue(check_rbac_permission(admin, VaultAction.VIEW_SCHEDULE_FA))
        self.assertTrue(check_rbac_permission(admin, VaultAction.VIEW_FOREIGN_ASSETS))
        self.assertTrue(check_rbac_permission(admin, VaultAction.RESET_LEDGER))
        self.assertTrue(check_rbac_permission(admin, VaultAction.EDIT_PROFILE))
        self.assertTrue(check_rbac_permission(admin, VaultAction.ACCESS_CONCIERGE))

    def test_f05_tc02_rbac_member_access_to_own_portfolio(self):
        """Member (Robert / Father) is authorized to view his own portfolio."""
        member = UserRole.MEMBER
        self.assertTrue(
            check_rbac_permission(member, VaultAction.VIEW_INDIVIDUAL_PORTFOLIO, requested_portfolio="port_father", user_portfolio="port_father")
        )

    def test_f05_tc03_rbac_member_blocked_from_other_member_portfolio(self):
        """Member (Robert) is strictly blocked from accessing Alex or Margaret's portfolio."""
        member = UserRole.MEMBER
        self.assertFalse(
            check_rbac_permission(member, VaultAction.VIEW_INDIVIDUAL_PORTFOLIO, requested_portfolio="port_primary", user_portfolio="port_father")
        )
        self.assertFalse(
            check_rbac_permission(member, VaultAction.VIEW_INDIVIDUAL_PORTFOLIO, requested_portfolio="port_mother", user_portfolio="port_father")
        )

    def test_f05_tc04_rbac_member_blocked_from_system_admin_actions(self):
        """Member is blocked from sensitive administrative actions (Reset Ledger, Foreign Assets)."""
        member = UserRole.MEMBER
        self.assertFalse(check_rbac_permission(member, VaultAction.VIEW_CONSOLIDATED_VAULT))
        self.assertFalse(check_rbac_permission(member, VaultAction.VIEW_SCHEDULE_FA))
        self.assertFalse(check_rbac_permission(member, VaultAction.VIEW_FOREIGN_ASSETS))
        self.assertFalse(check_rbac_permission(member, VaultAction.RESET_LEDGER))
        self.assertFalse(check_rbac_permission(member, VaultAction.EDIT_PROFILE))

    def test_f05_tc05_rbac_advisor_read_only_privileges(self):
        """Advisor (CA) has read-only access to Tax Dossier, Schedule FA, and Consolidated Vault."""
        advisor = UserRole.ADVISOR
        self.assertTrue(check_rbac_permission(advisor, VaultAction.VIEW_CONSOLIDATED_VAULT))
        self.assertTrue(check_rbac_permission(advisor, VaultAction.VIEW_TAX_DOSSIER))
        self.assertTrue(check_rbac_permission(advisor, VaultAction.VIEW_SCHEDULE_FA))
        self.assertTrue(check_rbac_permission(advisor, VaultAction.VIEW_FOREIGN_ASSETS))

        # Blocked from state mutations
        self.assertFalse(check_rbac_permission(advisor, VaultAction.INGEST_STATEMENT))
        self.assertFalse(check_rbac_permission(advisor, VaultAction.RESET_LEDGER))
        self.assertFalse(check_rbac_permission(advisor, VaultAction.EDIT_PROFILE))

    def test_f05_tc06_rbac_guest_fail_closed_zero_access(self):
        """Guest / Unauthenticated role has 0 permissions (fail-closed perimeter)."""
        guest = UserRole.GUEST
        for action in [
            VaultAction.VIEW_CONSOLIDATED_VAULT,
            VaultAction.VIEW_INDIVIDUAL_PORTFOLIO,
            VaultAction.INGEST_STATEMENT,
            VaultAction.VIEW_TAX_DOSSIER,
            VaultAction.RESET_LEDGER,
        ]:
            self.assertFalse(check_rbac_permission(guest, action))

    def test_f05_tc07_rbac_accessible_portfolios_by_role(self):
        """Verifies portfolio list resolution per role."""
        self.assertEqual(len(get_accessible_portfolios(UserRole.ADMIN)), 4)
        self.assertEqual(len(get_accessible_portfolios(UserRole.ADVISOR)), 4)
        self.assertEqual(get_accessible_portfolios(UserRole.MEMBER, "port_father"), ["port_father"])
        self.assertEqual(get_accessible_portfolios(UserRole.GUEST), [])

    # ==========================================================================
    # 6. CONCIERGE ALERTS & MILESTONE TRACKING HELPERS
    # ==========================================================================

    def test_f06_tc01_concierge_alert_dispatch(self):
        """Dispatches structured concierge alert with full audit metadata."""
        req = ConciergeRequest(
            user_name="Robert Taylor",
            user_email="robert.taylor@example.com",
            portfolio_id="port_father",
            screen_context="VOICE_PORTAL_OVERVIEW",
            message="How do I view dividend income for FY24-25?",
            urgency="NORMAL",
        )
        res = dispatch_concierge_alert(req)
        self.assertEqual(res["status"], "DISPATCHED")
        self.assertTrue(res["ticket_id"].startswith("CONC-"))
        self.assertEqual(res["target_admin"], "alex.taylor@example.com")
        self.assertEqual(res["user_name"], "Robert Taylor")

    def test_f06_tc02_concierge_missing_email_raises_error(self):
        """Fails closed when concierge request lacks email or message."""
        with self.assertRaises(ValueError):
            dispatch_concierge_alert(
                ConciergeRequest(user_name="User", user_email="", portfolio_id="port_x", screen_context="ctx", message="help")
            )

    def test_f06_tc03_milestone_progress_tracking_partial_and_completed(self):
        """Calculates milestone completion percentage, deficit, and goal achievement."""
        # 50% funded milestone
        m1 = calculate_milestone_progress(Decimal("5000000"), Decimal("10000000"), "Emergency Fund Target")
        self.assertEqual(m1["percentage_complete"], Decimal("50.0"))
        self.assertEqual(m1["remaining_deficit"], Decimal("5000000.00"))
        self.assertFalse(m1["is_achieved"])

        # 100%+ completed milestone
        m2 = calculate_milestone_progress(Decimal("12000000"), Decimal("10000000"), "Retirement Corpus Tranche")
        self.assertEqual(m2["percentage_complete"], Decimal("100.0"))
        self.assertEqual(m2["remaining_deficit"], Decimal("0.00"))
        self.assertTrue(m2["is_achieved"])


if __name__ == "__main__":
    unittest.main()
