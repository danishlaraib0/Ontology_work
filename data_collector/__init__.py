"""
Automotive Data Collector Module
=================================
Collects layered automotive intelligence data for a given brand + model.

Layer sequence (per ontology context):
  1. Vehicle Master
  2. Feature / Specification Master
  3. Market & Competitor Master
  4. Customer Audience / Segment Data
  5. Reviews & Opinions
  6. Search / Intent Data
  7. Sales & Registration Data
  8. Pricing / Offers
  9. Buying Factors
 10. Derived Opinion Dataset

Usage:
    from data_collector import run_collection
    run_collection(brand="Maruti Suzuki", model="Dzire")
"""

from .collector import run_collection

__all__ = ["run_collection"]
