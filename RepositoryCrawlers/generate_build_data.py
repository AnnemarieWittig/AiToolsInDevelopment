import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.api_access import retrieve_workflow_runs
from helper.standard import substract_and_format_time
import json
load_dotenv()

ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
OWNER = os.getenv('OWNER')
REPO = os.getenv('REPO')

workflow_runs = retrieve_workflow_runs(OWNER, REPO, ACCESS_TOKEN)
results = []
# print(json.dumps(workflow_runs[0]))
for run in workflow_runs:
    if not run:
        continue
    created_at = datetime.fromisoformat(run['created_at'][:-1])
    updated_at = datetime.fromisoformat(run['updated_at'][:-1])

    # Calculate time until completed
    time_until_completed = None
    if run['status'] == 'completed' and run['conclusion']:
        completed_at = datetime.fromisoformat(run['updated_at'][:-1])
        time_until_completed = substract_and_format_time(created_at, completed_at)

    # Add information to results
    results.append({
        'run_id': run['id'],
        'name': run['name'],
        'status': run['status'],
        'trigger_event': run['event'],
        'conclusion': run.get('conclusion', 'N/A'),
        'related_commit': run['head_sha']['id'] if 'id' in run['head_sha'] else run['head_sha'],
        'attempts': run['run_attempt'],
        'created_at': run['created_at'],
        'updated_at': run['updated_at'],
        'author': run['triggering_actor']['login'],
        'time_until_completed': time_until_completed
    })

df = pd.DataFrame(results)
df.to_csv('workflow_runs.csv', index=False)
