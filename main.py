"""
Dynamic Programming Solution for Uber Driver Optimization

time t = 0 and location loc means max money u can have at 0:59 (time is in hours)
D(loc, t) = dynamic programming matrix = max money u can have at hour t at place loc
	
at start of each time interval we either stay in the same cell or move
Score(loc, t) = matricea de la gali

D(loc, t) = max money u can have at location loc at time t
	option 1: stau pe loc (prevLoc = loc)
		= D(prevLoc, t-1) + Score(loc, t)
	option 2: ma mut la o casuta noua
		= D(prevLoc, t-1) + Score(loc, t) * (60 - duration(preLoc, loc, t)) / 60 - consumBenzen * dist(prevLoc, loc)
"""

import csv
import os
import pandas as pd
from pandasgui import show

# Global variables
Score = None  # Score[loc][t] = money per hour at location loc at time t
D = None      # D[loc][t] = max money at location loc at time t
prev = None   # prev[loc][t] = previous location to reconstruct path
num_locations = 0
num_times = 0
distance_matrix = None  # distance_matrix[i][j] = distance between city i and city j

# Parameters
# TODO: Replace with actual data if available
AVG_SPEED_KMH = 50  # Average speed in km/h
FUEL_CONSUMPTION_PER_100KM = 7  # Liters per 100 km
FUEL_COST_PER_LITER = 2  # Euros per liter
consumBenzen = (FUEL_CONSUMPTION_PER_100KM / 100) * FUEL_COST_PER_LITER  # €0.14 per km


def load_score_data(filepath):
    """Load score data from CSV file"""
    global Score, num_locations, num_times
    
    # Read CSV file
    city_time_scores = {}
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_id = int(row['city_id'])
            job_hour = int(row['job_hour_2h'])
            score = float(row['avg_score_per_earner'])
            
            if city_id not in city_time_scores:
                city_time_scores[city_id] = {}
            city_time_scores[city_id][job_hour] = score
    
    # Determine dimensions
    city_ids = sorted(city_time_scores.keys())
    num_locations = len(city_ids)
    
    # Get all unique time periods
    all_times = set()
    for city_data in city_time_scores.values():
        all_times.update(city_data.keys())
    time_periods = sorted(all_times)
    num_times = len(time_periods)
    
    # Create Score matrix indexed by [city_index][time_index]
    Score = [[0.0] * num_times for _ in range(num_locations)]
    
    for city_idx, city_id in enumerate(city_ids):
        for time_idx, time_period in enumerate(time_periods):
            Score[city_idx][time_idx] = city_time_scores[city_id].get(time_period, 0.0)
    
    print(f"Loaded score data: {num_locations} cities, {num_times} time periods")
    return city_ids, time_periods


def load_distance_matrix(filepath):
    """Load distance matrix from CSV file"""
    global distance_matrix, num_locations
    
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        matrix_lines = [row for row in reader]
    
    n = len(matrix_lines)
    distance_matrix = [[0.0] * n for _ in range(n)]
    
    for i, row in enumerate(matrix_lines):
        for j, val in enumerate(row):
            distance_matrix[i][j] = float(val)
    
    print(f"Loaded distance matrix: {n}x{n}")
    return distance_matrix


def distance(loc1, loc2):
    """Returns distance between two locations in km"""
    return distance_matrix[loc1][loc2]


def travel_duration(loc1, loc2, t):
    """Returns travel time in minutes from loc1 to loc2 at time t"""
    # TODO: Replace with actual travel time data if available (considering traffic, time of day, etc.)
    dist = distance(loc1, loc2)
    duration_hours = dist / AVG_SPEED_KMH
    duration_minutes = duration_hours * 60
    return duration_minutes


def initialize_dp(start_hour, start_city):
    """
    Initialize DP tables
    
    Args:
        start_hour: Time index where the driver starts
        start_city: City index where the driver starts (home location)
    """
    global D, prev
    D = [[0.0] * num_times for _ in range(num_locations)]
    prev = [[-1] * num_times for _ in range(num_locations)]
    
    # Base case: driver starts at start_city at start_hour and earns the score there
    D[start_city][start_hour] = Score[start_city][start_hour]
    # All other locations at start_hour have 0 (driver can't be there)


def solve_dp(user_id, start_hour, start_city, end_hour, end_city):
    """
    Solve the DP problem for optimal driver routing
    
    Args:
        user_id: Driver identifier (not used yet, for future use)
        start_hour: Time index where the driver starts
        start_city: City index where the driver starts (home location)
        end_hour: Time index when driver needs to be back home
        end_city: City index where the driver needs to end up
    
    Returns:
        best_loc: Best city to be at before returning home
        best_money: Maximum money earned (including cost of returning home)
    """
    global D, prev
    
    initialize_dp(start_hour, start_city)
    
    # Fill DP table from start_hour+1 to end_hour
    for t in range(start_hour + 1, end_hour + 1):
        for loc in range(num_locations):
            # Option 1: stay at same location
            stay_money = D[loc][t-1] + Score[loc][t]
            
            if stay_money > D[loc][t]:
                D[loc][t] = stay_money
                prev[loc][t] = loc
            
            # Option 2: move from another location
            for prevLoc in range(num_locations):
                if prevLoc == loc:
                    continue
                
                duration = travel_duration(prevLoc, loc, t)
                if duration >= 60:  # can't make money if travel takes full hour
                    continue
                
                dist = distance(prevLoc, loc)
                move_money = (D[prevLoc][t-1] + 
                            Score[loc][t] * (60 - duration) / 60 - 
                            consumBenzen * dist)
                
                if move_money > D[loc][t]:
                    D[loc][t] = move_money
                    prev[loc][t] = prevLoc
    
    # Find best final location accounting for return to end_city
    # For each city, calculate the cost/time to return to end_city and adjust the score
    best_loc = end_city
    best_money = D[end_city][end_hour]
    
    for loc in range(num_locations):
        if loc == end_city:
            # Already at end city, no additional cost
            adjusted_money = D[loc][end_hour]
        else:
            # Calculate travel time to get to end_city (in minutes)
            travel_time_minutes = travel_duration(loc, end_city, end_hour)
            # Convert to 2-hour periods (rounding up)
            travel_time_periods = int((travel_time_minutes + 119) // 120)  # Round up to nearest 2-hour period
            
            # Go back that many periods in the DP table
            departure_time = end_hour - travel_time_periods
            
            if departure_time < start_hour:
                # Not enough time to get to end_city from this location
                continue
            
            # Calculate fuel cost to get to end_city
            dist = distance(loc, end_city)
            fuel_cost = consumBenzen * dist
            
            # Adjusted score = earnings up to departure time - fuel cost to get to end_city
            adjusted_money = D[loc][departure_time] - fuel_cost
        
        if adjusted_money > best_money:
            best_money = adjusted_money
            best_loc = loc
    
    return best_loc, best_money


def reconstruct_path(final_loc, start_hour, end_hour):
    """
    Reconstruct the optimal path
    
    Args:
        final_loc: Best city to be at before returning home
        start_hour: Time index where the driver started
        end_hour: Time index when driver needs to be back home
    
    Returns:
        path: List of city indices representing the optimal path
    """
    path = []
    loc = final_loc
    
    for t in range(end_hour, start_hour - 1, -1):
        path.append(loc)
        if t > start_hour:
            loc = prev[loc][t]
    
    path.reverse()
    return path


def shouldWeChangeCity(current_city, current_time, end_city, user_id, end_hour):
    """
    Determine if the driver should change cities based on the optimal path from current position.
    
    This function runs the DP algorithm from the current position/time, reconstructs the optimal
    path, and checks if the next location in the path is different from the current location.
    
    Args:
        current_city: City index where the driver is currently located (start position)
        current_time: Time index representing the current time (start time)
        end_city: City index where the driver needs to end up
        user_id: Driver identifier
        end_hour: Time index when driver needs to be at end_city
    
    Returns:
        None: If the driver should stay in the current city
        int: City index of where the driver should go if they need to move
    """
    # Run the DP algorithm from current position
    best_loc, best_money = solve_dp(user_id, current_time, current_city, end_hour, end_city)
    
    # Reconstruct the optimal path starting from current position/time
    path = reconstruct_path(best_loc, current_time, end_hour)
    
    # Check if we have at least 2 positions in the path (current and next)
    if len(path) < 2:
        # Only one time period left or edge case - stay where we are
        return None
    
    # Compare current position with next position in optimal path
    current_position = path[0]  # Where we are now
    next_position = path[1]     # Where we should be next
    
    if current_position == next_position:
        # Should stay in current city
        return None
    else:
        # Should move to next_position
        return next_position


def visualize_matrices(start_hour, end_hour):
    """
    Visualize the Score and DP matrices using pandasgui
    Shows columns from start_hour to end_hour
    
    Args:
        start_hour: Starting time index
        end_hour: Ending time index
    """
    # Create data for the DataFrame - only columns in the working range
    data = {}
    num_columns = end_hour - start_hour + 1
    
    for t in range(start_hour, end_hour + 1):
        col_data = []
        for loc in range(num_locations):
            score_val = Score[loc][t]
            dp_val = D[loc][t]
            # Format: "S: X.XX | D: Y.YY"
            cell_str = f"S: {score_val:.2f} | D: {dp_val:.2f}"
            col_data.append(cell_str)
        # Label columns as relative time (0, 1, 2, ...) or absolute (T=start, T=start+1, ...)
        data[f"T={t}"] = col_data
    
    # Create DataFrame with city indices as rows
    df = pd.DataFrame(data, index=[f"City {i+1}" for i in range(num_locations)])
    
    # Print to console for reference
    print("\n=== Score and DP Matrix Visualization ===")
    print(f"Time range: {start_hour} to {end_hour} ({num_columns} periods)")
    print("Format: S: Score | D: DP Value")
    print("\n")
    print(df.to_string())
    print("\nOpening GUI window...")
    
    # Open pandasgui window - that's it!
    show(df, settings={'block': True})
    
    return df


# Main function to run
def run(user_id, start_hour, start_city, end_hour, end_city):
    """
    Run the dynamic programming solution
    
    Args:
        user_id: Driver identifier
        start_hour: Time index where the driver starts
        start_city: City index where the driver starts (home location)
        end_hour: Time index when driver needs to be back home
        end_city: City index where the driver needs to end up
    
    Returns:
        best_money: Maximum money earned
        path: Optimal path as list of city indices
    """
    best_loc, best_money = solve_dp(user_id, start_hour, start_city, end_hour, end_city)
    path = reconstruct_path(best_loc, start_hour, end_hour)
    
    print(f"\n=== Results ===")
    print(f"User ID: {user_id}")
    print(f"Start: City {start_city + 1} at hour {start_hour}")
    print(f"End: Must be at City {end_city + 1} by hour {end_hour}")
    print(f"Maximum money: €{best_money:.2f}")
    print(f"Best location before returning: City {best_loc + 1}")
    print(f"\nOptimal path (city indices): {path}")
    print(f"Optimal path (city IDs): {[loc + 1 for loc in path]}")
    
    # Visualize the matrices
    df = visualize_matrices(start_hour, end_hour)
    
    return best_money, path, df


if __name__ == "__main__":
    # File paths
    data_dir = "data"
    score_file = os.path.join(data_dir, "test_69_relocation_schedule_scaled_2_to_8_compact_10_per_city.csv")
    distance_file = os.path.join(data_dir, "nl_cities_adjacency_matrix.csv")
    
    print("Loading data...")
    city_ids, time_periods = load_score_data(score_file)
    load_distance_matrix(distance_file)
    
    print(f"\nParameters:")
    print(f"  Average speed: {AVG_SPEED_KMH} km/h")
    print(f"  Fuel consumption: {FUEL_CONSUMPTION_PER_100KM} L/100km")
    print(f"  Fuel cost: €{FUEL_COST_PER_LITER}/L")
    print(f"  Total fuel cost: €{consumBenzen:.4f}/km")
    
    # Example usage: Driver works for 8 hours (4 time periods of 2 hours each)
    user_id = "driver_001"
    start_hour = 0
    start_city = 0  # City 1 (index 0)
    end_city = 0    # Must return to City 1 (index 0)
    end_hour = 8    # 8 hours: 0-3 = 4 periods (8 hours total)
    
    print(f"\nRunning dynamic programming solver for 8 HOURS...")
    print(f"Driver {user_id} starting at City {start_city + 1} at hour {start_hour}")
    print(f"Must return to City {end_city + 1} by hour {end_hour}")
    
    best_money, path, df = run(user_id, start_hour, start_city, end_hour, end_city)
