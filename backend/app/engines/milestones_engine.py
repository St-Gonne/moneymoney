"""
Milestones, Concierge, Emergency Fund, and RBAC Engine
Implements:
1. Sovereign Gold Bond (SGB) 2031 maturity math, semi-annual interest, and Section 47(viic) tax rules.
2. Liquid Emergency Fund runway calculations, burn-rate sensitivity, and liquidity stress testing.
3. Role-Based Access Control (RBAC) permission matrix (Admin, Family Member, Advisor, Guest).
4. Red "Need Help?" Concierge Alert dispatcher and family milestone goal tracking.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Set, Tuple


# ==============================================================================
# 1. SOVEREIGN GOLD BOND (SGB) MATURITY & INTEREST ENGINE
# ==============================================================================

@dataclass(frozen=True)
class SGBBondSpecification:
    """Specification metadata for Sovereign Gold Bond issues."""
    tranche_name: str
    isin: str
    issue_date: date
    maturity_date: date
    issue_price_per_gram: Decimal
    coupon_rate_p_a: Decimal = Decimal("0.0250")  # 2.50% p.a.
    coupon_frequency_months: int = 6               # Semi-annual


# SGB 2023-24 Series II (Maturity September 2031) Default Spec
SGB_SEP_2031_SPEC = SGBBondSpecification(
    tranche_name="SGB 2023-24 Series II",
    isin="IN0020230119",
    issue_date=date(2023, 9, 15),
    maturity_date=date(2031, 9, 15),
    issue_price_per_gram=Decimal("5923.00"),
    coupon_rate_p_a=Decimal("0.0250"),
    coupon_frequency_months=6,
)


def calculate_sgb_semi_annual_interest(
    quantity_grams: Decimal,
    issue_price_per_gram: Decimal = Decimal("5923.00"),
    coupon_rate_p_a: Decimal = Decimal("0.0250"),
) -> Decimal:
    """
    Calculates the 6-month semi-annual interest coupon for SGB holdings.
    Formula: Quantity (grams) * Issue Price * (Coupon Rate p.a. / 2)
    """
    if quantity_grams <= Decimal("0") or issue_price_per_gram <= Decimal("0"):
        return Decimal("0.00")
    semi_rate = coupon_rate_p_a / Decimal("2")
    nominal_principal = quantity_grams * issue_price_per_gram
    interest = nominal_principal * semi_rate
    return interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_sgb_annual_interest(
    quantity_grams: Decimal,
    issue_price_per_gram: Decimal = Decimal("5923.00"),
    coupon_rate_p_a: Decimal = Decimal("0.0250"),
) -> Decimal:
    """
    Calculates annual interest coupon (2 semi-annual payments) for SGB holdings.
    """
    return calculate_sgb_semi_annual_interest(quantity_grams, issue_price_per_gram, coupon_rate_p_a) * Decimal("2")


def calculate_sgb_lifecycle_interest(
    quantity_grams: Decimal,
    issue_price_per_gram: Decimal = Decimal("5923.00"),
    tenor_years: int = 8,
    coupon_rate_p_a: Decimal = Decimal("0.0250"),
) -> Decimal:
    """
    Calculates total cumulative interest earned over the entire 8-year (16 coupons) SGB lifespan.
    Total = 16 * Semi-Annual Coupon = 20.00% of nominal subscription principal.
    """
    semi_coupon = calculate_sgb_semi_annual_interest(quantity_grams, issue_price_per_gram, coupon_rate_p_a)
    total_periods = tenor_years * 2
    return semi_coupon * Decimal(str(total_periods))


def calculate_sgb_redemption_payout(
    quantity_grams: Decimal,
    redemption_gold_price_per_gram: Decimal,
) -> Decimal:
    """
    Calculates gross redemption payout at maturity based on prevailing RBI reference gold price.
    Formula: Quantity (grams) * RBI Gold Rate at Maturity.
    """
    if quantity_grams <= Decimal("0") or redemption_gold_price_per_gram <= Decimal("0"):
        return Decimal("0.00")
    payout = quantity_grams * redemption_gold_price_per_gram
    return payout.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_sgb_tax_position(
    quantity_grams: Decimal,
    issue_price_per_gram: Decimal,
    redemption_price_per_gram: Decimal,
    is_maturity_redemption: bool = True,
    holding_months: int = 96,
) -> Dict[str, Any]:
    """
    Evaluates Capital Gains tax liability on SGB disposal under Section 47(viic) & Finance Act 2024:
    - Final Redemption at 8-Year Maturity: 100% Tax EXEMPT under Section 47(viic) of Income Tax Act (Tax = ₹0).
    - Secondary Market Sale (> 12 months): LTCG at 12.5% without indexation (Finance Act 2024).
    - Secondary Market Sale (<= 12 months): STCG at slab rate.
    """
    nominal_principal = (quantity_grams * issue_price_per_gram).quantize(Decimal("0.01"))
    total_proceeds = (quantity_grams * redemption_price_per_gram).quantize(Decimal("0.01"))
    capital_gain = total_proceeds - nominal_principal

    if is_maturity_redemption:
        return {
            "is_maturity_redemption": True,
            "nominal_principal": nominal_principal,
            "total_proceeds": total_proceeds,
            "capital_gain": capital_gain,
            "taxable_gain": Decimal("0.00"),
            "tax_rate_pct": Decimal("0.00"),
            "tax_liability": Decimal("0.00"),
            "exemption_section": "Section 47(viic)",
            "tax_status": "TAX_EXEMPT_AT_MATURITY",
        }

    # Secondary market sale before maturity
    if holding_months > 12:
        tax_rate = Decimal("0.125")  # 12.5% Finance Act 2024 LTCG
        taxable_gain = max(Decimal("0.00"), capital_gain)
        tax_liability = (taxable_gain * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {
            "is_maturity_redemption": False,
            "nominal_principal": nominal_principal,
            "total_proceeds": total_proceeds,
            "capital_gain": capital_gain,
            "taxable_gain": taxable_gain,
            "tax_rate_pct": Decimal("12.50"),
            "tax_liability": tax_liability,
            "exemption_section": None,
            "tax_status": "SECONDARY_MARKET_LTCG_12_5_PCT",
        }
    else:
        # STCG slab rate (modeled at nominal 30% slab)
        taxable_gain = max(Decimal("0.00"), capital_gain)
        tax_liability = (taxable_gain * Decimal("0.30")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {
            "is_maturity_redemption": False,
            "nominal_principal": nominal_principal,
            "total_proceeds": total_proceeds,
            "capital_gain": capital_gain,
            "taxable_gain": taxable_gain,
            "tax_rate_pct": Decimal("30.00"),
            "tax_liability": tax_liability,
            "exemption_section": None,
            "tax_status": "SECONDARY_MARKET_STCG_SLAB",
        }


# ==============================================================================
# 2. LIQUID EMERGENCY FUND RUNWAY ENGINE
# ==============================================================================

class AssetLiquidityTier:
    """Categorization of assets for emergency fund liquidity calculation."""
    INSTANT_LIQUID = {"SAVINGS_BANK", "FIXED_DEPOSIT_SWEEP", "OVERNIGHT_MF", "LIQUID_MF"}
    NEAR_LIQUID = {"ULTRA_SHORT_MF", "ARBITRAGE_FUND"}
    ILLIQUID = {"EQUITY_STOCKS", "ELSS", "PPF", "EPF", "REAL_ESTATE", "SGB", "US_STOCKS"}


DEFAULT_LIQUIDITY_WEIGHTS: Dict[str, Decimal] = {
    "SAVINGS_BANK": Decimal("1.00"),
    "FIXED_DEPOSIT_SWEEP": Decimal("1.00"),
    "OVERNIGHT_MF": Decimal("1.00"),
    "LIQUID_MF": Decimal("1.00"),
    "ULTRA_SHORT_MF": Decimal("0.95"),
    "ARBITRAGE_FUND": Decimal("0.90"),
    "EQUITY_STOCKS": Decimal("0.00"),
    "ELSS": Decimal("0.00"),
    "PPF": Decimal("0.00"),
    "REAL_ESTATE": Decimal("0.00"),
    "SGB": Decimal("0.00"),
    "US_STOCKS": Decimal("0.00"),
}


def calculate_liquid_emergency_fund(
    asset_balances: List[Dict[str, Any]],
    liquidity_weights: Optional[Dict[str, Decimal]] = None,
) -> Decimal:
    """
    Computes weighted liquid capital available strictly for emergency reserves.
    Excludes lock-ins, high-volatility equities, and foreign accounts with FEMA remittance delays.
    """
    weights = liquidity_weights or DEFAULT_LIQUIDITY_WEIGHTS
    total_liquid = Decimal("0.00")

    for asset in asset_balances:
        category = asset.get("category", "")
        amount = Decimal(str(asset.get("amount", 0)))
        weight = weights.get(category, Decimal("0.00"))
        total_liquid += amount * weight

    return total_liquid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_emergency_runway(
    total_liquid_capital: Decimal,
    monthly_burn_rate: Decimal,
    target_months: int = 6,
) -> Dict[str, Any]:
    """
    Calculates liquid emergency runway in months, target fund amount, and surplus/deficit metrics.
    """
    if monthly_burn_rate <= Decimal("0"):
        raise ValueError("Monthly burn rate must be greater than zero.")

    runway_months = (total_liquid_capital / monthly_burn_rate).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    target_fund_amount = (Decimal(str(target_months)) * monthly_burn_rate).quantize(Decimal("0.01"))
    variance_amount = (total_liquid_capital - target_fund_amount).quantize(Decimal("0.01"))
    funded_ratio_pct = ((total_liquid_capital / target_fund_amount) * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )

    if runway_months < Decimal("3.0"):
        status = "CRITICAL_DEFICIT"
    elif runway_months < Decimal(str(target_months)):
        status = "MODERATE_DEFICIT"
    elif runway_months == Decimal(str(target_months)):
        status = "ADEQUATELY_FUNDED"
    else:
        status = "SURPLUS"

    return {
        "total_liquid_capital": total_liquid_capital,
        "monthly_burn_rate": monthly_burn_rate,
        "runway_months": runway_months,
        "target_months": target_months,
        "target_fund_amount": target_fund_amount,
        "variance_amount": variance_amount,
        "funded_ratio_pct": funded_ratio_pct,
        "status": status,
        "is_target_met": total_liquid_capital >= target_fund_amount,
    }


def stress_test_emergency_runway(
    total_liquid_capital: Decimal,
    monthly_burn_rate: Decimal,
    expense_surge_pct: Decimal = Decimal("0.25"),     # +25% monthly expense surge
    liquidity_haircut_pct: Decimal = Decimal("0.05"), # 5% haircut on liquid redemption
    target_months: int = 6,
) -> Dict[str, Any]:
    """
    Simulates acute distress: living cost surge (medical/family emergency) + mutual fund redemption haircut.
    """
    stressed_capital = total_liquid_capital * (Decimal("1.00") - liquidity_haircut_pct)
    stressed_burn = monthly_burn_rate * (Decimal("1.00") + expense_surge_pct)

    baseline = calculate_emergency_runway(total_liquid_capital, monthly_burn_rate, target_months)
    stressed = calculate_emergency_runway(stressed_capital, stressed_burn, target_months)

    return {
        "baseline_runway_months": baseline["runway_months"],
        "stressed_runway_months": stressed["runway_months"],
        "runway_delta_months": (stressed["runway_months"] - baseline["runway_months"]).quantize(Decimal("0.1")),
        "stressed_liquid_capital": stressed_capital.quantize(Decimal("0.01")),
        "stressed_monthly_burn": stressed_burn.quantize(Decimal("0.01")),
        "stressed_status": stressed["status"],
        "resilience_pass": stressed["runway_months"] >= Decimal("3.0"),
    }


# ==============================================================================
# 3. ROLE-BASED ACCESS CONTROL (RBAC) PERMISSION MATRIX
# ==============================================================================

class UserRole:
    ADMIN = "ADMIN"        # Alex - Full Vault Administrator
    MEMBER = "MEMBER"      # Robert / Margaret - Individual Member View
    ADVISOR = "ADVISOR"    # Chartered Accountant / Tax Advisor (Read-Only)
    GUEST = "GUEST"        # Unauthenticated / Unauthorized (Fail-Closed)


class VaultAction:
    VIEW_CONSOLIDATED_VAULT = "VIEW_CONSOLIDATED_VAULT"
    VIEW_INDIVIDUAL_PORTFOLIO = "VIEW_INDIVIDUAL_PORTFOLIO"
    INGEST_STATEMENT = "INGEST_STATEMENT"
    VIEW_TAX_DOSSIER = "VIEW_TAX_DOSSIER"
    VIEW_SCHEDULE_FA = "VIEW_SCHEDULE_FA"
    VIEW_FOREIGN_ASSETS = "VIEW_FOREIGN_ASSETS"
    RESET_LEDGER = "RESET_LEDGER"
    EDIT_PROFILE = "EDIT_PROFILE"
    ACCESS_CONCIERGE = "ACCESS_CONCIERGE"


# Global Permission Matrix
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    UserRole.ADMIN: {
        VaultAction.VIEW_CONSOLIDATED_VAULT,
        VaultAction.VIEW_INDIVIDUAL_PORTFOLIO,
        VaultAction.INGEST_STATEMENT,
        VaultAction.VIEW_TAX_DOSSIER,
        VaultAction.VIEW_SCHEDULE_FA,
        VaultAction.VIEW_FOREIGN_ASSETS,
        VaultAction.RESET_LEDGER,
        VaultAction.EDIT_PROFILE,
        VaultAction.ACCESS_CONCIERGE,
    },
    UserRole.MEMBER: {
        VaultAction.VIEW_INDIVIDUAL_PORTFOLIO,
        VaultAction.INGEST_STATEMENT,
        VaultAction.VIEW_TAX_DOSSIER,
        VaultAction.ACCESS_CONCIERGE,
    },
    UserRole.ADVISOR: {
        VaultAction.VIEW_CONSOLIDATED_VAULT,
        VaultAction.VIEW_INDIVIDUAL_PORTFOLIO,
        VaultAction.VIEW_TAX_DOSSIER,
        VaultAction.VIEW_SCHEDULE_FA,
        VaultAction.VIEW_FOREIGN_ASSETS,
    },
    UserRole.GUEST: set(),  # Fail-closed: 0 permissions
}


def check_rbac_permission(
    role: str,
    action: str,
    requested_portfolio: Optional[str] = None,
    user_portfolio: Optional[str] = None,
) -> bool:
    """
    Evaluates RBAC authorization matrix:
    - ADMIN: Full access across all actions and all portfolios.
    - MEMBER: Allowed only for own assigned portfolio; blocked from other portfolios, Schwab foreign assets, and system reset.
    - ADVISOR: Read-only access across tax dossiers and schedule FA; blocked from mutating state (ingest/reset).
    - GUEST / UNKNOWN: Always denied (fail-closed).
    """
    allowed_actions = ROLE_PERMISSIONS.get(role, set())
    if action not in allowed_actions:
        return False

    # Member isolation check: Member cannot view or modify someone else's portfolio
    if role == UserRole.MEMBER:
        if requested_portfolio and user_portfolio and requested_portfolio != user_portfolio:
            return False

    return True


def get_accessible_portfolios(role: str, user_portfolio: Optional[str] = None) -> List[str]:
    """
    Returns list of portfolio IDs accessible to the specified role.
    """
    all_portfolios = ["port_primary", "port_father", "port_mother", "port_trust"]
    if role in (UserRole.ADMIN, UserRole.ADVISOR):
        return all_portfolios
    elif role == UserRole.MEMBER and user_portfolio:
        return [user_portfolio]
    return []


# ==============================================================================
# 4. CONCIERGE & MILESTONE TRACKING HELPERS
# ==============================================================================

@dataclass
class ConciergeRequest:
    user_name: str
    user_email: str
    portfolio_id: str
    screen_context: str
    message: str
    urgency: str = "NORMAL"  # NORMAL, URGENT, CRITICAL


def dispatch_concierge_alert(req: ConciergeRequest) -> Dict[str, Any]:
    """
    Dispatches a concierge notification for family support / one-click assistance.
    """
    if not req.user_email or not req.message:
        raise ValueError("Concierge request must include user_email and message.")

    ticket_id = f"CONC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return {
        "status": "DISPATCHED",
        "ticket_id": ticket_id,
        "target_admin": "alex.taylor@example.com",
        "user_name": req.user_name,
        "portfolio_id": req.portfolio_id,
        "screen_context": req.screen_context,
        "urgency": req.urgency,
        "timestamp": datetime.now().isoformat(),
    }


def calculate_milestone_progress(
    current_value: Decimal,
    target_value: Decimal,
    milestone_name: str,
    target_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Computes visual milestone progress ratio, remaining deficit, and on-track status.
    """
    if target_value <= Decimal("0"):
        raise ValueError("Target value must be greater than zero.")

    pct_complete = min(Decimal("100.0"), ((current_value / target_value) * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    ))
    remaining_deficit = max(Decimal("0.00"), target_value - current_value)

    return {
        "milestone_name": milestone_name,
        "current_value": current_value,
        "target_value": target_value,
        "percentage_complete": pct_complete,
        "remaining_deficit": remaining_deficit,
        "is_achieved": current_value >= target_value,
        "target_date": target_date.isoformat() if target_date else None,
    }
