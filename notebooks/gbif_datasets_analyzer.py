import pandas as pd

# Load the TSV file into a pandas DataFrame
try:
    df = pd.read_csv('gbif_datasets.tsv', sep='\t', error_bad_lines=False)
except Exception as e:
    print(f"Error reading TSV: {e}")
    # Handle error, maybe the separator is different or file is corrupt.
    # For now, we'll exit if it fails.
    exit()

# --- Filtering Criteria ---
# 1. Dataset Class: We want 'occurrence' data.
is_occurrence = df['dataset_class'] == 'occurrence'

# 2. Taxonomic Focus: Look for datasets focused on 'Plantae' (plants).
# We search for 'plantae' in the description or title as a proxy.
contains_plants = df['description'].str.contains('plantae|flora|vascular plants|botany', case=False, na=False) | \
                  df['title'].str.contains('plantae|flora|vascular plants|botany', case=False, na=False)

# 3. Geographic Focus: Target North America or the USA.
# Search for relevant keywords in the description or title.
is_relevant_geo = df['description'].str.contains('new york|united states|north america', case=False, na=False) | \
                    df['title'].str.contains('new york|united states|north america', case=False, na=False)

# 4. Reputable Publishers: Prefer data from institutions like botanical gardens, universities, and governments.
reputable_publishers = ['new york botanical garden', 'usgs', 'university', 'usda', 'forest service', 'us national herbarium']
is_reputable = df['publishing_organization_title'].str.contains('|'.join(reputable_publishers), case=False, na=False)


# --- Apply Filters ---
filtered_df = df[is_occurrence & contains_plants & is_relevant_geo & is_reputable]

# --- Rank and Select ---
# Rank by the number of records, which indicates a more comprehensive dataset.
# 'occurrence_count' is a likely column name, adjust if different in your file.
if 'occurrence_count' in filtered_df.columns:
    sorted_df = filtered_df.sort_values(by='occurrence_count', ascending=False)
else:
    # If there is no count, we just use the filtered list.
    sorted_df = filtered_df

# --- Display Top Recommendations ---
print("--- Top Recommended GBIF Datasets for Your Platform ---")
# Print the most relevant columns for the top 15 datasets
print(sorted_df[['key', 'title', 'publishing_organization_title', 'occurrence_count']].head(15).to_string())

# The 'key' column is the dataset's unique identifier (a UUID) you would use with the GBIF API.