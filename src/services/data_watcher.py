import os
import yaml
import fiona
import time

# Directory where you will drop new GIS files
DOWNLOADS_DIR = "./data"
# The main config file that the importer uses
CONFIG_FILE = "data_config.yaml"

def load_existing_config(file_path):
    """Loads the current YAML config to avoid adding duplicates."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or []
    except FileNotFoundError:
        return []

def get_existing_filepaths(config_data):
    """Returns a set of file paths that are already in the config."""
    return {item.get('file_path') for item in config_data}

def scan_for_new_data():
    """
    Scans the DOWNLOADS_DIR, identifies new GIS files, and updates the config.
    """
    print(f"Scanning for new files in '{DOWNLOADS_DIR}'...")
    
    if not os.path.exists(DOWNLOADS_DIR):
        print("Data directory not found. Please create it.")
        os.makedirs(DOWNLOADS_DIR)
        return

    config_data = load_existing_config(CONFIG_FILE)
    existing_files = get_existing_filepaths(config_data)
    
    new_items_added = False

    for filename in os.listdir(DOWNLOADS_DIR):
        if filename in existing_files:
            continue # Skip files already in the config

        full_path = os.path.join(DOWNLOADS_DIR, filename)
        
        # Check if it's a recognized GIS file/folder
        if filename.endswith(('.gpkg', '.shp', '.gdb')):
            print(f"Found new item: {filename}")
            new_items_added = True
            try:
                # Inspect the file to get layer names
                layers = fiona.listlayers(full_path)
                
                # Create a new entry for each layer
                for layer in layers:
                    new_entry = {
                        'state_code': "TODO", # Placeholder to be filled in manually
                        'file_path': os.path.join(os.path.basename(DOWNLOADS_DIR), filename),
                        'layer_name': layer,
                        'table_name': f"new_{layer.lower()}_{int(time.time())}", # Create a unique placeholder name
                        'is_spatial': True
                    }
                    config_data.append(new_entry)
                
                print(f"  > Added {len(layers)} layer(s) from {filename} to config.")

            except Exception as e:
                print(f"  > Could not process {filename}. Error: {e}")

    # Write the updated data back to the YAML file
    if new_items_added:
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        print(f"\n✅ Successfully updated '{CONFIG_FILE}'. Please review and edit placeholders.")
    else:
        print("No new data files found.")


if __name__ == "__main__":
    scan_for_new_data()