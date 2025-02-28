import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.anonymizer import replace_all_user_occurences
from helper.general_purpose import substract_and_format_time
import ijson
import logging
import json

load_dotenv()
logging.basicConfig(level=logging.ERROR)

# Setup
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
OWNER = os.getenv('OWNER')
REPO = os.getenv('REPO')
REPO_PATH = os.getenv('REPO_PATH')
storage_path = os.getenv('STORAGE_PATH') + '/workflow_runs.csv'

json_file_path = storage_path.replace('.csv', '.json')

results = []
counter = 0
missings = []

def check_value_presence(run):
    missing_keys = []
    
    def get_value(key, default="N/A"):
        """Fetch key value and log if missing."""
        if key not in run:
            missing_keys.append(key)
            return default
        return run[key]
    
    def get_time(key, default="N/A"):
        val = get_value(key, default)
        return val[:-1] if val != default else default
    
    # Extract required values
    run_id = get_value("id")
    name = get_value("name")
    status = get_value("status")
    trigger_event = get_value("event")
    conclusion = get_value("conclusion", "N/A")
    related_commit = get_value("head_sha")  # `head_sha` should always be a string
    attempts = get_value("run_attempt")
    created_at = get_value("created_at")
    updated_at = get_value("updated_at")

    # Handle `triggering_actor` safely
    triggering_actor = get_value("triggering_actor", {})
    author = triggering_actor.get("login", "N/A") if isinstance(triggering_actor, dict) else "N/A"

    if author == "N/A":
        missing_keys.append("triggering_actor")

    # Log any missing values
    if missing_keys:
        logging.debug(f"Missing keys in run {run_id}: {', '.join(missing_keys)}")
        missings.append(run)
    
    # Compute time_until_completed safely
    time_until_completed = "N/A"
    
    created_at = datetime.fromisoformat(get_time("created_at"))
    updated_at = datetime.fromisoformat(get_time("updated_at"))
    
    # Calculate time until completed
    time_until_completed = None
    if run["status"] == "completed" and run.get("conclusion"):
        completed_at = updated_at
        time_until_completed = substract_and_format_time(created_at, completed_at)

    return {
        "run_id": run_id,
        "name": name,
        "status": status,
        "trigger_event": trigger_event,
        "conclusion": conclusion,
        "related_commit": related_commit,
        "attempts": attempts,
        "created_at": created_at,
        "last_updated_at": updated_at,
        "author": author,
        "time_until_completed": time_until_completed,
    }

with open(json_file_path, "r", encoding="utf-8") as file:
    parser = ijson.items(file, "item")  # Stream each top-level item (assuming a list of runs)
    for run in parser:
        counter += 1
        if counter % 1000 == 0:
            logging.info(f'Processed {counter} workflow runs so far')
        
        if not run:
            continue
        
        if "created_at" not in run:
            logging.debug('Run does not contain "created_at" field: %s', run)
            continue
        
        # Add information to results
        results.append(check_value_presence(run))

# Store in CSV
logging.info(f'Total processed workflow runs: {counter}')
df = pd.DataFrame(results)
if len (df) > 1:
    df = replace_all_user_occurences(df, REPO_PATH)
df.to_csv(storage_path, index=False)

with open(storage_path.replace(".csv", "_missing_values.json"), "w") as f:
    json.dump(missings, f)