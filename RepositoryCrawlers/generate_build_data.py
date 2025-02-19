import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.api_access import retrieve_workflow_runs
from helper.console_access import substract_and_format_time
import json
import logging
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Setup
ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
OWNER = os.getenv('OWNER')
REPO = os.getenv('REPO')
storage_path = os.getenv('STORAGE_PATH') + '/workflow_runs.csv'

# Get all runs
workflow_runs = retrieve_workflow_runs(OWNER, REPO, ACCESS_TOKEN)
# Safety net
with open(storage_path.replace('.csv', '.json'), 'w') as file:
    json.dump(workflow_runs, file)
# with open(storage_path.replace('.csv', '.json')) as file:
#     workflow_runs = json.load(file)
results = []

logging.info(len(workflow_runs))
counter = 0

def get_run_values(run):
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
        logging.warning(f"Missing keys in run {run_id}: {', '.join(missing_keys)}")
    
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

# Format all runs
for run in workflow_runs:
    counter+=1
    if counter % 100 == 0:
        logging.info(f'Processed {counter} workflow runs so far')
    
    if not run:
        continue
    
    if not 'created_at' in run:
        logging.warning('Run does not contain "created_at" field: %s', run)
        continue

    # Add information to results
    results.append(get_run_values(run))

# Store
df = pd.DataFrame(results)
df.to_csv(storage_path, index=False)
