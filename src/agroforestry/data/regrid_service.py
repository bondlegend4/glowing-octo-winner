import requests
import pandas as pd
from typing import List, Dict

# Assume config.py is in the parent directory and properly configured
from ..config import REGRID_API_TOKEN

REGRID_API_URL = "https://app.regrid.com/api/v2/parcels"

# Define the core fields your platform requires.
# 'geom' is assumed to be present for any spatial query.
REQUIRED_FIELDS = [
    'owner',        # Owner name
    'zoning',       # Zoning information
    'propclass',    # Property class (e.g., residential, commercial, agricultural)
    'landuse_desc', # Description of land use
    'acres',        # Parcel size
    'sale_price',   # Last sale price
    'sale_date'     # Last sale date
]

def fetch_regrid_data_by_county(county_fips: str, limit: int = 1000) -> List[Dict]:
    """
    Fetches parcel data from the Regrid API for a given county FIPS code.
    
    Args:
        county_fips: The 5-digit FIPS code for the county (e.g., '36001' for Albany, NY).
        limit: The number of records to fetch.
        
    Returns:
        A list of parcel dictionaries from the API response.
    """
    if not REGRID_API_TOKEN:
        raise ValueError("REGRID_API_TOKEN is not set in your environment.")

    headers = {'Authorization': f'Bearer {REGRID_API_TOKEN}'}
    params = {
        'county_fips': county_fips,
        'limit': limit
    }
    
    try:
        response = requests.get(REGRID_API_URL, headers=headers, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json().get('parcels', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Regrid API: {e}")
        return []

def analyze_data_completeness(parcels: List[Dict]) -> Dict:
    """
    Analyzes a list of parcel records to determine the completeness of required fields.
    """
    if not parcels:
        return {
            "total_records": 0,
            "completeness_percentage": {},
            "fields_to_source": []
        }
        
    df = pd.DataFrame(parcels)
    total_records = len(df)
    completeness = {}
    
    for field in REQUIRED_FIELDS:
        if field in df.columns:
            # Calculate percentage of non-null/non-empty values
            completeness[field] = (df[field].notna().sum() / total_records) * 100
        else:
            completeness[field] = 0

    fields_to_source = [field for field, pct in completeness.items() if pct < 80] # Set a threshold
    
    return {
        "total_records": total_records,
        "completeness_percentage": completeness,
        "fields_to_source": fields_to_source
    }

def create_acquisition_plan(analysis_results: Dict, state: str, client_demand: Dict) -> Dict:
    """
    Generates a prioritized plan for acquiring missing data.
    """
    plan = {
        "state": state,
        "data_needed": analysis_results['fields_to_source'],
        "priority_score": 0,
        "client_demand": client_demand,
        "notes": f"Analysis based on {analysis_results['total_records']} records. Key missing fields: {', '.join(analysis_results['fields_to_source'])}"
    }
    
    # Simple priority scoring model
    # Higher score = higher priority
    score = 0
    score += len(plan['data_needed']) * 10  # More missing fields = higher priority
    score += client_demand.get('platinum', 0) * 5
    score += client_demand.get('gold', 0) * 3
    score += client_demand.get('free', 0) * 1
    
    plan['priority_score'] = score
    
    return plan

if __name__ == '__main__':
    # --- Example Usage for an Admin Task ---
    
    # 1. Fetch data for a target county (e.g., Albany County, NY)
    print("Fetching data from Regrid for Albany County, NY (FIPS: 36001)...")
    albany_parcels = fetch_regrid_data_by_county('36001', limit=500)
    
    # 2. Analyze completeness
    print("\nAnalyzing data completeness...")
    analysis = analyze_data_completeness(albany_parcels)
    print(pd.DataFrame([analysis['completeness_percentage']]).round(2))
    
    # 3. Simulate client demand and create an acquisition plan
    print("\nGenerating data acquisition plan...")
    # This demand would come from your user database in a real scenario
    simulated_demand = {"platinum": 5, "gold": 20, "free": 100}
    
    acquisition_plan = create_acquisition_plan(analysis, "NY", simulated_demand)
    
    # Sort plans by priority score in a real application
    print("\n--- Data Acquisition Priority ---")
    print(f"State: {acquisition_plan['state']}")
    print(f"Priority Score: {acquisition_plan['priority_score']}")
    print(f"Data Needed: {acquisition_plan['data_needed']}")
    print(f"Client Demand: {acquisition_plan['client_demand']}")
    print(f"Notes: {acquisition_plan['notes']}")
    
    # The output of this would be saved to a database or CSV for the admin team.