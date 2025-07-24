from fastapi import FastAPI
from agroforestry.core.analysis_engine import run_permaculture_analysis

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Agroforestry Platform API"}

@app.get("/analyze/{parcel_id}")
def analyze_parcel(parcel_id: int):
    """
    Endpoint to trigger a full analysis for a given parcel.
    """
    # In the future, you would fetch parcel data from the database here
    mock_parcel_data = {"id": parcel_id, "size_acres": 10}
    
    # Use a relative import to call your core logic
    analysis = run_permaculture_analysis(mock_parcel_data)
    
    return {"parcel_id": parcel_id, "analysis": analysis}