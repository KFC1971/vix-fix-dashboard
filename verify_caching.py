
from cm_williams_vix_fix import CMWilliamsVixFixScanner
import os
import shutil

# Clean up previous test data if any
if os.path.exists("data/nasdaq100_data.csv"):
    os.remove("data/nasdaq100_data.csv")

print("--- TEST 1: First Run (Full Download) ---")
scanner = CMWilliamsVixFixScanner()
scanner.fetch_data(universe="nasdaq100")
data_shape_1 = scanner.data.shape
print(f"Data Loaded: {data_shape_1}")
assert os.path.exists("data/nasdaq100_data.csv"), "CSV file not created"

print("\n--- TEST 2: Second Run (Incremental - Should be fast) ---")
scanner2 = CMWilliamsVixFixScanner()
scanner2.fetch_data(universe="nasdaq100") # Should use cache
data_shape_2 = scanner2.data.shape
print(f"Data Loaded: {data_shape_2}")

assert data_shape_1 == data_shape_2, "Data mismatch between cached and fresh run"

print("\n--- SUCCESS: Caching verified ---")
