
from cm_williams_vix_fix import CMWilliamsVixFixScanner

print("Verifying fix for Nasdaq 100 download...")
scanner = CMWilliamsVixFixScanner()
# Manually override universe selection to Nasdaq 100
scanner.fetch_data(universe="nasdaq100")

if scanner.data is not None and not scanner.data.empty:
    print("SUCCESS: Data downloaded successfully!")
    print(f"Data shape: {scanner.data.shape}")
else:
    print("FAILURE: Data download failed.")
