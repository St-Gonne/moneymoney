#!/usr/bin/env python3
"""
Comprehensive Test Runner for MoneyMoney Statement Ingestion Pipeline E2E Test Suite.
Executes all test tiers (Tiers 1-5), checks invariants, and generates feature coverage matrix.
"""
import sys
import os
import unittest
import time
from io import StringIO

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.tests.test_tier1_feature_coverage import TestTier1FeatureCoverage
from backend.tests.test_tier2_boundary_corner import TestTier2BoundaryCorner
from backend.tests.test_tier3_cross_feature import TestTier3CrossFeatureCombinations
from backend.tests.test_tier4_workloads import TestTier4RealWorldWorkloads
from backend.tests.test_tier5_adversarial import TestTier5AdversarialHardening
from backend.tests.test_tier6_milestones_and_concierge import TestTier6MilestonesAndConcierge



def run_tier(suite_class, tier_name: str) -> bool:
    suite = unittest.TestLoader().loadTestsFromTestCase(suite_class)
    count = suite.countTestCases()
    print(f"\n{'='*70}")
    print(f"▶ RUNNING {tier_name} ({count} test cases)")
    print(f"{'='*70}")
    runner = unittest.TextTestRunner(verbosity=1)
    start_t = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_t
    print(f"Result: {result.testsRun} run | {len(result.failures)} failures | {len(result.errors)} errors | {elapsed:.3f}s")
    return result.wasSuccessful(), result.testsRun, len(result.failures), len(result.errors)


def main():
    print("""
======================================================================
  MONEYMONEY FAMILY VAULT FINANCIAL STATEMENT INGESTION PIPELINE
           Comprehensive Multi-Tier E2E Test Suite
======================================================================
""")
    tiers = [
        (TestTier1FeatureCoverage, "TIER 1: Feature Coverage (>=5 per feature)"),
        (TestTier2BoundaryCorner, "TIER 2: Boundary & Corner Cases (Fail-Closed & Negative)"),
        (TestTier3CrossFeatureCombinations, "TIER 3: Cross-Feature Combinations & State Transitions"),
        (TestTier4RealWorldWorkloads, "TIER 4: Real-World Multi-Broker Family Workloads"),
        (TestTier5AdversarialHardening, "TIER 5: Adversarial Hardening & Forensic Integrity"),
        (TestTier6MilestonesAndConcierge, "TIER 6: Milestones, Concierge, Statement Gateway & RBAC Matrix"),
    ]

    all_passed = True
    total_run = 0
    total_failures = 0
    total_errors = 0

    for suite_class, name in tiers:
        passed, run_c, fail_c, err_c = run_tier(suite_class, name)
        total_run += run_c
        total_failures += fail_c
        total_errors += err_c
        if not passed:
            all_passed = False

    print("\n" + "="*70)
    print("                      TEST SUITE SUMMARY                      ")
    print("="*70)
    print(f"  Total Test Cases Executed : {total_run}")
    print(f"  Total Passed              : {total_run - total_failures - total_errors}")
    print(f"  Total Failures            : {total_failures}")
    print(f"  Total Errors              : {total_errors}")
    print(f"  Overall Status            : {'PASSED (100%)' if all_passed else 'FAILED'}")
    print("="*70 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
