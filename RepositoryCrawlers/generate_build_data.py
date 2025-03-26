import os
import json
import pandas as pd
from dotenv import load_dotenv
from helper.api_access import retrieve_workflow_runs, retrieve_via_url
from helper.general_purpose import substract_and_format_time, transform_time
from helper.anonymizer import replace_all_user_occurences
import logging
load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)

# Setup
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
OWNER = os.getenv('OWNER')
REPO = os.getenv('REPO')
ENDPOINT = os.getenv('ENDPOINT')
MODE = os.getenv('MODE')
REPO_PATH = os.getenv('REPO_PATH')
PROJECT = os.getenv('PROJECT')
storage_path = os.getenv('STORAGE_PATH') + '/workflow_runs.csv'

# Get all runs
if MODE == "azure":
    workflow_runs = retrieve_workflow_runs(OWNER, PROJECT, ACCESS_TOKEN, endpoint= ENDPOINT, mode=MODE)
else:
    workflow_runs = retrieve_workflow_runs(OWNER, REPO, ACCESS_TOKEN, endpoint= ENDPOINT, mode=MODE)

# Safety net
# with open(storage_path.replace('.csv', '.json'), 'w') as file:
#     json.dump(workflow_runs, file)
# with open(storage_path.replace('.csv', '.json')) as file:
#     workflow_runs = json.load(file)
results = []
missing_keys = []

counter = 0

def get_github_run_values(run):
    missing_keys = []
    
    run_id = get_value(run, "id")
    name = get_value(run, "name")
    status = get_value(run, "status")
    trigger_event = get_value(run, "event")
    conclusion = get_value(run, "conclusion", "N/A")
    related_commit = get_value(run, "head_sha")
    attempts = get_value(run, "run_attempt", "N/A")
    created_at = get_value(run, "created_at")
    updated_at = get_value(run, "updated_at")
    
    triggering_actor = get_value(run, "triggering_actor", {})
    author = triggering_actor.get("login", "N/A") if isinstance(triggering_actor, dict) else "N/A"
    if author == "N/A":
        missing_keys.append("triggering_actor")
    
    if missing_keys:
        logging.debug(f"Missing keys in run {run_id}: {', '.join(missing_keys)}")
    
    created_at = transform_time(get_time("created_at"))
    updated_at = transform_time(get_time("updated_at"))
    
    time_until_completed = None
    try:
        if (status == "completed" and conclusion != "N/A") or (created_at != None and completed_at != None and conclusion != "N/A"):
            completed_at = updated_at
            time_until_completed = substract_and_format_time(created_at, completed_at)
        elif (created_at != None and updated_at != None):
            time_until_completed = substract_and_format_time(created_at, updated_at)
    except Exception as e:
        logging.error(f"Error processing run {run_id}: {e}")
    
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
        "time_until_updated": time_until_completed,
    }
    
def get_value(run, key, default="N/A"):
    value = run.get(key, default)
    if value == default:
        missing_keys.append(key)
    return value

def get_time(key, default="N/A"):
    val = get_value(run,key, default)
    return val[:-1] if isinstance(val, str) and val.endswith("Z") else val

def get_gitlab_run_values(run):
    missing_keys = []
    
    run_id = get_value(run, "id")
    name = get_value(run, "name")
    status = get_value(run, "status")
    trigger_event = get_value(run, "source")
    conclusion = "Not/Gitlab"
    related_commit = get_value(run, "sha")
    attempts = get_value(run, "attempts", "N/A")
    created_at = get_value(run, "created_at")
    updated_at = get_value(run, "updated_at")
    
    if missing_keys:
        logging.debug(f"Missing keys in run {run_id}: {', '.join(missing_keys)}")
    
    created_at = transform_time(get_time("created_at"))
    updated_at = transform_time(get_time("updated_at"))
    
    time_until_completed = None
    try:
        if created_at and updated_at:
            completed_at = updated_at
            time_until_completed = substract_and_format_time(created_at, completed_at)
    except Exception as e:
        logging.error(f"Error processing run {run_id}: {e}")
    
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
        "author": None,
        "time_until_updated": time_until_completed,
    }
    
def get_azure_run_values(pipelines):
    results = []
    if type(pipelines) != list:
        pipelines = [pipelines["value"]]
    for countvalue in pipelines:
        for value in countvalue['value']:
            name = value["name"]
            if  "id" in value:
                try:
                    runs = retrieve_via_url(OWNER,PROJECT,ACCESS_TOKEN, ending=f"pipelines/{value["id"]}/runs", endpoint=ENDPOINT, mode=MODE)
                except SyntaxError as se:
                    logging.warning(f"Syntax error with value id {value['id']}: {se}")
                except Exception as e:
                    logging.warning(f"Error retrieving runs for value id {value['id']}: {e}")
            else:
                logging.warning(f"No run ID in value {value} in {pipelines}")
                runs = None
            if type(runs) != list:
                runs = [runs["value"]]
            for runcountvalue in runs:
                for run in runcountvalue["value"]:
                    createdDate = transform_time(run["createdDate"])
                    finishedDate = transform_time(run["finishedDate"])
                    results.append(
                        {
                            "run_id": run['id'],
                            "name": f"{name}-{run['id']}",
                            "status": run['state'],
                            "trigger_event": "Not/Azure",
                            "conclusion": run["result"],
                            "related_commit": "Not/Azure",
                            "attempts": "Not/Azure",
                            "created_at": createdDate,
                            "last_updated_at": finishedDate,
                            "author": "Not/Azure",
                            "time_until_updated": substract_and_format_time(createdDate, finishedDate) if run["finishedDate"] and run["createdDate"] else "N/A",
                        }
                    )
    return results
    

if MODE == "azure" and workflow_runs != {} and workflow_runs != []:
    results = get_azure_run_values(workflow_runs)

else:
    # Format all runs
    for run in workflow_runs:
        counter += 1
        if counter % 100 == 0:
            logging.info(f'Processed {counter} workflow runs so far')
        
        if not run:
            continue
        
        if "created_at" not in run:
            logging.debug('Run does not contain "created_at" field: %s', run)
            continue
        
        if MODE == "github":
            results.append(get_github_run_values(run))
        elif MODE == "gitlab":
            results.append(get_gitlab_run_values(run))

# Store
df = pd.DataFrame(results)
if len(df) > 0:
    df = replace_all_user_occurences(df, repo_path=REPO_PATH)
    
    df.to_csv(storage_path, index=False)
else:
    logging.warning(f"No Builds/Workflows found for {REPO}.")
