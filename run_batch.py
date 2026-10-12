"""
run_batch.py
============
Sequentially run automotive intelligence collection across target models:
  • Maruti Suzuki Wagon R
  • Maruti Suzuki Baleno
  • Maruti Suzuki Ciaz
  • Maruti Suzuki Brezza
  • Maruti Suzuki Ertiga
"""
import sys
import time
from data_collector.collector import run_collection

TARGET_VEHICLES = [
    ("Maruti Suzuki", "Wagon R"),
    ("Maruti Suzuki", "Baleno"),
    ("Maruti Suzuki", "Ciaz"),
    ("Maruti Suzuki", "Brezza"),
    ("Maruti Suzuki", "Ertiga"),
]

def main():
    print(f"🚀 Starting Multi-Vehicle Ontology Data Collection for {len(TARGET_VEHICLES)} models...\n")
    results = {}
    for brand, model in TARGET_VEHICLES:
        print(f"\n=======================================================")
        print(f"▶ Processing: {brand} {model}")
        print(f"=======================================================\n")
        try:
            res = run_collection(brand, model, force=False)
            results[f"{brand} {model}"] = "SUCCESS"
        except Exception as e:
            print(f"❌ Error processing {brand} {model}: {e}")
            results[f"{brand} {model}"] = f"FAILED: {e}"
        
        # Inter-vehicle cool-off period to prevent rate-limit buildup
        print(f"⏳ Cooling down for 6s before next vehicle...")
        time.sleep(6.0)

    print("\n\n=======================================================")
    print("📊 BATCH SUMMARY")
    print("=======================================================")
    for vehicle, status in results.items():
        print(f"  {vehicle}: {status}")

if __name__ == "__main__":
    main()
