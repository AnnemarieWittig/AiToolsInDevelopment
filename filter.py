import os
import pandas as pd
import logging
import shutil
from RepositoryCrawlers.helper.anonymizer import replace_all_user_occurences
from dotenv import load_dotenv

load_dotenv(override=True)

repo_list = 'done.csv'
input_path = 'store'
output_path = 'store-anon'

filter_columns = {
    'branches.csv': ['created_by', 'last_author'],
    'commits.csv': ['author'],
    'pull_requests.csv': ['author', 'merged_by', 'requested_reviewers', 'assignees'],
    'releases.csv': ['author'],
}

# Read the repo list
repo_df = pd.read_csv(repo_list)
repo_mapping = {f"{row['STORAGE_PATH']}\\{row['REPO']}".replace(".\\", ""): row['REPO_PATH'] for index, row in repo_df.iterrows()}

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_unique_values(df, filter_columns):
    for column in filter_columns:
        if column in df.columns:
            unique_values = df[column].dropna().unique()
            logging.debug(f'Unique values in column {column}: {unique_values}')

def anonymize_files(input_path, output_path, filter_columns, repo_mapping):
    for root, dirs, files in os.walk(input_path):
        # Create corresponding directories in the output path
        for directory in dirs:
            input_dir_path = os.path.join(root, directory)
            output_dir_path = os.path.join(output_path, os.path.relpath(input_dir_path, input_path))
            os.makedirs(output_dir_path, exist_ok=True)

        for file_name in files:
            file_path = os.path.join(root, file_name)
            output_file_path = os.path.join(output_path, os.path.relpath(file_path, input_path))
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

            # Determine the corresponding repo path
            storage_path = os.path.commonpath([input_path, root])
            repo_path = repo_mapping.get(root, None)
            
            if not repo_path:
                logging.warning(f'No REPO_PATH found for {storage_path}, skipping file {file_path}')
                continue
            
            if file_name in filter_columns:
                try:
                    # Read the CSV file
                    df = pd.read_csv(file_path)
                    
                    # Log unique values of filter columns
                    log_unique_values(df, filter_columns[file_name])
                    
                    # Anonymize the data
                    df = replace_all_user_occurences(df, repo_path=repo_path, use_custom_mapping=True, filter_columns=filter_columns[file_name])
                    
                    # Save the anonymized data to the output path
                    df.to_csv(output_file_path, index=False)
                except Exception as e:
                    logging.error(f'Error processing file {file_path}: {e}')
            elif file_name.endswith('.csv') or file_name.endswith('.json'):
                # Copy CSV or JSON files as they are
                shutil.copy(file_path, output_file_path)

# Run the anonymization process
anonymize_files(input_path, output_path, filter_columns, repo_mapping)