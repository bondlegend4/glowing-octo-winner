# tests/conftest.py
import pytest
import json
import os
import shutil

def pytest_addoption(parser):
    parser.addoption(
        "--from-scratch", action="store_true", default=False, help="Reset 'imported' flags to false"
    )

@pytest.fixture
def temp_manifest(tmp_path, request):
    """Creates a temporary sources.json. Resets 'imported' if --from-scratch is used."""
    original_path = os.path.join('data', 'sources.json')
    temp_path = tmp_path / "sources_test.json"
    
    with open(original_path, 'r') as f:
        data = json.load(f)

    if request.config.getoption("--from-scratch"):
        # Iterate through datasets and reset imported status
        for definition in data.get('source_definitions', []):
            for category in definition.get('categories', []):
                for dataset in category.get('datasets', []):
                    dataset['imported'] = False
    
    with open(temp_path, 'w') as f:
        json.dump(data, f)
    
    return str(temp_path)