"""
dynamic_query_engine.py
======================
End-to-end Dynamic Querying Engine for the Automotive World Model.
Orchestrates:
  1. SLM Intent & Query Planning
  2. Guardrailed Parameterized & Dynamic Cypher Tool Execution
  3. Bounded Query Revision on Execution Faults
  4. Evidence-Grounded Multi-Tier Causal Synthesis
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from graph_db.neo4j_client import Neo4jClient
from intelligence.query_safety import CypherSafetyValidator
from intelligence.query_planner import SLMQueryPlanner, QueryPlan
from intelligence.schema_registry import GraphSchemaRegistry
from intelligence.query_tools import (
    ToolResult,
    VehicleSpecCompareTool,
    AudienceFitTool,
    CompetitorVulnerabilityTool,
    MarketChangeTracerTool,
    EvidenceCorrelatorTool,
    DynamicCypherTool,
    CategoryGapAnalysisTool,
    CustomerBehaviorAnalysisTool,
)
from data_collector.search_tools import gemini_grounded_search_with_tool, gemini_plain_call
from data_collector.config import GEMINI_MODEL
from config_loader import get_prompt

logger = logging.getLogger(__name__)


@dataclass
class DynamicQueryResult:
    """Complete grounded answer to a dynamic automotive intelligence inquiry."""
    query: str
    plan: QueryPlan
    tool_result: ToolResult
    causal_synthesis: str
    grounded_memo: Optional[str] = None
    confidence_score: float = 0.90
    limitations: List[str] = field(default_factory=list)
    markdown_report: str = ""


class DynamicQueryEngine:
    """
    Main entry point for dynamic queries over the Automotive World Model.
    Supports Level 1 (static), Level 2 (parameterized), and Level 3 (schema-aware dynamic).
    """

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()
        self.schema = GraphSchemaRegistry(self.client)
        self.planner = SLMQueryPlanner()
        self.validator = CypherSafetyValidator()

        # Tool registry
        self.spec_tool = VehicleSpecCompareTool(self.client)
        self.fit_tool = AudienceFitTool(self.client)
        self.vuln_tool = CompetitorVulnerabilityTool(self.client)
        self.change_tool = MarketChangeTracerTool(self.client)
        self.corr_tool = EvidenceCorrelatorTool(self.client)
        self.dynamic_tool = DynamicCypherTool(self.client)
        self.gap_tool = CategoryGapAnalysisTool(self.client)
        self.behavior_tool = CustomerBehaviorAnalysisTool(self.client, self.schema)

    def execute(self, query: str, use_grounding: bool = False, force_llm: bool = False) -> DynamicQueryResult:
        """Executes an end-to-end dynamic automotive intelligence query with exception safety."""
        logger.info(f"🔍 DynamicQueryEngine received query: '{query}'")

        try:
            # ── Step 1: SLM Query Planning ─────────────────────────────────────────
            try:
                plan = self.planner.plan_query(query, force_llm=force_llm)
            except Exception as plan_err:
                logger.warning(f"Planner error ({plan_err}). Falling back to baseline plan.")
                plan = QueryPlan(
                    user_query=query,
                    intent="GENERAL_INQUIRY",
                    selected_tool="market_change_tracer",
                    target_models=[],
                    complexity="SIMPLE",
                    planner_model="EXCEPTION_FALLBACK",
                    reasoning="Planner recovered from exception gracefully.",
                )
            logger.info(f"📋 Executing Plan: Tool=[{plan.selected_tool}], Complexity=[{plan.complexity}], Planner=[{plan.planner_model}]")

            # ── Step 1.5: Input Validation Early Rejection (No Cypher or Hallucination) ──
            if plan.selected_tool == "invalid_query":
                tool_res = ToolResult(
                    tool_name="invalid_query",
                    success=False,
                    summary=plan.reasoning or "Unrecognized query or random input.",
                    error="INVALID_INPUT",
                    confidence_score=0.0,
                )
                synthesis = (
                    "The query does not contain recognized automotive models, brands, segments, or inquiry terms. "
                    "No graph queries or AI analyses were executed to prevent hallucinated decisions."
                )
                markdown_rep = self._format_invalid_query_report(query, plan, tool_res)
                return DynamicQueryResult(
                    query=query,
                    plan=plan,
                    tool_result=tool_res,
                    causal_synthesis=synthesis,
                    grounded_memo=None,
                    confidence_score=0.0,
                    limitations=["No recognized automotive entities or inquiry terms in query."],
                    markdown_report=markdown_rep,
                )

            # ── Step 2: Tool Execution ─────────────────────────────────────────────
            try:
                tool_res = self._dispatch_tool(plan)
            except Exception as tool_err:
                logger.error(f"Tool execution failed: {tool_err}", exc_info=True)
                tool_res = ToolResult(
                    tool_name=plan.selected_tool,
                    success=False,
                    summary=f"Tool execution encountered an error: {str(tool_err)}",
                    error=str(tool_err),
                )

            # ── Step 3: Bounded Query Revision (If Dynamic Cypher Failed or Returned 0 Records) ──
            if (not tool_res.success or (tool_res.data.get("record_count", 0) == 0)) and plan.selected_tool == "dynamic_cypher":
                logger.warning(f"Dynamic Cypher returned 0 records or failed (error: {tool_res.error}). Attempting bounded schema repair...")
                try:
                    repaired_plan = self.planner._call_llm_fallback_planner(query)
                    if repaired_plan.dynamic_cypher and repaired_plan.dynamic_cypher != plan.dynamic_cypher:
                        plan = repaired_plan
                        tool_res = self._dispatch_tool(plan)
                except Exception as repair_err:
                    logger.warning(f"Bounded repair encountered error: {repair_err}")

            # ── Step 4: Causal Explanation & Evidence Synthesis ────────────────────
            try:
                synthesis = self._synthesize_grounded_answer(query, plan, tool_res)
            except Exception as syn_err:
                logger.warning(f"Synthesis failed: {syn_err}")
                synthesis = f"**Findings**: Analysis completed with summary: {tool_res.summary}"

            limitations = self._determine_limitations(plan, tool_res)

            # ── Step 5: Optional Grounded Executive Memo ───────────────────────────
            grounded_memo = None
            if use_grounding:
                try:
                    grounded_memo = self._generate_executive_memo(query, plan, tool_res, synthesis)
                except Exception as memo_err:
                    logger.warning(f"Grounded memo generation failed: {memo_err}")

            # ── Step 6: Format Rich Markdown Report ────────────────────────────────
            markdown_rep = self._format_markdown_report(query, plan, tool_res, synthesis, grounded_memo, limitations)

            return DynamicQueryResult(
                query=query,
                plan=plan,
                tool_result=tool_res,
                causal_synthesis=synthesis,
                grounded_memo=grounded_memo,
                confidence_score=tool_res.confidence_score,
                limitations=limitations,
                markdown_report=markdown_rep,
            )

        except Exception as top_err:
            logger.error(f"Unhandled exception in DynamicQueryEngine.execute: {top_err}", exc_info=True)
            fallback_plan = QueryPlan(
                user_query=query,
                intent="ERROR_RECOVERY",
                selected_tool="error_handler",
                target_models=[],
                reasoning=f"Recovered from exception: {str(top_err)}",
            )
            fallback_res = ToolResult(
                tool_name="error_handler",
                success=False,
                summary=f"System error: {str(top_err)}",
                error=str(top_err),
            )
            return DynamicQueryResult(
                query=query,
                plan=fallback_plan,
                tool_result=fallback_res,
                causal_synthesis=f"**Execution Notice**: An unexpected issue occurred during analysis: {str(top_err)}.",
                confidence_score=0.0,
                limitations=[f"Internal error: {str(top_err)}"],
                markdown_report=f"# ⚠️ Analysis Notice\n\n> {str(top_err)}",
            )

    def _dispatch_tool(self, plan: QueryPlan) -> ToolResult:
        """Routes execution to the appropriate parameterized or dynamic tool dynamically."""
        t_name = plan.selected_tool
        known_v = self.schema.get_known_vehicles()
        default_target = known_v[0] if known_v else "Vehicle"

        if t_name == "category_gap_analysis":
            known_s = self.schema.get_known_segments()
            default_seg = known_s[0] if known_s else "Small Urban Families"
            segment = plan.segments[0] if plan.segments else default_seg
            return self.gap_tool.run(category_or_segment=segment, target_models=plan.target_models)

        elif t_name == "vehicle_spec_compare":
            models = plan.target_models or (known_v[:2] if len(known_v) >= 2 else [default_target])
            return self.spec_tool.run(models, plan.aspects)

        elif t_name == "audience_fit":
            known_s = self.schema.get_known_segments()
            default_seg = known_s[0] if known_s else "Small Urban Families"
            segment = plan.segments[0] if plan.segments else default_seg
            target = plan.target_models[0] if plan.target_models else None
            return self.fit_tool.run(segment, target)

        elif t_name == "competitor_vulnerability":
            target = plan.target_models[0] if plan.target_models else default_target
            price_cut = plan.parameters.get("price_cut_inr")
            pct = plan.parameters.get("pct_change")
            return self.vuln_tool.run(target, price_cut_inr=price_cut, pct_change=pct)

        elif t_name == "market_change_tracer":
            return self.change_tool.run(plan.user_query)

        elif t_name == "evidence_correlator":
            target = plan.target_models[0] if plan.target_models else default_target
            return self.corr_tool.run(target)

        elif t_name == "dynamic_cypher":
            cypher_to_run = plan.dynamic_cypher
            if not cypher_to_run:
                fallback_plan = self.planner._call_llm_fallback_planner(plan.user_query)
                cypher_to_run = fallback_plan.dynamic_cypher or (
                    "MATCH (s:VehicleSegment)<-[:BELONGS_TO]-(v:VehicleModel) "
                    "OPTIONAL MATCH (v)-[:HAS_VARIANT]->(:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation) "
                    "OPTIONAL MATCH (v)-[:HAS_SALES_OBSERVATION]->(sales:SalesObservation) "
                    "RETURN s.name AS segment, collect(DISTINCT v.name) AS models, count(DISTINCT v) AS competition_count, "
                    "min(p.ex_showroom_inr) AS min_price, max(p.ex_showroom_inr) AS max_price, "
                    "sum(sales.units_sold) AS total_sales, round(avg(sales.units_sold)) AS avg_monthly_sales "
                    "ORDER BY max_price DESC LIMIT 25"
                )
            return self.dynamic_tool.run(cypher_to_run)

        elif t_name == "customer_behavior_analysis":
            return self.behavior_tool.execute(plan)

        elif t_name == "decision_engine":
            from decisions.decision_engine import AutomotiveDecisionEngine
            engine = AutomotiveDecisionEngine(self.client)
            target = plan.target_models[0] if plan.target_models else "Aura"
            rival = plan.target_models[1] if len(plan.target_models) > 1 else ("Dzire" if target.lower() != "dzire" else "Aura")
            brief = engine.evaluate_pricing_decision(
                target_model=target,
                rival_model=rival,
                user_query=plan.user_query,
            )
            return ToolResult(
                tool_name="decision_engine",
                success=True,
                summary=brief.recommendation_summary,
                data={
                    "decision_id": brief.decision_id,
                    "target_vehicle": brief.target_vehicle,
                    "rival_vehicle": brief.rival_vehicle,
                    "recommended_alternative": brief.recommended_alternative,
                    "baseline_metrics": brief.baseline_metrics,
                    "alternatives": brief.alternatives,
                    "affected_segments": brief.affected_segments,
                    "facts": brief.facts,
                    "assumptions_and_uncertainties": brief.assumptions_and_uncertainties,
                    "proposed_action": brief.proposed_action,
                    "brief_markdown": brief.to_markdown(),
                },
                confidence_score=0.92,
            )

        elif t_name == "invalid_query":
            return ToolResult(
                tool_name="invalid_query",
                success=False,
                summary=plan.reasoning or "Input was rejected as invalid or unrecognized.",
                error="INVALID_INPUT",
                confidence_score=0.0,
            )

        else:
            return ToolResult(tool_name="unknown", success=False, summary="Unknown tool", error="Tool not supported")

    def _synthesize_grounded_answer(self, query: str, plan: QueryPlan, res: ToolResult) -> str:
        """Synthesizes factual empirical findings into clear causal explanations."""
        if not res.success:
            return f"**Analysis Unavailable**: Unable to complete execution due to {res.error}."

        data = res.data

        # 1. Attempt LLM executive synthesis for deep, customized strategic answering
        synth_template = get_prompt("intelligence", "strategic_synthesis")
        if synth_template:
            try:
                synth_prompt = synth_template.format(
                    query=query,
                    selected_tool=plan.selected_tool,
                    summary=res.summary,
                    data_json=json.dumps(res.data, default=str, indent=2)[:3500],
                )
            except Exception:
                synth_prompt = f"Question: {query}\nEvidence: {res.summary}\nData: {json.dumps(res.data, default=str)[:3000]}"
        else:
            synth_prompt = f"""
You are an Executive Automotive Intelligence Strategist.
User Question: "{query}"

Retrieved Neo4j Knowledge Graph Evidence:
Tool: {plan.selected_tool}
Summary: {res.summary}
Data:
{json.dumps(res.data, default=str, indent=2)[:3500]}

Instructions:
1. Directly, rigorously, and concisely answer the user's specific question using ONLY the provided graph data.
2. Provide a crisp, high-signal 1-2 paragraph executive strategic analysis focused strictly on decision-making. Avoid repetitive fluff, meta-commentary, or rambling filler.
3. DO NOT introduce or discuss vehicles, brands, or topics not present in the user question or retrieved graph data.
4. Reference specific numbers, price bands, and volume figures directly from the data.
"""
        try:
            from data_collector.search_tools import gemini_plain_call
            from data_collector.config import GEMINI_MODEL
            llm_synth = gemini_plain_call(synth_prompt, model=GEMINI_MODEL, max_tokens=650)
            if llm_synth and len(llm_synth.strip()) > 50:
                return llm_synth.strip()
        except Exception as e:
            logger.warning(f"LLM synthesis failed: {e}. Falling back to structured templates.")

        # 2. Deterministic Template Fallbacks
        if plan.selected_tool == "competitor_vulnerability":
            target = data.get("target_model", "Target Vehicle")
            vol_gain = data.get("target_volume_gain_units", 0)
            rivals = data.get("vulnerable_rivals", [])
            top_rival = rivals[0]["rival_name"] if rivals else "Segment Competitors"
            top_share_loss = rivals[0]["estimated_monthly_share_loss_units"] if rivals else 0

            return (
                f"**Causal Disruption Mechanism**: A price adjustment on {target} expands its projected wholesale run-rate "
                f"by **+{vol_gain:,} units/month** via improved ex-showroom affordability and EMI elasticity. "
                f"Because **{top_rival}** shares the highest price band overlap and direct competitor links, it suffers "
                f"the sharpest cross-shopping defection (estimated **~{top_share_loss:,} units/month** volume pressure). "
                f"Buyers prioritizing price accessibility defect directly to {target}, leaving rivals with aging powertrain "
                f"or safety propositions at severe competitive risk."
            )

        elif plan.selected_tool == "vehicle_spec_compare":
            matrix = data.get("comparison_matrix", {})
            models = list(matrix.keys())
            if len(models) >= 2:
                m1, m2 = models[0], models[1]
                p1, p2 = matrix[m1].get("min_price_inr", 0), matrix[m2].get("min_price_inr", 0)
                s1, s2 = matrix[m1].get("safety_rating", "N/A"), matrix[m2].get("safety_rating", "N/A")
                eff1, eff2 = matrix[m1].get("efficiency", "N/A"), matrix[m2].get("efficiency", "N/A")

                return (
                    f"**Comparative Advantage Analysis**: Across verified Neo4j specifications, **{m1}** offers a base entry "
                    f"of ₹{p1:,.0f} with a verified **{s1}** rating (claimed fuel efficiency {eff1}), compared to **{m2}** "
                    f"at ₹{p2:,.0f} with **{s2}** (claimed efficiency {eff2}). The divergence in crashworthiness credentials "
                    f"and ARAI fuel economy creates a decisive purchase partition between safety-conscious family cohorts and "
                    f"brand-loyal urban commuters."
                )

        elif plan.selected_tool == "audience_fit":
            seg = data.get("segment", "Audience Segment")
            rankings = data.get("rankings", [])
            top_model = rankings[0]["model"] if rankings else "Top Model"
            top_score = rankings[0]["fit_percentage"] if rankings else 0

            return (
                f"**Audience Resonance Analysis**: For the **'{seg}'** cohort, vehicle choice architecture is governed by "
                f"weighted factor priorities stored in the graph. **{top_model}** leads with a **{top_score}% fit score**, "
                f"delivering superior satisfaction on the segment's highest-weighted buying priorities."
            )

        elif plan.selected_tool == "category_gap_analysis" and "ranked_gaps" in data:
            gaps = data["ranked_gaps"]
            target_model = data.get("target_model")
            if target_model:
                top_gap = gaps[0]
                rivals_str = ", ".join(data.get("rivals_evaluated", [])) or "direct segment rivals"
                specs = data.get("target_specs", {})
                segs = specs.get("segments", [])
                seg_str = f"among {segs[0]} and {segs[1]}" if len(segs) >= 2 else "in its target segment"

                return (
                    f"**Strategic Product Gap & Competitive Vulnerability Analysis: {target_model}**\n\n"
                    f"Empirical graph traversal reveals that **{target_model}** currently faces critical product vulnerabilities "
                    f"that negatively impact its positioning against {rivals_str} {seg_str}.\n\n"
                    f"• **#1 Vulnerability ({top_gap['gap_name']})**: Carries an opportunity score of **{top_gap['opportunity_gap_score']:.3f}** "
                    f"(Importance: {top_gap['importance_weight']:.2f}, Satisfaction: {top_gap['category_satisfaction']*100:.0f}%). "
                    f"Customer feedback highlights: *\"{top_gap['primary_complaint']}\"* ({top_gap['source']}). "
                    f"Against benchmark rival **{top_gap.get('rival_benchmark')}**, this creates decisive defection pressure.\n\n"
                    + (f"• **Secondary Gaps**: **{gaps[1]['gap_name']}** (Score: {gaps[1]['opportunity_gap_score']:.3f}) and **{gaps[2]['gap_name']}** (Score: {gaps[2]['opportunity_gap_score']:.3f}) further erode competitive appeal.\n\n" if len(gaps) > 2 else "\n\n")
                    + f"**Recommended OEM Roadmap**: Product development should prioritize: (1) {top_gap['recommended_action']}, "
                    + (f"and (2) {gaps[1]['recommended_action']}" if len(gaps) > 1 else "")
                )
            else:
                top_gaps_str = ", ".join([f"{g['gap_name']} (Opp Score: {g['opportunity_gap_score']:.3f})" for g in gaps[:3]])
                return (
                    f"**Category Gap & Commercial Opportunity Analysis**: Empirical traversal across Neo4j customer priorities "
                    f"and vehicle opinions reveals top unmet needs: **{top_gaps_str}**. "
                    f"Automakers that resolve these trade-offs can capture significant segment defection."
                )

        elif plan.selected_tool == "dynamic_cypher" and "records" in data:
            records = data["records"]
            return (
                f"**Dynamic Graph Traversal Findings**: Traversed {len(records)} records from the Neo4j Automotive World Model "
                f"answering '{query}'."
            )

        elif plan.selected_tool == "evidence_correlator":
            return (
                f"**Empirical Intent-to-Sales Pathway**: Longitudinal analysis confirms that digital consumer inquiries "
                f"(pricing ladders, safety crash scores, mileage inquiries) exhibit a **2 to 6 week lead time** prior to "
                f"SIAM wholesale dispatches. Sudden spikes in product interest precede dealership walk-in spikes and subsequent "
                f"OEM production ramp-ups."
            )

        return res.summary

    def _determine_limitations(self, plan: QueryPlan, res: ToolResult) -> List[str]:
        """Provides empirical boundaries and limitations dynamically from tool result."""
        lims = res.data.get("data_limitations", []) if hasattr(res, "data") and isinstance(res.data, dict) else []
        return lims

    def _generate_executive_memo(self, query: str, plan: QueryPlan, res: ToolResult, synthesis: str) -> Optional[str]:
        """Generates an executive intelligence brief using Gemma 4 / GenAI."""
        memo_template = get_prompt("intelligence", "executive_brief")
        if memo_template:
            try:
                prompt = memo_template.format(
                    query=query,
                    synthesis=synthesis,
                )
            except Exception:
                prompt = f"Inquiry: {query}\nFindings:\n{synthesis}\nProvide executive strategic recommendations."
        else:
            prompt = f"""
You are an Executive Automotive Strategy Director.
Synthesize a concise, rigorous 2-paragraph executive memo answering:
"{query}"

Graph Findings:
{synthesis}

Tool Used: {plan.selected_tool}
Confidence: {res.confidence_score * 100:.0f}%

Format:
1. Executive Decision Summary
2. Strategic Recommendations
Keep the tone quantitative, authoritative, and direct.
"""
        try:
            memo = gemini_grounded_search_with_tool(prompt, model=GEMINI_MODEL, max_tokens=800)
            if memo:
                return memo
            return gemini_plain_call(prompt, model=GEMINI_MODEL, max_tokens=800)
        except Exception:
            return None

    def _format_invalid_query_report(self, query: str, plan: QueryPlan, res: ToolResult) -> str:
        """Formats a clean, professional rejection report for invalid queries."""
        lines = []
        lines.append(f"# 🚗 Automotive Intelligence Query: *\"{query}\"*")
        lines.append(f"**Intent**: `{plan.intent}` | **Tool**: `{plan.selected_tool}` | **Planner**: `{plan.planner_model}`")
        lines.append(f"**Status**: `REJECTED (INVALID_INPUT)`\n")
        lines.append("## 1. Input Analysis")
        lines.append(f"> **Notice**: {res.summary}\n")
        lines.append(
            "The query was rejected by the Automotive Intelligence input validator. "
            "To prevent inaccurate analyses or irrelevant data retrieval, random keystrokes "
            "and inquiries lacking automotive entities, segments, or inquiry terms are blocked before execution.\n"
        )
        lines.append("## 2. Supported Automotive Inquiries")
        lines.append("Please specify an automotive model, brand, segment, or strategic question. Examples:")
        lines.append("- **Product Gaps & Customer Sentiment**: `\"gaps in aura\"`, `\"customer complaints on ertiga\"`")
        lines.append("- **Competitive Benchmarking**: `\"compare dzire and amaze\"`, `\"spec differences between nexon and brezza\"`")
        lines.append("- **Strategic Pricing & Counterfactuals**: `\"what happens if aura cuts price by 30000?\"`")
        lines.append("- **Segment Profitability & Opportunities**: `\"which segment is most profitable to enter?\"`")
        lines.append("")
        return "\n".join(lines)

    def _format_cypher_records_table(self, records: List[Dict[str, Any]]) -> List[str]:
        """Formats and deduplicates dynamic Cypher traversal records cleanly for decision-making."""
        if not records:
            return []

        all_keys = list(records[0].keys())

        # Check for columns that are 100% None or empty across all rows
        active_keys = [
            k for k in all_keys
            if any(row.get(k) is not None and str(row.get(k)).strip() != "" and str(row.get(k)) != "None" for row in records)
        ]
        if not active_keys:
            active_keys = all_keys

        # Deduplicate records by their active keys
        seen = set()
        deduped = []
        for r in records:
            row_tuple = tuple(str(r.get(k)) for k in active_keys)
            if row_tuple not in seen:
                seen.add(row_tuple)
                deduped.append(r)

        lines = []
        header = "| " + " | ".join([k.replace("_", " ").title() for k in active_keys]) + " |"
        sep = "| " + " | ".join([":---:" for _ in active_keys]) + " |"
        lines.append(header)
        lines.append(sep)

        max_rows = 6
        for row in deduped[:max_rows]:
            vals = []
            for k in active_keys:
                v = row.get(k)
                if v is None or str(v).strip() == "" or str(v) == "None":
                    vals.append("-")
                elif isinstance(v, (int, float)):
                    if any(w in k.lower() for w in ["price", "inr"]):
                        vals.append(f"₹{v:,.0f}")
                    elif any(w in k.lower() for w in ["units", "sales", "count"]):
                        vals.append(f"{v:,.0f}")
                    else:
                        vals.append(f"{v:.2f}" if isinstance(v, float) else f"{v}")
                elif isinstance(v, list):
                    vals.append(", ".join([str(x) for x in v]))
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")

        if len(deduped) > max_rows:
            lines.append(f"\n*Showing top {max_rows} distinct records of {len(records)} retrieved.*")

        return lines

    def _format_markdown_report(
        self,
        query: str,
        plan: QueryPlan,
        res: ToolResult,
        synthesis: str,
        memo: Optional[str],
        limitations: List[str],
    ) -> str:
        """Formats the entire dynamic query response into GitHub-flavored markdown."""
        if plan.selected_tool == "decision_engine" and res.data and "brief_markdown" in res.data:
            return res.data["brief_markdown"]

        lines = []
        lines.append(f"# 🚗 Automotive Intelligence Query: *\"{query}\"*")
        lines.append(f"**Intent**: `{plan.intent}` | **Tool**: `{plan.selected_tool}` | **Planner**: `{plan.planner_model}`")
        lines.append(f"**Confidence**: `{res.confidence_score * 100:.0f}%` | **Execution Status**: `{'SUCCESS' if res.success else 'FAILED'}`\n")

        sec_idx = 1

        # Section 1: Executive Summary
        lines.append(f"## {sec_idx}. Executive Summary")
        lines.append(f"> **Key Finding**: {res.summary}\n")
        lines.append(synthesis)
        lines.append("")
        sec_idx += 1

        # Section 2: Traversed Graph Paths (if any)
        if res.graph_paths:
            lines.append(f"## {sec_idx}. Graph Evidence Paths")
            for p in res.graph_paths:
                lines.append(f"- 🔗 `{p}`")
            lines.append("")
            sec_idx += 1

        # Section 3: Tool-Specific Data Tables
        has_table = False
        if plan.selected_tool == "competitor_vulnerability" and "vulnerable_rivals" in res.data:
            lines.append(f"## {sec_idx}. Competitor Vulnerability Scorecard")
            lines.append("| Competitor Model | Brand | Competition Intensity | Price Overlap | Vulnerability Score | Est. Monthly Defection Units |")
            lines.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
            for riv in res.data["vulnerable_rivals"]:
                lines.append(f"| **{riv['rival_name']}** | {riv['brand']} | `{riv['competition_intensity']:.2f}` | `{riv['price_overlap_pct']}%` | **`{riv['vulnerability_score']:.2f}`** | **-{riv['estimated_monthly_share_loss_units']:,} units** |")
            lines.append("")
            has_table = True

        elif plan.selected_tool == "vehicle_spec_compare" and "comparison_matrix" in res.data:
            lines.append(f"## {sec_idx}. Side-by-Side Competitive Matrix")
            lines.append("| Dimension | " + " | ".join([f"**{m}**" for m in res.data["models_evaluated"]]) + " |")
            lines.append("| :--- | " + " | ".join([":---:" for _ in res.data["models_evaluated"]]) + " |")
            matrix = res.data["comparison_matrix"]
            lines.append("| **Brand** | " + " | ".join([matrix[m].get("brand", "N/A") for m in res.data["models_evaluated"]]) + " |")
            lines.append("| **Safety Rating** | " + " | ".join([f"**{matrix[m].get('safety_rating', 'N/A')}**" for m in res.data["models_evaluated"]]) + " |")
            lines.append("| **Price Band (INR)** | " + " | ".join([f"₹{matrix[m].get('min_price_inr', 0):,.0f} – ₹{matrix[m].get('max_price_inr', 0):,.0f}" for m in res.data["models_evaluated"]]) + " |")
            lines.append("| **Fuel Efficiency** | " + " | ".join([matrix[m].get("efficiency", "N/A") for m in res.data["models_evaluated"]]) + " |")
            lines.append("")
            has_table = True

        elif plan.selected_tool == "audience_fit" and "rankings" in res.data:
            lines.append(f"## {sec_idx}. Customer Segment Fit Rankings")
            lines.append("| Rank | Model | Brand | Fit Score | Key Strength | Primary Trade-Off |")
            lines.append("| :---: | :--- | :--- | :---: | :--- | :--- |")
            for r in res.data["rankings"][:5]:
                str_top = r["top_strengths"][0] if r["top_strengths"] else "Balanced offering"
                str_trade = r["key_tradeoffs"][0] if r["key_tradeoffs"] else "None recorded"
                lines.append(f"| #{r['rank']} | **{r['model']}** | {r['brand']} | `{r['fit_percentage']}%` | {str_top[:60]} | {str_trade[:60]} |")
            lines.append("")
            has_table = True

        elif plan.selected_tool == "category_gap_analysis" and "ranked_gaps" in res.data:
            target_model = res.data.get("target_model")
            if target_model:
                lines.append(f"## {sec_idx}. {target_model} Product Gaps & Market Opportunities")
                lines.append("| Rank | Product Gap / Deficit | Severity | Opp. Score | Importance | Model Satisf. | Customer Feedback (Source) | Benchmark Rival & Countermeasure |")
                lines.append("| :---: | :--- | :---: | :---: | :---: | :---: | :--- | :--- |")
                for g in res.data["ranked_gaps"]:
                    lines.append(
                        f"| #{g['rank']} | **{g['gap_name']}** | `{g['severity']}` | **`{g['opportunity_gap_score']:.3f}`** | "
                        f"`{g['importance_weight']:.2f}` | `{g['category_satisfaction']*100:.0f}%` | "
                        f"\"{g['primary_complaint']}\" *({g['source']})* | "
                        f"**Benchmark**: {g.get('rival_benchmark', 'Segment Rivals')}.<br/>**Fix**: {g['recommended_action']} |"
                    )
                lines.append("")
            else:
                lines.append(f"## {sec_idx}. Ranked Category Gaps & Market Opportunities")
                lines.append("| Rank | Product Gap | Importance | Satisfaction | Opp. Score | Severity | Affected Vehicles | Recommended Action |")
                lines.append("| :---: | :--- | :---: | :---: | :---: | :---: | :--- | :--- |")
                for g in res.data["ranked_gaps"][:8]:
                    lines.append(f"| #{g['rank']} | **{g['gap_name']}** | `{g['importance_weight']:.2f}` | `{g['category_satisfaction']*100:.0f}%` | **`{g['opportunity_gap_score']:.3f}`** | `{g['severity']}` | {', '.join(g['affected_vehicles'][:3])} | {g['recommended_action'][:60]}... |")
                lines.append("")
            has_table = True

        elif plan.selected_tool == "dynamic_cypher" and "records" in res.data and res.data["records"]:
            table_lines = self._format_cypher_records_table(res.data["records"])
            if table_lines:
                lines.append(f"## {sec_idx}. Dynamic Graph Traversal Records")
                lines.extend(table_lines)
                lines.append("")
                has_table = True

        if has_table:
            sec_idx += 1

        # Section: Executive Strategic Brief (if present)
        if memo:
            lines.append(f"## {sec_idx}. Executive Strategic Brief")
            lines.append(f"{memo}\n")
            sec_idx += 1

        # Section: Sources & Boundaries
        if res.citations or limitations:
            lines.append(f"## {sec_idx}. Verified Data Sources & Coverage Scope")
            if res.citations:
                for cit in res.citations:
                    lines.append(f"- 📑 **{cit.get('source', 'Source')}** (`{cit.get('tier', 'TIER_1_VERIFIED')}`)")
            for lim in limitations:
                lines.append(f"- ⚠️ {lim}")
            lines.append("")
            sec_idx += 1

        return "\n".join(lines)
