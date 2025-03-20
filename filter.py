import os
import pandas as pd
import logging
import shutil
from RepositoryCrawlers.helper.anonymizer import replace_all_user_occurences
from dotenv import load_dotenv

load_dotenv(override=True)

REPO_PATH = os.getenv('REPO_PATH')

input_path = 'store/'
output_path = 'store-anon/'

filter_columns = {
    'branches.csv': ['created_by', 'last_author'],
    'commits.csv': ['author'],
    'pull_requests.csv': ['author', 'merged_by', 'requested_reviewers', 'assignees'],
    'releases.csv': ['author'],
}

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_unique_values(df, filter_columns):
    for column in filter_columns:
        if column in df.columns:
            unique_values = df[column].dropna().unique()
            logging.debug(f'Unique values in column {column}: {unique_values}')

def anonymize_files(input_path, output_path, filter_columns):
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
            
            if file_name in filter_columns:
                try:
                    # Read the CSV file
                    df = pd.read_csv(file_path)
                    
                    # Log unique values of filter columns
                    log_unique_values(df, filter_columns[file_name])
                    
                    # Anonymize the data
                    df = replace_all_user_occurences(df, repo_path=REPO_PATH, use_custom_mapping=True, filter_columns=filter_columns[file_name])
                    
                    # Save the anonymized data to the output path
                    df.to_csv(output_file_path, index=False)
                except:
                    logging.error(f'No file content in {file_path}')
            elif file_name.endswith('.csv') or file_name.endswith('.json'):
                # Copy CSV or JSON files as they are
                shutil.copy(file_path, output_file_path)

# Run the anonymization process
anonymize_files(input_path, output_path, filter_columns)