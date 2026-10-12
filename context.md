# Automotive Product & Market Intelligence Ontology

## 1. Project Context

The goal is to build a large, general-purpose **Automotive Product &
Market Intelligence Ontology** that represents the automotive market as
an interconnected decision system.

The system is not intended to be only a chatbot, RAG system, or vehicle
recommender.

It should allow a product manager, strategy team, sales team, or
automotive executive to ask questions such as:

-   What customer expectations or unmet needs would a new vehicle
    address?
-   Which customer segments are most likely to buy a proposed vehicle?
-   Which existing vehicles would the new vehicle compete with?
-   Which existing products would it cannibalize?
-   What would happen to sales if we changed the price?
-   What happens if we add/remove a feature?
-   Which features have the highest impact on purchase intent?
-   What price-feature combination is likely to maximize demand or
    profit?
-   What market share could the vehicle capture?
-   Which competitors are most exposed?
-   Which variants should be launched?
-   How would a launch affect the existing product portfolio?
-   What should sales and marketing do next?

The central idea is:

> **Ontology = representation of the automotive world and its
> relationships.**
>
> **ML/statistical models = prediction of what will happen.**
>
> **Simulation/optimization = evaluation of what could happen under
> different decisions.**
>
> **LLM/agents = natural-language interface and orchestration layer.**

------------------------------------------------------------------------

# 2. Core Concept

The system should connect:

``` text
Customer Needs
      ↓
Customer Segments
      ↓
Vehicle Requirements
      ↓
Vehicle / Variant / Features
      ↓
Price / Offers / Financing
      ↓
Competitive Set
      ↓
Purchase Consideration
      ↓
Demand
      ↓
Sales
      ↓
Market Share
      ↓
Revenue / Margin
      ↓
Business Outcome
```

The ontology should also capture the feedback loop:

``` text
Market
  ↓
Customer Behavior
  ↓
Sales
  ↓
Observed Outcomes
  ↓
Model Updates
  ↓
Better Product Decisions
```

------------------------------------------------------------------------

# 3. Core Ontology Entities

## 3.1 Customer / Consumer

Represents an individual customer where permitted, or an anonymized
customer profile.

Important properties:

-   customer_id
-   age_band
-   income_band
-   location
-   household_size
-   occupation_segment
-   current_vehicle
-   owned_vehicle_history
-   preferred_brand
-   preferred_body_type
-   preferred_powertrain
-   budget
-   financing_preference
-   usage_pattern
-   purchase_history

Relationships:

``` text
Customer → owns → Vehicle
Customer → considers → Vehicle
Customer → prefers → Feature
Customer → belongs_to → CustomerSegment
Customer → generated → Intent
Customer → interacted_with → Dealer
Customer → completed → Purchase
```

------------------------------------------------------------------------

# 4. Customer Segment

Represents groups of customers with similar needs or behavior.

Examples:

-   First-time car buyers
-   Existing SUV owners
-   Premium upgraders
-   EV adopters
-   Fleet buyers
-   Urban families
-   Rural buyers
-   Performance-oriented customers
-   Price-sensitive customers
-   Technology-oriented customers

Properties:

-   segment_id
-   demographic characteristics
-   income range
-   geography
-   purchase frequency
-   price sensitivity
-   brand affinity
-   feature preferences
-   powertrain preference

Relationships:

``` text
CustomerSegment → has_need → CustomerNeed
CustomerSegment → prefers → Vehicle
CustomerSegment → sensitive_to → Price
CustomerSegment → responds_to → Feature
```

------------------------------------------------------------------------

# 5. Customer Need / Expectation

This is one of the most important ontology concepts.

Examples:

``` text
Safety
Low running cost
High mileage
Long EV range
Fast charging
Performance
Luxury
Technology
Space
7-seat capacity
Low maintenance
Reliability
Brand prestige
Off-road capability
Affordable ownership
```

Needs should be separated from features.

For example:

``` text
Need:
"Low running cost"

Potential features/products satisfying it:
- EV powertrain
- High fuel efficiency
- Regenerative braking
- Low maintenance schedule
```

This allows the system to answer:

> "Which customer needs does this new vehicle satisfy?"

------------------------------------------------------------------------

# 6. Vehicle Product Hierarchy

The ontology should distinguish:

``` text
Brand
  ↓
Model
  ↓
Generation
  ↓
Variant
  ↓
Configuration
```

Example:

``` text
Hyundai
  ↓
Creta
  ↓
Current Generation
  ↓
SX(O)
  ↓
Petrol Automatic
```

Properties may include:

-   price
-   body type
-   dimensions
-   engine
-   battery
-   range
-   transmission
-   power
-   torque
-   mileage
-   seating capacity
-   boot space
-   safety rating
-   ADAS
-   infotainment
-   connectivity
-   warranty
-   service interval

------------------------------------------------------------------------

# 7. Feature Ontology

Features should be modeled independently because they are important for
product optimization.

Examples:

``` text
ADAS
Sunroof
360° Camera
Ventilated Seats
Fast Charging
Large Battery
Third-row Seating
Premium Audio
Connected Car
Automatic Transmission
```

Relationships:

``` text
Vehicle → has_feature → Feature
Feature → satisfies → CustomerNeed
Feature → influences → PurchaseIntent
Feature → affects → Cost
Feature → differentiates → Vehicle
```

This enables questions such as:

> "Which features have the strongest relationship with purchase
> conversion in this segment?"

------------------------------------------------------------------------

# 8. Market / Geography

Represent:

``` text
Country
State
City
Region
Urban/Rural
Dealer Territory
Market Segment
```

Relationships:

``` text
Vehicle → sold_in → Geography
Customer → located_in → Geography
Dealer → operates_in → Geography
Demand → measured_in → Geography
```

This is important because vehicle demand is highly geographical.

Example:

``` text
EV demand in Delhi
≠
EV demand in Jaipur
≠
EV demand in Mumbai
```

------------------------------------------------------------------------

# 9. Competitor Ontology

Competitors should not simply be manually defined.

A vehicle can compete based on:

-   price
-   body type
-   segment
-   powertrain
-   size
-   feature overlap
-   customer overlap
-   purchase consideration overlap
-   geography
-   financing affordability

Relationship:

``` text
Vehicle A → competes_with → Vehicle B
```

The relationship should have a confidence/score:

``` text
competition_score = 0.87
```

and supporting reasons:

``` text
price_overlap = high
customer_overlap = high
feature_overlap = medium
segment_overlap = high
```

------------------------------------------------------------------------

# 10. Sales Ontology

Entities:

``` text
Lead
Opportunity
Dealer
Salesperson
Test Drive
Quotation
Booking
Order
Purchase
Cancellation
```

Relationships:

``` text
Customer → generated → Lead
Lead → interested_in → Vehicle
Lead → assigned_to → Salesperson
Customer → booked → TestDrive
Customer → purchased → Vehicle
Lead → converted_to → Sale
```

This provides the bridge between product interest and actual sales.

------------------------------------------------------------------------

# 11. Intent Ontology

Intent should be a first-class object.

Examples:

``` text
EXPLORE_VEHICLE
COMPARE_VEHICLES
CHECK_PRICE
CHECK_FEATURE
CHECK_FINANCE
CHECK_EXCHANGE
UPGRADE_VEHICLE
REPLACE_VEHICLE
SELECT_VARIANT
REQUEST_TEST_DRIVE
REQUEST_CALLBACK
PURCHASE
NEGOTIATE_PRICE
ANALYZE_PRODUCT
LAUNCH_PRODUCT
OPTIMIZE_PRICE
OPTIMIZE_FEATURES
ANALYZE_COMPETITION
FORECAST_SALES
ANALYZE_CANNIBALIZATION
```

For strategic users, intents could include:

``` text
LAUNCH_PRODUCT
ENTER_MARKET
TARGET_SEGMENT
IDENTIFY_UNMET_NEED
OPTIMIZE_PRODUCT
OPTIMIZE_VARIANT_MIX
OPTIMIZE_PRICE
FORECAST_DEMAND
ESTIMATE_MARKET_SHARE
ANALYZE_CANNIBALIZATION
ANALYZE_COMPETITOR_IMPACT
```

------------------------------------------------------------------------

# 12. Product Proposal / Hypothetical Vehicle

A critical component is the ability to model a vehicle that does not yet
exist.

Example:

``` yaml
vehicle_proposal:
  segment: mid_size_suv
  powertrain: ev
  price: 1500000
  range_km: 450
  seats: 5
  adas: level_2
  battery_kwh: 50
```

This object is connected to the existing ontology and passed to
prediction/simulation models.

This enables:

> "What happens if we launch this vehicle?"

------------------------------------------------------------------------

# 13. Decision / Scenario Ontology

A scenario represents a hypothetical decision.

Examples:

``` text
Scenario A:
Price = ₹15L
Range = 400 km

Scenario B:
Price = ₹17L
Range = 500 km

Scenario C:
Price = ₹16L
Range = 450 km
ADAS = Level 2
```

Each scenario can produce:

-   estimated demand
-   expected sales
-   market share
-   revenue
-   margin
-   cannibalization
-   competitor displacement
-   target segment penetration
-   probability of purchase

------------------------------------------------------------------------

# 14. Data Sources Required

The ontology itself is not the source of truth.

It should be populated and continuously updated from multiple data
sources.

## 14.1 Vehicle Product Catalog

Source types:

-   OEM websites
-   OEM brochures
-   official specifications
-   dealer catalogs
-   homologation/specification databases
-   automotive databases
-   product master data
-   internal PLM/PIM systems

Required data:

``` text
Brand
Model
Variant
Price
Body type
Engine
Power
Torque
Mileage
Battery
Range
Charging
Dimensions
Seating
Boot capacity
Safety
ADAS
Features
Warranty
```

Purpose:

**Build the vehicle and feature ontology.**

------------------------------------------------------------------------

# 15. Historical Sales Data

This is one of the most important datasets.

Potential sources:

-   OEM sales systems
-   dealer management systems
-   monthly registration data
-   industry sales reports
-   internal CRM
-   distributor/dealer data

Required fields:

``` text
date
vehicle
variant
dealer
geography
units_sold
revenue
discount
sales_channel
customer_segment
```

Purpose:

-   demand forecasting
-   market share
-   product performance
-   seasonality
-   geographic demand
-   cannibalization analysis

------------------------------------------------------------------------

# 16. Vehicle Registration Data

Useful external source:

-   Government vehicle registration databases
-   Transport authority datasets
-   Industry registration aggregators

Potential fields:

``` text
date
manufacturer
model
variant
fuel_type
vehicle_type
geography
registrations
```

Purpose:

-   estimate actual market demand
-   competitor sales
-   regional adoption
-   EV adoption
-   market share

This is especially useful when OEM internal sales data is unavailable.

------------------------------------------------------------------------

# 17. Customer / CRM Data

Potential sources:

-   CRM
-   dealership CRM
-   lead-management systems
-   website leads
-   mobile applications
-   call center
-   WhatsApp/chat
-   test-drive systems

Fields:

``` text
customer_id
lead_date
source
vehicle_interested
budget
location
intent
lead_stage
test_drive
quotation
booking
purchase
conversion
```

Purpose:

-   intent modeling
-   conversion prediction
-   sales funnel analysis
-   next-best-action
-   customer segmentation

------------------------------------------------------------------------

# 18. Conversational Data

This is particularly valuable for the proposed system.

Sources:

-   chatbot conversations
-   call-center transcripts
-   sales conversations
-   WhatsApp conversations
-   website search queries
-   voice assistants
-   dealer conversations

Example:

``` text
"I need a 7 seater"
"Need something under 15 lakh"
"EV range is important"
"Don't want expensive maintenance"
"Can I get an automatic?"
"How much EMI?"
"Can I exchange my Creta?"
```

From this data, extract:

``` text
Intent
Need
Constraint
Preference
Vehicle
Feature
Budget
Purchase stage
Objection
Competitor mention
```

Purpose:

**Build the Customer Need → Intent → Vehicle graph.**

------------------------------------------------------------------------

# 19. Pricing and Offers Data

Sources:

-   OEM pricing
-   dealer pricing
-   promotional campaigns
-   discounts
-   exchange bonuses
-   financing offers
-   seasonal offers

Fields:

``` text
vehicle
variant
MRP
selling_price
discount
exchange_bonus
finance_offer
interest_rate
campaign
date
geography
dealer
```

Purpose:

-   price elasticity
-   demand modeling
-   competitive pricing
-   offer effectiveness
-   revenue optimization

------------------------------------------------------------------------

# 20. Competitor Data

Sources:

-   competitor OEM websites
-   brochures
-   dealer data
-   automotive portals
-   industry reports
-   product announcements

Required:

``` text
competitor vehicle
price
segment
features
powertrain
dimensions
sales
market share
launch date
promotions
```

Purpose:

-   competitive mapping
-   product positioning
-   competitor impact analysis

------------------------------------------------------------------------

# 21. Customer Reviews and Social Data

Sources:

-   automotive review platforms
-   public reviews
-   social media
-   YouTube comments/transcripts
-   forums
-   public discussion platforms

Extract:

``` text
feature sentiment
complaints
desired features
purchase reasons
rejection reasons
competitor comparisons
quality issues
ownership experience
```

Example:

``` text
Customer says:
"Great car but mileage is poor."

Graph:

Vehicle
  → has_problem → Mileage
  → negative_sentiment → Mileage
```

This helps discover **unmet needs**.

------------------------------------------------------------------------

# 22. Search and Behavioral Data

Potential sources:

-   website search logs
-   Google search trends
-   OEM website events
-   configurator usage
-   product-page views
-   feature clicks
-   comparison events
-   abandoned bookings

Example:

``` text
User searches:
"best SUV under 20 lakh"
"ADAS SUV"
"EV range 500 km"
"7 seater automatic"
```

This reveals emerging customer demand before it necessarily appears in
sales data.

------------------------------------------------------------------------

# 23. Macroeconomic Data

Potential sources:

-   inflation
-   interest rates
-   fuel prices
-   electricity prices
-   disposable income
-   employment
-   GDP
-   regional economic indicators

Why:

Automotive demand is strongly affected by affordability.

For example:

``` text
Interest rate ↑
       ↓
EMI ↑
       ↓
Vehicle affordability ↓
       ↓
Demand ↓
```

------------------------------------------------------------------------

# 24. EV / Charging Infrastructure Data

For EV-focused analysis:

Sources:

-   charging station databases
-   government infrastructure data
-   charging networks
-   OEM data

Fields:

``` text
location
charger_type
power
availability
operator
charging_time
```

This allows:

``` text
Vehicle
  → range
  → charging_requirement

Customer
  → location

Infrastructure
  → charger availability
```

and supports questions such as:

> "Which cities are best suited for launching this EV?"

------------------------------------------------------------------------

# 25. Supply Chain / Manufacturing Data

For a complete product decision system:

Sources:

-   ERP
-   MES
-   PLM
-   supplier systems
-   inventory systems
-   procurement systems

Data:

``` text
component
supplier
cost
lead_time
capacity
inventory
production_capacity
factory
```

This matters because the theoretically best product may not be the
economically best product.

Example:

``` text
Feature X
→ increases customer demand
→ increases BOM cost
→ requires new supplier
→ increases lead time
→ reduces manufacturing capacity
```

The ontology can connect all of these.

------------------------------------------------------------------------

# 26. Financial Data

Sources:

-   finance/ERP
-   product costing
-   BOM costing
-   dealer margins
-   incentives
-   financing data

Required:

``` text
BOM cost
manufacturing cost
distribution cost
dealer margin
marketing cost
warranty cost
financing cost
selling price
gross margin
```

This enables:

> "Does this product maximize sales or profit?"

These are not always the same.

------------------------------------------------------------------------

# 27. Data Architecture

A practical architecture could look like:

``` text
                    DATA SOURCES
                         │
      ┌──────────────────┼──────────────────┐
      ↓                  ↓                  ↓
   Internal            External          Behavioral
      │                  │                  │
 ERP / CRM            Market data        Search
 Sales                Competitors        Chat
 Dealer               Reviews            Calls
 Product              Registrations      Web
      │                  │                  │
      └──────────────────┼──────────────────┘
                         ↓
                 Data Lake / Warehouse
                         ↓
                  Data Processing
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
       Structured Data          Unstructured
              ↓                     ↓
       Ontology Builder        LLM/NLP Extraction
              └──────────┬──────────┘
                         ↓
                  Automotive Ontology
                         ↓
       ┌─────────────────┼─────────────────┐
       ↓                 ↓                 ↓
    Analytics           ML            Knowledge/RAG
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ↓
                  Scenario Engine
                         ↓
                Decision Intelligence
```

------------------------------------------------------------------------

# 28. Models Required

The ontology alone will not answer sales-impact questions.

You need several model classes.

## Demand Forecasting

Predict:

``` text
vehicle demand
variant demand
regional demand
monthly sales
```

Potential models:

-   XGBoost
-   LightGBM
-   temporal models
-   hierarchical forecasting
-   TFT
-   probabilistic forecasting

------------------------------------------------------------------------

## Purchase Intent Model

Predict:

``` text
P(purchase | customer, vehicle, context)
```

Inputs:

-   customer segment
-   vehicle
-   price
-   features
-   interactions
-   competitor consideration
-   previous behavior

------------------------------------------------------------------------

## Price Elasticity Model

Estimate:

``` text
ΔDemand / ΔPrice
```

This is critical for:

> "What happens if we increase price from ₹15L to ₹16L?"

------------------------------------------------------------------------

## Cannibalization Model

Estimate:

``` text
New Product Sales
       ↓
Which existing products lose sales?
```

Example:

``` text
New SUV:
20K incremental sales

8K from competitors
7K from existing company products
5K new buyers
```

This is much more useful than simply forecasting 20K units.

------------------------------------------------------------------------

## Choice Model

A discrete choice model can estimate how customers select among
alternatives.

Potential approaches:

-   Multinomial logit
-   Nested logit
-   Mixed logit
-   ML choice models

Conceptually:

``` text
Customer
    ↓
Consideration Set
    ↓
Vehicle utility
    ↓
Purchase probability
```

This is particularly relevant for competitive vehicle analysis.

------------------------------------------------------------------------

# 29. The Final Decision Engine

The final system should support questions like:

### Product launch

> "What happens if we launch a ₹15L EV SUV with 450 km range?"

### Feature optimization

> "Is increasing range from 450 km to 500 km worth the additional cost?"

### Pricing

> "What is the optimal price between ₹14L and ₹18L?"

### Competition

> "Which competitors are most exposed?"

### Cannibalization

> "How much of our existing SUV sales will we cannibalize?"

### Customer needs

> "What are the largest unmet needs among Indian SUV buyers?"

### Market expansion

> "Which customer segment and geography should we target first?"

### Portfolio

> "Do we need another SUV between ₹12L and ₹15L?"

------------------------------------------------------------------------

# 30. The End-State

The ultimate system should let an executive ask:

> **"I want to launch a ₹15--18 lakh electric SUV in India. Tell me what
> customer need it should target, which segments are most attractive,
> what features we should prioritize, what competitors we will take
> share from, how much of our existing portfolio we will cannibalize,
> what price maximizes contribution margin, and what sales impact we
> should expect."**

The system then traverses:

``` text
Intent
  ↓
Customer Needs
  ↓
Customer Segments
  ↓
Market
  ↓
Competitive Vehicles
  ↓
Product Features
  ↓
Price
  ↓
Historical Sales
  ↓
Choice / Demand Models
  ↓
Cannibalization Model
  ↓
Scenario Simulation
  ↓
Revenue / Margin / Market Share
  ↓
Recommendation
```

This is the core vision:

> **Build an automotive world model where customer needs, products,
> competitors, prices, sales, and business outcomes are connected, and
> use predictive models + simulation on top of that world model to
> evaluate product decisions.**

The ontology is therefore the **shared context layer**, not the
prediction engine itself.

# 31. Audience Intelligence Layer

A major objective of the system is to answer not only:

> "What do people think about this vehicle?"

but also:

> "Who is this vehicle actually relevant to, why would they buy it, what
> prevents them from buying it, and how does that differ across audience
> segments?"

Audience Intelligence should therefore be a first-class part of the
ontology.

The initial system should focus on **general, aggregated audience
segments** rather than attempting to create invasive individual-level
profiles.

------------------------------------------------------------------------

## 31.1 Audience Dimensions

The system can initially segment audiences using broad dimensions such
as:

### Demographic

-   Age band
-   Household size
-   Life stage
-   Occupation category
-   Urban / semi-urban / rural
-   Geography

Example:

``` text
18-24
25-34
35-44
45-54
55+
```

### Financial / Affordability

Use ranges and derived affordability indicators rather than
unnecessarily precise personal financial information.

Examples:

-   Income band
-   Vehicle budget band
-   EMI affordability band
-   Down-payment capacity band
-   Financing preference
-   Price sensitivity
-   Total cost of ownership sensitivity

Example:

``` text
Budget:
< ₹8L
₹8-12L
₹12-15L
₹15-20L
₹20-30L
₹30L+
```

### Behavioral

-   Current vehicle ownership
-   Previous vehicle category
-   Replacement cycle
-   Purchase frequency
-   Brand loyalty
-   EV adoption propensity
-   Financing behavior
-   Test-drive behavior
-   Comparison behavior
-   Online research intensity

### Usage

-   Daily commute
-   Annual mileage
-   City usage
-   Highway usage
-   Family usage
-   Commercial usage
-   Long-distance travel
-   Off-road usage

------------------------------------------------------------------------

# 32. Buying Factor Ontology

The system should explicitly model **why people buy a vehicle**.

Buying factors can include:

``` text
Price
Safety
Mileage
Performance
Reliability
Brand
Design
Comfort
Technology
Features
Space
Seating capacity
Resale value
Maintenance cost
Fuel cost
EV range
Charging availability
Financing / EMI
After-sales service
Dealer proximity
Driving experience
Status / aspiration
```

Each buying factor should have relationships to:

``` text
Audience Segment
Vehicle
Feature
Intent
Purchase
Review
Competitor
```

For example:

``` text
Customer Segment
      ↓
highly_values
      ↓
Safety
      ↓
Vehicle Feature
      ↓
ADAS / airbags / crash rating
      ↓
Purchase Intent
```

------------------------------------------------------------------------

# 33. Buying Factor Weight

Buying factors should not be treated as equally important.

For each audience segment, estimate a relative importance:

``` text
Audience: Family SUV buyers

Safety             0.91
Space              0.84
Mileage            0.78
Price              0.75
Comfort            0.73
Technology         0.61
Performance        0.48
```

For another segment:

``` text
Audience: Young premium buyers

Design              0.88
Technology          0.86
Performance         0.82
Brand               0.79
Features            0.76
Mileage             0.51
Space               0.43
```

These weights should be learned from behavioral and survey data where
possible rather than being manually assigned.

------------------------------------------------------------------------

# 34. Purchase Driver vs Purchase Barrier

The system should distinguish between four related concepts:

### Strength

Something customers generally like.

``` text
Vehicle → strength → Interior Design
```

### Weakness

Something customers generally dislike.

``` text
Vehicle → weakness → Rear Seat Space
```

### Purchase Driver

A factor that actively increases the probability of purchase.

``` text
Customer Segment
      ↓
purchase_driver
      ↓
Safety
```

### Purchase Barrier

A factor that actively reduces the probability of purchase.

``` text
Customer Segment
      ↓
purchase_barrier
      ↓
Price
```

This distinction is important because a vehicle can have a weakness that
does not materially affect sales, while a relatively small purchase
barrier can significantly reduce conversion.

------------------------------------------------------------------------

# 35. Review & Opinion Intelligence

Reviews should become a structured intelligence layer rather than simply
a document collection.

The extraction pipeline should transform:

``` text
Raw Review
     ↓
Vehicle
     ↓
Aspect
     ↓
Opinion
     ↓
Sentiment
     ↓
Intensity
     ↓
Audience
     ↓
Intent
     ↓
Purchase Impact
```

Example:

> "The car is comfortable, but the mileage is disappointing."

Structured representation:

``` yaml
vehicle: Vehicle_X

opinions:
  - aspect: comfort
    sentiment: positive
    intensity: high

  - aspect: mileage
    sentiment: negative
    intensity: medium
```

------------------------------------------------------------------------

# 36. Customer vs Critic Opinion

The system should preserve source type.

Possible source classes:

``` text
Customer
Professional Critic
Automotive Journalist
Dealer
Salesperson
Expert
Social Media User
Forum User
```

This allows analysis such as:

> "Customers dislike mileage, but professional reviewers consider it
> acceptable."

Instead of incorrectly collapsing the two opinions into one score.

------------------------------------------------------------------------

# 37. Opinion Aggregation

For every vehicle and aspect, calculate:

``` text
Positive %
Negative %
Neutral %
Average sentiment
Sentiment intensity
Mention volume
Trend
Source distribution
```

Example:

``` text
Vehicle: X

Aspect: Mileage

Customer sentiment:
  Positive: 42%
  Negative: 51%
  Neutral: 7%

Critic sentiment:
  Positive: 61%
  Negative: 32%
  Neutral: 7%

Trend:
  Worsening

Business relevance:
  High
```

------------------------------------------------------------------------

# 38. Review → Purchase Impact

This is one of the most important extensions.

A negative review is not automatically a business problem.

The system should determine whether an opinion is associated with:

``` text
Purchase consideration
Purchase rejection
Test-drive request
Booking
Cancellation
Competitor selection
Upgrade
Downgrade
```

Example:

``` text
Customer considered:
Vehicle X

Rejected because:
Price

Alternative selected:
Vehicle Y
```

This creates:

``` text
Vehicle X
   ↓
Purchase Barrier
   ↓
Price
   ↓
Customer Segment
   ↓
Rejected
   ↓
Vehicle Y
```

This is much more valuable than sentiment alone.

------------------------------------------------------------------------

# 39. Unmet Need Detection

The system should identify repeated complaints that represent potential
product opportunities.

Example:

``` text
Thousands of conversations/reviews:

"Need better mileage"
"Great car but mileage is low"
"Would buy if mileage was better"
"Fuel cost is too high"
```

The system can consolidate these into:

``` text
Unmet Need:
LOWER RUNNING COST

Affected segment:
Urban SUV buyers

Frequency:
High

Purchase impact:
High

Competitive gap:
Medium

Potential product opportunity:
High
```

This allows the system to answer:

> "What customer needs are currently underserved by the market?"

------------------------------------------------------------------------

# 40. Audience × Vehicle Matrix

The system should build a matrix connecting audience segments to
products.

Example:

  Audience     Vehicle A   Vehicle B   Vehicle C
  ---------- ----------- ----------- -----------
  18-24             0.32        0.61        0.44
  25-34             0.72        0.81        0.55
  35-44             0.83        0.64        0.71
  45-54             0.68        0.51        0.77

The score could represent predicted purchase probability, consideration,
or suitability depending on the model.

This should not be interpreted as a static truth; it is a model output
that changes with price, features, competition, and market conditions.

------------------------------------------------------------------------

# 41. Audience × Buying Factor Matrix

Another important analytical layer:

  -------------------------------------------------------------------------------
  Audience        Price     Safety    Mileage   Features   Performance      Brand
  ---------- ---------- ---------- ---------- ---------- ------------- ----------
  Young            High     Medium     Medium       High          High       High
  Buyers                                                               

  Families         High  Very High       High     Medium        Medium     Medium

  Premium        Medium       High        Low  Very High     Very High  Very High
  Buyers                                                               

  Fleet       Very High     Medium  Very High        Low        Medium     Medium
  -------------------------------------------------------------------------------

This enables product teams to understand **what matters to whom**.

------------------------------------------------------------------------

# 42. Audience Evolution

Audience segments should not be static.

Track changes over time:

``` text
2024 → 2025 → 2026
```

Examples:

``` text
EV acceptance ↑
ADAS importance ↑
SUV preference ↑
Price sensitivity ↑
```

This can reveal emerging market shifts.

------------------------------------------------------------------------

# 43. Product Opportunity Engine

Combine:

``` text
Audience
+
Buying Factors
+
Unmet Needs
+
Competitor Weaknesses
+
Vehicle Features
+
Price
+
Market Demand
```

to identify product opportunities.

Example:

``` text
Opportunity:

Segment:
25-34 urban families

Need:
Affordable 7-seat vehicle

Current market:
Limited options

Price gap:
₹12-15L

Competitor weakness:
Low feature availability

Expected demand:
High
```

This can become a product hypothesis.

------------------------------------------------------------------------

# 44. Product Hypothesis

A proposed product should be represented as a structured hypothesis.

Example:

``` yaml
product_hypothesis:
  target_segment:
    - urban_families
    - 25_44

  need:
    - family_space
    - affordability
    - low_running_cost

  body_type: suv
  seating: 7

  powertrain: hybrid

  price_range:
    min: 1300000
    max: 1600000

  priority_features:
    - safety
    - mileage
    - space
    - connected_features
```

The system can then estimate:

``` text
Demand
Purchase probability
Market share
Competitor displacement
Cannibalization
Revenue
Margin
```

------------------------------------------------------------------------

# 45. Scenario Analysis

The product team should be able to change one or more parameters.

Example:

``` text
Scenario A:
₹15L
450 km range
5 seats

Scenario B:
₹17L
500 km range
5 seats

Scenario C:
₹16L
450 km range
7 seats
```

Then compare:

``` text
Expected demand
Revenue
Margin
Market share
Target audience
Purchase probability
Cannibalization
Competitive displacement
```

This creates the bridge between the ontology and the decision/simulation
engine.

------------------------------------------------------------------------

# 46. Additional Data Sources for Audience & Opinion Intelligence

## Customer Surveys

Useful for:

-   buying factors
-   feature importance
-   price sensitivity
-   brand perception
-   purchase barriers
-   unmet needs

Possible fields:

``` text
respondent_segment
vehicle_considered
feature_importance
purchase_reason
rejection_reason
budget_band
purchase_intent
```

## Market Research

Useful for:

-   segment sizing
-   demographic trends
-   brand perception
-   market trends
-   customer expectations

## Reviews

Sources:

-   automotive review platforms
-   public review sites
-   forums
-   social media
-   video comments
-   owner communities

## YouTube / Video Transcripts

Useful for:

-   professional reviews
-   owner reviews
-   comparison videos
-   long-term ownership reports

Extract:

``` text
vehicle
aspect
sentiment
claim
source_type
reviewer_type
```

## CRM / Sales Conversations

Useful for:

-   buying intent
-   objections
-   rejection reasons
-   competitor mentions
-   purchase drivers
-   conversion

## Search / Website Behavior

Useful for:

-   emerging demand
-   feature interest
-   comparison behavior
-   price sensitivity
-   audience intent

## Sales and Registration Data

Useful for validating whether stated preferences translate into actual
purchases.

------------------------------------------------------------------------

# 47. Privacy and Governance

Audience intelligence should primarily operate on:

-   aggregated segments
-   anonymized identifiers
-   consented first-party data
-   minimum cohort sizes
-   non-sensitive attributes relevant to automotive decisions

Avoid creating unnecessary individual-level profiles.

The objective is:

``` text
"25-34 urban buyers value X"
```

rather than:

``` text
"Person Y is likely to buy because of sensitive personal information."
```

The system should maintain source provenance for important claims and
distinguish observed data from model-derived inference.

------------------------------------------------------------------------

# 48. Updated End-to-End Architecture

``` text
                         DATA SOURCES
                              │
       ┌──────────────────────┼──────────────────────┐
       ↓                      ↓                      ↓
   Product Data          Customer Data          Market Data
       │                      │                      │
   Vehicles               CRM / Sales          Competitors
   Features               Conversations        Registrations
   Prices                 Search               Trends
       │                  Reviews               Macro
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              ↓
                     DATA + NLP PIPELINE
                              │
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
         Ontology         Audience         Opinion
         Extraction       Modeling        Extraction
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                 AUTOMOTIVE WORLD MODEL
                              │
      ┌───────────────────────┼───────────────────────┐
      ↓                       ↓                       ↓
  Products                Customers                Market
      │                       │                       │
  Features                Needs                   Competitors
  Variants                Intent                  Prices
  Costs                   Segments                Sales
      │                       │                       │
      └───────────────────────┼───────────────────────┘
                              ↓
                    DECISION INTELLIGENCE
                              │
       ┌──────────────────────┼──────────────────────┐
       ↓                      ↓                      ↓
   Demand Model          Choice Model          Sentiment Model
       │                      │                      │
       ├──────────────┬───────┴──────────────┬───────┤
       ↓              ↓                      ↓       │
  Price Elasticity  Cannibalization    Purchase     │
       │              Model             Intent       │
       └──────────────┴──────────┬───────────┴───────┘
                                 ↓
                          SCENARIO ENGINE
                                 ↓
                         WHAT-IF ANALYSIS
                                 ↓
                       BUSINESS RECOMMENDATION
```

------------------------------------------------------------------------

# 49. Example Executive Query

The complete system should eventually handle:

> "We are considering a ₹15--18 lakh hybrid SUV for India. Who should we
> target? What are the biggest buying factors for that audience? What do
> customers currently dislike about competing vehicles? Which unmet
> needs are most attractive? Which features should we prioritize? Which
> existing vehicles will we take sales from? What price maximizes demand
> and contribution margin? And what sales impact should we expect?"

The system should decompose this into:

``` text
1. IDENTIFY_TARGET_AUDIENCE
2. IDENTIFY_BUYING_FACTORS
3. IDENTIFY_UNMET_NEEDS
4. ANALYZE_CUSTOMER_OPINIONS
5. ANALYZE_CRITIC_OPINIONS
6. ANALYZE_COMPETITORS
7. GENERATE_PRODUCT_HYPOTHESES
8. ESTIMATE_DEMAND
9. ESTIMATE_PURCHASE_PROBABILITY
10. ESTIMATE_CANNIBALIZATION
11. ESTIMATE_COMPETITOR_DISPLACEMENT
12. OPTIMIZE_PRICE
13. OPTIMIZE_FEATURE_SET
14. SIMULATE_SALES
15. COMPARE_SCENARIOS
```

This makes the project much broader than a recommendation engine:

> **It becomes an Automotive Product & Market Intelligence system that
> connects audience needs, product attributes, opinions, competitive
> positioning, demand, and financial outcomes into one decision model.**
