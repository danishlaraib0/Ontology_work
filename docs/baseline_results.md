# Baseline and Verification Results: Automotive World Model

## Overview
This document records empirical baseline results, test execution outputs, and regression fixtures across all components of the Automotive Decision Platform.

---

## 1. Test Suite Results

```text
Ran 41 tests in 53.272s
OK
```

### Breakdown by Module:
1. `evaluation/test_fit_scoring.py`: 4 tests passed.
   - Persona weight calculations, vehicle satisfaction aggregation, ranking consistency.
2. `evaluation/test_intelligence_engine.py`: 6 tests passed.
   - Change detection deduplication, impact path traversal, cross-domain evidence harvesting, causal synthesis.
3. `evaluation/test_predictive_engine.py`: 8 tests passed.
   - Historical time series audit, model comparison (Naive, SMA-3, Holt Linear Trend), rolling-origin backtesting, forecast interval calibration.
4. `evaluation/test_dynamic_query.py`: 5 tests passed.
   - Multi-tier query planning, read-only Cypher safety validator, parameterized tool execution, category gap analysis.
5. `evaluation/validate_world_model.py`: 6 tests passed.
   - Schema constraints, foreign key referential integrity, temporal validity periods, graph connectivity.
6. `evaluation/test_decision_system.py`: 12 tests passed.
   - Typed contracts validation, deterministic pricing scenario arithmetic ($Q_1 = Q_0(P_1/P_0)^\epsilon$), RBAC authorization, policy approval gate, invalid state transition rejection, connector allowlisting, action execution idempotency, and outcome tracking error evaluation.

---

## 2. Query Planner Benchmark Evaluation

Evaluation over the 7 canonical benchmark queries from `evaluation/benchmark_query_planner.py`:

| ID | Query | Intent | Tool | Safety | Evidence | Latency | Planner Tier | Verdict |
|---|---|---|---|---|---|---|---|---|
| TC-01 | Compare Dzire and Amaze on safety and price. | SPEC_FEATURE_COMPARE | vehicle_spec_compare | SAFE | FULL | 3652.4 ms | RULE_FASTPATH | **PASSED** |
| TC-02 | Which vehicles compete with Dzire for family buyers? | AUDIENCE_FIT | audience_fit | SAFE | FULL | 9830.7 ms | RULE_FASTPATH | **PASSED** |
| TC-03 | What changed in the market over the last six months? | MARKET_CHANGE_INVESTIGATION | market_change_tracer | SAFE | FULL | 3552.7 ms | RULE_FASTPATH | **PASSED** |
| TC-04 | Which competitors are most vulnerable if Dzire cuts its price? | COMPETITOR_VULNERABILITY | competitor_vulnerability | SAFE | FULL | 2497.1 ms | RULE_FASTPATH | **PASSED** |
| TC-05 | Show the evidence connecting customer search intent to sales. | CORRELATION_ANALYSIS | evidence_correlator | SAFE | FULL | 2388.3 ms | RULE_FASTPATH | **PASSED** |
| TC-06 | If the Amaze reduces its price by 5%, which segments affected? | COMPETITOR_VULNERABILITY | competitor_vulnerability | SAFE | FULL | 3268.6 ms | RULE_FASTPATH | **PASSED** |
| TC-07 | Rank the best cars for High-Mileage Gig Workers. | AUDIENCE_FIT | audience_fit | SAFE | FULL | 12158.2 ms | RULE_FASTPATH | **PASSED** |

**Summary**: 100.0% Pass Rate (7/7 passed), 100% Schema & Read-Only Safety Compliance, 100% Tool Routing Accuracy.

---

## 3. Canonical Strategic Decision Execution Verification

### Canonical Test Query:
*"Should Hyundai reduce Aura's price to compete with Dzire, which customer segments would be affected, and what would happen under different pricing scenarios?"*

1. **Intent & Planning**:
   - Resolved Intent: `DECISION_RECOMMENDATION`
   - Tool: `decision_engine`
   - Target Vehicle: `Aura` | Rival: `Dzire`
2. **Empirical Baseline Evidence**:
   - Aura Base Price: ₹600,000 | Avg Monthly Sales: 18,153 units
   - Dzire Base Price: ₹630,600 | Avg Monthly Sales: 28,932 units
   - Competition Intensity: 0.90 | Price Overlap: 85%
3. **Deterministic Scenarios (Elasticity $\epsilon = -0.90$)**:
   - Status Quo (₹600,000): 18,153 units, ₹1,089.18 Cr revenue
   - Moderate Repositioning (-3%, ₹582,000): 18,657 units (+505 units/mo), ₹1,085.87 Cr revenue (-₹3.31 Cr)
   - Aggressive Volume Parity (-5%, ₹570,000): 19,011 units (+858 units/mo), ₹1,083.61 Cr revenue (-₹5.57 Cr)
   - Premium Positioning (+5%, ₹630,000): 17,373 units (-780 units/mo), ₹1,094.51 Cr revenue (+₹5.33 Cr)
4. **Impacted Customer Segments (Neo4j Traversal)**:
   - Young Urban Professionals, Practical Family Men, Commercial Fleet Operators, Small Business Upgraders.
5. **Governance & Approval Lifecycle**:
   - Unauthorized attempts by `read_only` principal blocked with: `User lacks Permission.APPROVE_DECISION`.
   - Approved by `executive` role with signed reason.
6. **Action Execution & Idempotency**:
   - Action Proposal: `ACT_DEC_AURA_20261011_043436_PRICE_PROPOSAL`
   - Executed through authorized connector: `INTERNAL_PRICING_CATALOG`
   - Re-execution attempt safely recognized idempotency key `IDEMP_DEC_AURA_20261011_043436_ALT_02_COMPETITIVE_CUT` and returned existing execution record without side effects.
7. **Closed-Loop Outcome Tracking**:
   - Actual Siam Dispatches recorded: 18,600 units
   - Expected volume: 18,657 units
   - Realized Prediction Error: 0.3%
   - Verdict: `MET_EXPECTATION`
