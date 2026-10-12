"""
collect_and_ingest_competitors.py
=================================
Runs end-to-end data collection and ingests vehicles into Neo4j.
Accepts optional --make and --model CLI arguments.
"""
import argparse
import sys
import time
from data_collector.collector import run_collection
from graph_db.loader import load_all_collected_to_graph, load_vehicle_to_graph
from data_collector.storage import _slugify
from export_cypher import generate_cypher_script

DEFAULT_TARGETS = [
    ("Hyundai", "Aura"),
    ("Honda", "Amaze"),
]

def main():
    parser = argparse.ArgumentParser(description="Collect and ingest automotive data into Neo4j")
    parser.add_argument("--make", type=str, help="Vehicle Make / Brand (e.g. Hyundai)")
    parser.add_argument("--model", type=str, help="Vehicle Model (e.g. Aura)")
    args = parser.parse_args()

    targets = [(args.make, args.model)] if args.make and args.model else DEFAULT_TARGETS

    print(f"🚀 Starting Data Collection for Models: {targets}\n")
    for brand, model in targets:
        print(f"\n=======================================================")
        print(f"▶ Collecting 12 Layers for: {brand} {model}")
        print(f"=======================================================\n")
        try:
            run_collection(brand, model, force=False)
            print(f"✅ Successfully completed {brand} {model}")
        except Exception as e:
            print(f"❌ Error collecting {brand} {model}: {e}")

    print("\n\n=======================================================")
    print("🔄 Ingesting into Neo4j...")
    print("=======================================================\n")
    if args.make and args.model:
        try:
            metrics = load_vehicle_to_graph(_slugify(args.make), _slugify(args.model))
            print(f"✅ Ingested {args.make} {args.model}: {metrics}")
        except Exception as e:
            print(f"Falling back to load_all_collected_to_graph(): {e}")
            load_all_collected_to_graph()
    else:
        load_all_collected_to_graph()

    generate_cypher_script()
    print("\n🎉 Complete! Ingested into Neo4j Graph DB.")

if __name__ == "__main__":
    main()
