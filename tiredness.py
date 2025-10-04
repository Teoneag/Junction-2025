import csv
import math
from datetime import datetime

# === FATIGUE MODEL CONSTANTS ===

# Tiredness weights
ALPHA = 0.8    # weight for total hours driven
BETA = 0.008   # weight for total km driven
GAMMA = 1.2    # weight for hours since last break
DELTA = 0.015  # weight for km since last break
C = 7.0        # sigmoid center (threshold for 0.5 tiredness)

# Historical averages (for comparison)
MEAN_TIREDNESS = 0.5
STD_TIREDNESS = 0.1
MEAN_QUALITY = 0.6
STD_QUALITY = 0.1

# === TIREDNESS FUNCTIONS ===

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def compute_tiredness(total_hours, total_kms, hours_since_break, kms_since_break):
    tiredness_input = (
        ALPHA * total_hours +
        BETA * total_kms +
        GAMMA * hours_since_break +
        DELTA * kms_since_break
    )
    return sigmoid(tiredness_input - C)

def should_take_break(total_hours, hours_since_break,
                      total_kms, kms_since_break,
                      trip_quality):
    tiredness = compute_tiredness(total_hours, total_kms,
                                   hours_since_break, kms_since_break)

    threshold1 = MEAN_TIREDNESS + STD_TIREDNESS
    threshold2 = MEAN_TIREDNESS + 2 * STD_TIREDNESS
    quality_threshold = MEAN_QUALITY - STD_QUALITY

    if tiredness > threshold2:
        return True
    elif tiredness > threshold1 and trip_quality < quality_threshold:
        return True
    else:
        return False

# === MAIN PROCESSING FUNCTION ===

def process_latest_trip_per_driver(csv_path):
    latest_trip_by_driver = {}

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            driver_id = row['driver_id']
            ride_id = row['ride_id']
            end_time_str = row['end_time']

            # Parse trip end time
            try:
                end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                print(f"Skipping ride {ride_id}: invalid end_time format")
                continue

            # Keep only the latest trip per driver
            if driver_id not in latest_trip_by_driver or end_time > latest_trip_by_driver[driver_id]['_end_time']:
                row['_end_time'] = end_time  # Add parsed time for comparison
                latest_trip_by_driver[driver_id] = row

    # Now process only latest trip per driver
    results = []
    for driver_id, row in latest_trip_by_driver.items():
        try:
            ride_id = row['ride_id']

            # Extract fatigue-related data
            total_hours = float(row['total_hours_today'])
            hours_since_break = float(row['cont_hours_before'])
            total_kms = float(row['total_km_today'])
            kms_since_break = float(row['cont_km_before'])

            # Placeholder trip quality
            trip_quality = 0.5

            take_break = should_take_break(
                total_hours=total_hours,
                hours_since_break=hours_since_break,
                total_kms=total_kms,
                kms_since_break=kms_since_break,
                trip_quality=trip_quality
            )

            results.append((ride_id, driver_id, take_break))

        except Exception as e:
            print(f"Error processing driver {driver_id} (ride {ride_id}): {e}")

    return results

# === RUN SCRIPT ON EXAMPLE CSV ===

if __name__ == "__main__":
    csv_file_path = "simulated_rides_with_continuous_large_with_totals.csv"  # Replace with your actual CSV file path
    break_recommendations = process_latest_trip_per_driver(csv_file_path)

    # Print summary
    for ride_id, driver_id, should_break in break_recommendations:
        status = "Take Break" if should_break else "Keep Driving"
        print(f"Driver {driver_id} (latest ride {ride_id}): {status}")
