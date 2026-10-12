"""
cypher_schema.py
================
Defines Neo4j Cypher DDL statements:
  • Uniqueness Constraints for all 23 Node Labels
  • Secondary Indexes for high-frequency queries
  • Full-Text Search Indexes
"""

CYPHER_CONSTRAINTS = [
    # --- Product Domain ---
    "CREATE CONSTRAINT brand_id_unique IF NOT EXISTS FOR (n:Brand) REQUIRE n.brand_id IS UNIQUE",
    "CREATE CONSTRAINT vehicle_model_id_unique IF NOT EXISTS FOR (n:VehicleModel) REQUIRE n.vehicle_model_id IS UNIQUE",
    "CREATE CONSTRAINT generation_id_unique IF NOT EXISTS FOR (n:Generation) REQUIRE n.generation_id IS UNIQUE",
    "CREATE CONSTRAINT variant_id_unique IF NOT EXISTS FOR (n:VehicleVariant) REQUIRE n.variant_id IS UNIQUE",
    "CREATE CONSTRAINT segment_id_unique IF NOT EXISTS FOR (n:VehicleSegment) REQUIRE n.segment_id IS UNIQUE",
    "CREATE CONSTRAINT platform_id_unique IF NOT EXISTS FOR (n:Platform) REQUIRE n.platform_id IS UNIQUE",
    "CREATE CONSTRAINT powertrain_id_unique IF NOT EXISTS FOR (n:Powertrain) REQUIRE n.powertrain_id IS UNIQUE",
    "CREATE CONSTRAINT engine_id_unique IF NOT EXISTS FOR (n:Engine) REQUIRE n.engine_id IS UNIQUE",
    "CREATE CONSTRAINT feature_category_id_unique IF NOT EXISTS FOR (n:FeatureCategory) REQUIRE n.category_id IS UNIQUE",
    "CREATE CONSTRAINT feature_id_unique IF NOT EXISTS FOR (n:Feature) REQUIRE n.feature_id IS UNIQUE",

    # --- Customer Domain ---
    "CREATE CONSTRAINT customer_segment_id_unique IF NOT EXISTS FOR (n:CustomerSegment) REQUIRE n.segment_id IS UNIQUE",
    "CREATE CONSTRAINT need_id_unique IF NOT EXISTS FOR (n:Need) REQUIRE n.need_id IS UNIQUE",
    "CREATE CONSTRAINT buying_factor_id_unique IF NOT EXISTS FOR (n:BuyingFactor) REQUIRE n.factor_id IS UNIQUE",

    # --- Opinion & Review Domain ---
    "CREATE CONSTRAINT review_id_unique IF NOT EXISTS FOR (n:Review) REQUIRE n.review_id IS UNIQUE",
    "CREATE CONSTRAINT opinion_id_unique IF NOT EXISTS FOR (n:Opinion) REQUIRE n.opinion_id IS UNIQUE",
    "CREATE CONSTRAINT aspect_id_unique IF NOT EXISTS FOR (n:Aspect) REQUIRE n.aspect_id IS UNIQUE",

    # --- Behavior & Intent Domain ---
    "CREATE CONSTRAINT query_id_unique IF NOT EXISTS FOR (n:SearchQuery) REQUIRE n.query_id IS UNIQUE",
    "CREATE CONSTRAINT intent_id_unique IF NOT EXISTS FOR (n:Intent) REQUIRE n.intent_id IS UNIQUE",

    # --- Market & Commercial Domain ---
    "CREATE CONSTRAINT geography_id_unique IF NOT EXISTS FOR (n:Geography) REQUIRE n.geography_id IS UNIQUE",
    "CREATE CONSTRAINT sales_obs_id_unique IF NOT EXISTS FOR (n:SalesObservation) REQUIRE n.sales_obs_id IS UNIQUE",
    "CREATE CONSTRAINT price_obs_id_unique IF NOT EXISTS FOR (n:PriceObservation) REQUIRE n.price_obs_id IS UNIQUE",

    # --- Provenance Domain ---
    "CREATE CONSTRAINT source_id_unique IF NOT EXISTS FOR (n:Source) REQUIRE n.source_id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS FOR (n:Evidence) REQUIRE n.evidence_id IS UNIQUE",

    # --- Intelligence & Dynamics Domain ---
    "CREATE CONSTRAINT market_change_id_unique IF NOT EXISTS FOR (n:MarketChange) REQUIRE n.change_id IS UNIQUE",

    # --- Predictive & Forecasting Domain ---
    "CREATE CONSTRAINT forecast_run_id_unique IF NOT EXISTS FOR (n:ForecastRun) REQUIRE n.run_id IS UNIQUE",
    "CREATE CONSTRAINT sales_prediction_id_unique IF NOT EXISTS FOR (n:SalesPrediction) REQUIRE n.prediction_id IS UNIQUE",
]

CYPHER_INDEXES = [
    "CREATE INDEX vehicle_model_name_idx IF NOT EXISTS FOR (n:VehicleModel) ON (n.name)",
    "CREATE INDEX variant_name_idx IF NOT EXISTS FOR (n:VehicleVariant) ON (n.name)",
    "CREATE INDEX feature_name_idx IF NOT EXISTS FOR (n:Feature) ON (n.name)",
    "CREATE INDEX customer_segment_name_idx IF NOT EXISTS FOR (n:CustomerSegment) ON (n.name)",
    "CREATE INDEX buying_factor_name_idx IF NOT EXISTS FOR (n:BuyingFactor) ON (n.name)",
    "CREATE INDEX need_name_idx IF NOT EXISTS FOR (n:Need) ON (n.name)",
    "CREATE INDEX aspect_name_idx IF NOT EXISTS FOR (n:Aspect) ON (n.name)",
    "CREATE INDEX opinion_sentiment_idx IF NOT EXISTS FOR (n:Opinion) ON (n.sentiment)",
    "CREATE INDEX query_intent_idx IF NOT EXISTS FOR (n:SearchQuery) ON (n.intent_type)",
    "CREATE INDEX query_stage_idx IF NOT EXISTS FOR (n:SearchQuery) ON (n.purchase_stage)",
    "CREATE INDEX price_obs_valid_from_idx IF NOT EXISTS FOR (n:PriceObservation) ON (n.valid_from)",
    "CREATE INDEX sales_obs_period_idx IF NOT EXISTS FOR (n:SalesObservation) ON (n.period_value)",
    "CREATE INDEX sales_obs_period_type_idx IF NOT EXISTS FOR (n:SalesObservation) ON (n.period_type)",
    "CREATE INDEX source_name_idx IF NOT EXISTS FOR (n:Source) ON (n.name)",
    "CREATE INDEX market_change_date_idx IF NOT EXISTS FOR (n:MarketChange) ON (n.date)",
    "CREATE INDEX market_change_type_idx IF NOT EXISTS FOR (n:MarketChange) ON (n.change_type)",
    "CREATE INDEX forecast_run_model_idx IF NOT EXISTS FOR (n:ForecastRun) ON (n.vehicle_model)",
    "CREATE INDEX sales_prediction_period_idx IF NOT EXISTS FOR (n:SalesPrediction) ON (n.target_period)",
]

CYPHER_FULLTEXT_INDEXES = [
    """
    CREATE FULLTEXT INDEX vehicleFullTextIdx IF NOT EXISTS
    FOR (n:VehicleModel|VehicleVariant|Feature|Aspect)
    ON EACH [n.name, n.description, n.summary]
    """,
    """
    CREATE FULLTEXT INDEX opinionClaimFullTextIdx IF NOT EXISTS
    FOR (n:Opinion|Review|Evidence)
    ON EACH [n.claim, n.verdict, n.claim_text]
    """,
]
