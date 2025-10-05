# BOB — Smart Driver Assistant

## Overview
**BOB (Better Optimization Bot)** is an intelligent driver assistance system designed to maximize Uber driver earnings while prioritizing safety. The system combines dynamic route optimization, scientific fatigue monitoring, demand prediction, and AI-powered guidance to help drivers make optimal decisions throughout their shift.

## Core Value Proposition
- **Maximize Earnings:** Dynamic route optimization and intelligent trip acceptance  
- **Ensure Safety:** Science-based fatigue detection with mandatory break recommendations  
- **Reduce Uncertainty:** Predictive analytics for demand zones and trip quality  
- **Natural Guidance:** AI-generated conversational advice via GPT-3.5

---

## Dynamic Programming Route Optimization

The system uses dynamic programming to find the optimal sequence of locations across time periods that maximizes net earnings while accounting for travel costs and time constraints.

### State Definition
`D[loc][t]` = Maximum achievable earnings at location `loc` at end of time period `t`

**Parameters**
- **Locations:** Cities or zones (indexed `0..L-1`)
- **Time Periods:** 2-hour blocks (e.g., `t=0` represents 0–2h, `t=1` represents 2–4h)
- **Score[loc][t]:** Expected earnings per hour at location `loc` during time period `t`

### Recurrence Relation
For each location `loc` and time period `t > 0`:

**Option 1: Stay at Current Location**
```text
D[loc][t] = D[loc][t-1] + Score[loc][t]
```

**Option 2: Relocate from Another Location**
```text
D[loc][t] = max over all prevLoc ≠ loc of:
{
    D[prevLoc][t-1] 
    + Score[loc][t] × (60 - travel_time(prevLoc, loc, t)) / 60
    - fuel_cost_per_km × distance(prevLoc, loc)
}
```

**Final Selection**
```text
D[loc][t] = max(Option 1, Option 2)
prev[loc][t] = argmax(prevLoc)  # For path reconstruction
```

**Components**
- `travel_time(prevLoc, loc, t)`: Travel duration in minutes (distance / avg_speed)  
- `fuel_cost_per_km = (fuel_consumption_L_per_100km / 100) × fuel_price_per_L`  
  - **Default:** `(7 / 100) × 2.0 = €0.14` per km  
- `distance(prevLoc, loc)`: Distance in km from adjacency matrix

### Boundary Conditions
**Initial State (`t = start_hour`):**
```text
D[start_city][start_hour] = Score[start_city][start_hour]
D[other_cities][start_hour] = 0  # Driver cannot be elsewhere initially
```

**Final State (returning to end location):**
```text
For each potential final location 'loc':
    travel_periods_needed = ⌈travel_time_minutes / 120⌉  # Round up to 2-hour periods
    departure_time = end_hour - travel_periods_needed
    
    adjusted_earnings[loc] = D[loc][departure_time] 
                           - fuel_cost_per_km × distance(loc, end_city)

best_final_location = argmax(adjusted_earnings)
```

### Path Reconstruction
```python
path = []
current_loc = best_final_location
for t in range(end_hour, start_hour - 1, -1):
    path.insert(0, current_loc)
    current_loc = prev[current_loc][t]
return path
```

**Complexity:** `O(L² × T)` where `L` = number of locations, `T` = number of time periods

### Usage Example
```python
# Run optimization for 8-hour shift
best_money, path, df = run(
    user_id="driver_001",
    start_hour=4,    # 8:00 AM (hour 8 → index 4)
    start_city=1,    # City 2 (0-indexed)
    end_hour=12,     # 16:00 (hour 16 → index 8)
    end_city=1       # Return to City 2
)

print(f"Maximum Earnings: €{best_money:.2f}")
print(f"Optimal Route: {[city_id + 1 for city_id in path]}")
```

---

## Trip Acceptance Decision System (Heuristic 2)

### Trip Score Calculation
```text
trip_score = revenue - fuel_cost - safety_penalty
```
Where:
- `revenue = net_earnings + tips`
- `fuel_cost = fuel_cost_per_km × distance_km`
- `safety_penalty = safety_price × safety_score`

**Default Parameters**
- `fuel_cost_per_km = 0.14` (€0.14 per kilometer)  
- `safety_price = 0.1` (safety weight coefficient)  
- `safety_score ∈ [0, 1]` (0 = very safe, 1 = unsafe)

### Expected Score Calculation
```text
expected_score = (expected_score_per_hour / 60) × trip_duration_minutes
```
Where `expected_score_per_hour` is derived from the **hex scoring** system for the current location and time period.

### Decision Ratio and Acceptance Probability
```text
decision_ratio = current_trip_score / expected_score
P(Accept) = 1 / (1 + e^(-c·(decision_ratio - 1)))
```
Parameters:
- `c = 5.0`: Sigmoid steepness parameter (higher values create more decisive thresholds)

**Decision Rule**
```text
IF P(Accept) ≥ 0.5:  ACCEPT
ELSE:                REJECT (wait for better offer)
```

**Edge Cases**
- If `expected_score ≤ 0`: Accept if `current_trip_score > 0`, otherwise reject  
- If `decision_ratio = 1.0`: `P(Accept) = 0.5` (neutral decision point)  
- If `trip_duration > 60 minutes`: Cannot relocate and earn in same time period

### Implementation
```python
def shouldWeAccept(current_score, expected_score_hour, duration_this_trip_min, c=5.0):
    """
    Determine whether to accept a trip based on decision ratio probability.
    
    Returns:
        probability (float): Acceptance probability [0, 1]
        decision (bool): True to accept, False to reject
    """
    expected_score = (expected_score_hour / 60.0) * duration_this_trip_min
    
    if expected_score <= 0:
        probability = 1.0 if current_score > 0 else 0.0
        decision = current_score > 0
        return probability, decision
    
    decision_ratio = current_score / expected_score
    exponent = -c * (decision_ratio - 1)
    probability = 1.0 / (1.0 + math.exp(exponent))
    decision = probability >= 0.5
    
    return probability, decision
```

---

## Fatigue Detection Model

The system uses a multi-factor sigmoid model to compute driver tiredness and determine when breaks are mandatory.

### Tiredness Computation
```text
tiredness_input = α × total_hours_driven 
                + β × total_km_driven 
                + γ × hours_since_last_break 
                + δ × km_since_last_break

tiredness = σ(tiredness_input - C) = 1 / (1 + e^(-(tiredness_input - C)))
```

### Model Parameters
| Parameter | Value | Description |
|---|---:|---|
| α (ALPHA) | 0.8 | Weight for cumulative hours worked today |
| β (BETA) | 0.008 | Weight for cumulative kilometers driven today |
| γ (GAMMA) | 1.2 | Weight for continuous hours since last break |
| δ (DELTA) | 0.015 | Weight for continuous km since last break |
| C | 7.0 | Sigmoid center point (threshold for 50% tiredness) |

**Statistical Baselines**
- `MEAN_TIREDNESS = 0.5` — Historical average tiredness level  
- `STD_TIREDNESS = 0.1` — Standard deviation of tiredness  
- `MEAN_QUALITY = 0.6` — Historical average trip quality  
- `STD_QUALITY = 0.1` — Standard deviation of trip quality

### Break Decision Logic
```python
should_take_break = (
    tiredness > (MEAN_TIREDNESS + 2 * STD_TIREDNESS)  # Very tired (>0.7)
    or
    (tiredness > (MEAN_TIREDNESS + STD_TIREDNESS) and  # Moderately tired (>0.6)
     trip_quality < (MEAN_QUALITY - STD_QUALITY))      # AND low quality trip (<0.5)
)
```

**Break Trigger Conditions**
- **Mandatory Break:** Tiredness exceeds mean + 2σ (≈ 0.7)  
- **Conditional Break:** Tiredness exceeds mean + 1σ (≈ 0.6) **and** next available trip has quality below mean − 1σ

**Break Duration:** 15 minutes (`BREAK_DURATION_MINUTES`, configurable)

### Implementation
```python
def should_take_break(total_hours, hours_since_break,
                      total_kms, kms_since_break,
                      trip_quality):
    """
    Determine if driver should take a mandatory or conditional break.
    
    Returns:
        bool: True if break is recommended, False otherwise
    """
    tiredness = compute_tiredness(total_hours, total_kms,
                                   hours_since_break, kms_since_break)
    
    threshold1 = MEAN_TIREDNESS + STD_TIREDNESS
    threshold2 = MEAN_TIREDNESS + 2 * STD_TIREDNESS
    quality_threshold = MEAN_QUALITY - STD_QUALITY
    
    if tiredness > threshold2:
        return True  # Mandatory break
    elif tiredness > threshold1 and trip_quality < quality_threshold:
        return True  # Conditional break
    else:
        return False  # Continue driving
```

---

## Hexagonal Zone Scoring System

Each hexagonal zone receives a composite score to guide driver positioning decisions.

### Hex Score Formula
```text
hex_score = α × (predicted_eph / (predicted_std + ε)) 
          - β × cancellation_rate_pct 
          + γ × ln(1 + job_count)
```
**Scoring Components**
- **`α = 0.3` — Earnings reliability:** high predicted earnings per hour with low variance  
- **`β = 0.1` — Cancellation penalty:** historical cancellation rate reduces score  
- **`γ = 0.2` — Demand volume:** logarithmic scaling of job availability

**Variables**
- `predicted_eph`: Predicted earnings per hour for the zone/time  
- `predicted_std`: Standard deviation of earnings predictions  
- `cancellation_rate_pct`: Historical cancellation percentage (0–100)  
- `job_count`: Number of jobs available in the zone  
- `ε = 1e-6`: Small constant to prevent division by zero

### Cancellation Rate Aggregation
```python
avg_cancellation_rate_pct = mean(cancellation_rate_pct)  # GROUP BY city_id
```
Aggregates historical cancellation data by city to identify unreliable zones.

### Zone Recommendation
```python
def recommend_better_hex_index(current_hex, merged_csv="hex_scores.csv", 
                               num_neighbors=18, min_improvement=0.1):
    """
    Returns:
        relative_index (int): Index of best hex (0=current, 1-18=neighbors)
        improvement_pct (float): Percentage improvement over current hex
    """
    # Load hex scores and find neighbors
    # Return best scoring hexagon within neighbor range
```

---

## Relocation Decision System

### `shouldWeChangeCity()` Logic
```python
def shouldWeChangeCity(current_city, current_time, end_city, user_id, end_hour):
    """
    Determine if driver should relocate based on optimal path from current position.
    
    Returns:
        None: Stay at current location
        int: City index to relocate to
    """
    # Run DP from current position
    best_loc, best_money = solve_dp(user_id, current_time, current_city, 
                                    end_hour, end_city)
    
    # Reconstruct optimal path
    path = reconstruct_path(best_loc, current_time, end_hour)
    
    # Compare current vs next location in optimal path
    if len(path) < 2 or path[0] == path[1]:
        return None  # Stay at current location
    else:
        return path[1]  # Relocate to this city
```
**Decision Trigger:** Called after completing each trip or during idle periods

---

## Fuel Consumption Model
```text
fuel_consumed = (distance_km / 100) × fuel_consumption_rate
remaining_fuel = current_fuel - fuel_consumed
```
**Default Parameters**
- `fuel_consumption_rate = 6.0` liters per 100 km  
- `initial_tank_capacity = 50.0` liters

**Fuel Warnings**
- **Warning Level:** `remaining_fuel < 15L` (orange alert)  
- **Critical Level:** `remaining_fuel < 10L` (red alert — immediate refueling recommended)

---

## System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     Flutter Mobile App                       │
│  ┌────────────┐ ┌──────────────┐ ┌─────────────────────┐   │
│  │ Ride       │ │ Map View     │ │ BOB AI Assistant    │   │
│  │ Requests   │ │ (Hexagons)   │ │ (Advice Popup)      │   │
│  └────────────┘ └──────────────┘ └─────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
     ┌───────────────┼────────────────┬──────────────────┐
     │               │                │                  │
     ▼               ▼                ▼                  ▼
┌──────────┐  ┌─────────────┐  ┌──────────────┐  ┌────────────┐
│ Fatigue  │  │ DP Route    │  │ Hex Scoring  │  │ Trip       │
│ Monitor  │  │ Optimizer   │  │ Engine       │  │ Acceptance │
└──────────┘  └─────────────┘  └──────────────┘  └────────────┘
     │               │                │                  │
     └───────────────┴────────────────┴──────────────────┘
                     │
                     ▼
            ┌──────────────────┐
            │  OpenAI GPT-3.5  │
            │  Advice Engine   │
            └──────────────────┘
```

---

## Technical Stack

### Backend (Python)
- `pandas` — Data processing and aggregation  
- `numpy` — Numerical computations  
- `h3` — Hexagonal hierarchical spatial indexing  
- `folium` — Map visualization (development)

### Frontend (Flutter/Dart)
- `google_maps_flutter` — Interactive map display  
- `h3_flutter` — Hexagon rendering  
- `http` — OpenAI API communication  
- `dart:async` — Asynchronous operations

### AI/ML
- **OpenAI GPT-3.5 Turbo** — Conversational advice generation

---
## Performance Metrics

### Optimization Objectives
- **Earnings Maximization:** Net €/hour across shift  
- **Safety Compliance:** Break adherence rate  
- **Fuel Efficiency:** Kilometers per liter  
- **Strategic Positioning:** Time in high-demand zones

### Algorithm Complexity
| Component | Time Complexity | Space Complexity |
|---|---|---|
| Fatigue Detection | O(1) | O(1) |
| DP Optimization | O(L² × T) | O(L × T) |
| Hex Scoring | O(N) | O(N) |
| Trip Acceptance | O(1) | O(1) |

> Where: `L = locations`, `T = time periods`, `N = hexagons`

---

## Usage Examples

### Complete Simulation
```python
from dp_solution import run_simulation

results = run_simulation(
    trips_csv_path="data/testing-data-good-vladutz.csv",
    user_id="E30001",
    start_city_id=2,
    end_city_id=2,
    start_time_str="08:00",
    end_time_str="16:00"
)

print(f"Total Earnings: €{results['total_earnings']:.2f}")
print(f"Trips Taken: {results['trips_taken']}")
print(f"Breaks: {results['breaks_taken']}")
```

### Real-Time Decisions
```python
# Relocation decision
new_city = shouldWeChangeCity(
    current_city=1, 
    current_time=5, 
    end_city=1, 
    user_id="driver_001", 
    end_hour=8
)

# Trip acceptance decision
probability, accept = shouldWeAccept(
    current_score=12.50,
    expected_score_hour=15.0,
    duration_this_trip_min=25
)
```

---


## License
**JunctionX TU Delft Hackathon 2025** — Educational/Competition Use

---

## Team
**Project Team:** Vlad, Alex, Teodor, Horia, Patrick  
**Tagline:** _Drive Smart. Earn More. Stay Safe._

> Built to help drivers optimize earnings while maintaining safety and wellbeing on the road.
