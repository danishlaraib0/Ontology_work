# 🌐 Automotive World Ontology — Neo4j Graph Database Guide

This system transforms the 12-layer normalized vehicle intelligence datasets into a **Typed Property Graph (TPG)** in **Neo4j**, connecting **Products**, **Customers**, **Opinions**, **Search Behaviors**, and **Commercial Dynamics** into a unified intelligence graph.

---

## 🏗️ Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTOMOTIVE WORLD ONTOLOGY                            │
└─────────────────────────────────────────────────────────────────────────────┘

                    PRODUCT DOMAIN
                         │
       ┌─────────────────┼──────────────────┐
       ↓                 ↓                  ↓
     Brand          VehicleModel        VehicleSegment
                         │
                ┌────────┼────────┐
                ↓        ↓        ↓
            Generation  Variant  Platform
                         │
             ┌───────────┼──────────────┐
             ↓           ↓              ↓
          Powertrain   Feature      PriceObservation
             │
        ┌────┼────┐
        ↓    ↓    ↓
      Engine Fuel Transmission


                    CUSTOMER DOMAIN
                         │
                  CustomerSegment
                    /     |      \
                   /      |       \
                  ↓       ↓        ↓
               Need  BuyingFactor  Intent
                  \       /
                   \     /
                    ↓   ↓
                  Feature


                 OPINION / BEHAVIOR
                         │
          ┌──────────────┼───────────────┐
          ↓              ↓               ↓
       Review         SearchQuery      Opinion
          │              │               │
          │              ↓               ↓
          │           Intent          Aspect
          │                              │
          └──────────────────────────────┘
                         │
                    PurchaseImpact
                  /                 \
             Driver                Barrier


                 MARKET / COMMERCIAL
                         │
              ┌──────────┼──────────┐
              ↓          ↓          ↓
           Geography   SalesObs   PriceObs
                         │
                         ↓
                  CompetitorRelation
```

---

## 📋 Node Schema (23 Core Entity Labels)

| Domain | Label | Key Property | Key Attributes |
|---|---|---|---|
| **Product** | `Brand` | `brand_id` | `name`, `country_of_origin` |
| **Product** | `VehicleModel` | `vehicle_model_id` | `name`, `brand_id`, `body_type`, `segment_position`, `launch_year`, `status` |
| **Product** | `Generation` | `generation_id` | `name`, `generation_number`, `start_year`, `platform` |
| **Product** | `VehicleVariant` | `variant_id` | `name`, `fuel_type`, `transmission`, `is_top_trim` |
| **Product** | `VehicleSegment` | `segment_id` | `name`, `category` |
| **Product** | `Platform` | `platform_id` | `name`, `architecture_type` |
| **Product** | `Powertrain` | `powertrain_id` | `powertrain_type`, `claimed_efficiency` |
| **Product** | `Engine` | `engine_id` | `code`, `displacement_cc`, `max_power_hp`, `max_torque_nm` |
| **Product** | `FeatureCategory`| `category_id` | `name`, `pillar` |
| **Product** | `Feature` | `feature_id` | `name`, `category_id`, `is_standard` |
| **Customer**| `CustomerSegment`| `segment_id` | `name`, `description`, `age_band`, `income_band_inr_annual`, `gender_skew`, `first_car_buyer`, `avg_daily_km`, `budget_band_inr`, `segment_weight_percent` |
| **Customer**| `Need` | `need_id` | `name`, `category`, `description` |
| **Customer**| `BuyingFactor` | `factor_id` | `name`, `category` |
| **Opinion** | `Review` | `review_id` | `source_name`, `source_type`, `overall_rating`, `verdict` |
| **Opinion** | `Opinion` | `opinion_id` | `claim`, `sentiment`, `sentiment_score`, `intensity`, `aspect_name`, `is_purchase_driver`, `is_purchase_barrier` |
| **Opinion** | `Aspect` | `aspect_id` | `name`, `category` |
| **Behavior**| `SearchQuery` | `query_id` | `query_text`, `intent_type`, `purchase_stage`, `search_volume_tier` |
| **Behavior**| `Intent` | `intent_id` | `intent_type`, `stage` |
| **Market**  | `Geography` | `geography_id` | `name`, `geo_level`, `country_code` |
| **Commercial**|`SalesObservation`| `sales_obs_id`| `period_type`, `period_value`, `units_sold`, `market_share_percent`, `confidence_level` |
| **Commercial**|`PriceObservation`| `price_obs_id`| `date`, `ex_showroom_inr`, `currency`, `market_region` |
| **Provenance**|`Source` | `source_id` | `name`, `source_type`, `url` |
| **Provenance**|`Evidence` | `evidence_id` | `claim_text`, `confidence_score`, `observed_date` |

---

## 🔗 Key Relationships (25 Types)

- `(:Brand)-[:PRODUCES]->(:VehicleModel)`
- `(:VehicleModel)-[:HAS_GENERATION]->(:Generation)`
- `(:VehicleModel)-[:HAS_VARIANT]->(:VehicleVariant)`
- `(:VehicleModel)-[:BELONGS_TO]->(:VehicleSegment)`
- `(:VehicleModel)-[:USES_PLATFORM]->(:Platform)`
- `(:VehicleModel)-[:HAS_POWERTRAIN]->(:Powertrain)`
- `(:VehicleVariant)-[:USES_ENGINE]->(:Engine)`
- `(:VehicleVariant)-[:HAS_FEATURE]->(:Feature)`
- `(:FeatureCategory)-[:CONTAINS_FEATURE]->(:Feature)`
- `(:Feature)-[:SATISFIES]->(:Need)`
- `(:CustomerSegment)-[:PRIORITIZES {importance_weight: 0.90}]->(:BuyingFactor)`
- `(:CustomerSegment)-[:CONSIDERS]->(:VehicleModel)`
- `(:VehicleModel)-[:COMPETES_WITH {competition_score: 0.88, price_overlap: 0.90, customer_overlap: 0.85}]->(:VehicleModel)`
- `(:Review)-[:ABOUT]->(:VehicleModel)`
- `(:Review)-[:CONTAINS]->(:Opinion)`
- `(:Opinion)-[:ABOUT_ASPECT]->(:Aspect)`
- `(:Opinion)-[:EXPRESSED_BY]->(:CustomerSegment)`
- `(:SearchQuery)-[:TARGETS]->(:VehicleModel)`
- `(:SearchQuery)-[:HAS_INTENT]->(:Intent)`
- `(:VehicleModel)-[:HAS_SALES_OBSERVATION]->(:SalesObservation)`
- `(:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(:PriceObservation)`

---

## 🚀 Quickstart & Execution

### 1. Launch Local Neo4j (Docker)
```bash
docker compose up -d
```
> Neo4j Browser UI will be available at: `http://localhost:7474` (User: `neo4j`, Password: `password`)

### 2. Ingest Datasets into Neo4j
```bash
# Initialize constraints and ingest all collected vehicle layers
python load_graph.py --init
python load_graph.py --load
```

### 3. Generate Standalone Cypher Script
```bash
python load_graph.py --export
```
This generates `graph_export.cypher`, which you can copy and paste directly into any Neo4j instance or execute via `cypher-shell`.

### 4. Graph Traversals & Analytics
```bash
# 1. Why is Wagon R popular among small urban families?
python load_graph.py --why "Wagon R" --audience "Family"

# 2. Compare Wagon R vs Tata Tiago
python load_graph.py --compare "Wagon R" "Tiago"

# 3. 360-Degree Profile for Dzire
python load_graph.py --summary "Dzire"
```

---

## 💡 Example Cypher Queries

### 1. The Magic Traverse: Why does an audience buy a vehicle?
```cypher
MATCH (s:CustomerSegment)-[:CONSIDERS]->(v:VehicleModel {name: 'Wagon R'})
MATCH (s)-[p:PRIORITIZES]->(bf:BuyingFactor)
MATCH (v)-[:HAS_VARIANT]->(var:VehicleVariant)-[:HAS_FEATURE]->(f:Feature)
MATCH (v)<-[:ABOUT]-(r:Review)-[:CONTAINS]->(op:Opinion)-[:ABOUT_ASPECT]->(asp:Aspect)
WHERE op.sentiment = 'POSITIVE'
RETURN s.name AS Audience, bf.name AS Priority, f.name AS Feature, asp.name AS Aspect, op.claim AS Sentiment
LIMIT 10;
```

### 2. Multi-Dimensional Competitor Overlap
```cypher
MATCH (v1:VehicleModel {name: 'Wagon R'})-[c:COMPETES_WITH]->(v2:VehicleModel)
RETURN v1.name, v2.name, c.competition_score, c.price_overlap, c.customer_overlap, c.key_battleground
ORDER BY c.competition_score DESC;
```
