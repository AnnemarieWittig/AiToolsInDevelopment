import subprocess
import json
import requests

URL_ENDING_PULLS = "pulls"
URL_ENDING_ISSUES = "issues"
URL_ENDING_COMMITS = "commits"
URL_ENDING_TREES = "git/trees/{tree_sha}"
URL_ENDING_BLOBS = "git/blobs/{blob_sha}"

def retrieve_via_url (owner, repo, access_token, ending, parameters={}):
    url = f"https://api.github.com/repos/{owner}/{repo}/{ending}"

    payload = {}
    headers = {
    'Accept': 'application/vnd.github+json',
    'Authorization': f'Bearer {access_token}',
    'X-GitHub-Api-Version': '2022-11-28'
    }

    response = requests.request("GET", url, headers=headers, data=payload, params=parameters)
    result = response.json()
    
    return result

def run_git_command(args, cwd=None):
    """Run a Git command and return its output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(e.cmd)}\n{e.stderr}")
        return None

def retrieve_commits(parameters={}, repo_path="."):
    """Retrieve commits using Git command line."""
    # Construct the git log command
    git_args = ["log", "--pretty=format:%H,%an,%ad,%s", "--date=iso"]
    
    # Add additional parameters (e.g., since, until)
    if "since" in parameters:
        git_args.append(f"--since={parameters['since']}")
    if "until" in parameters:
        git_args.append(f"--until={parameters['until']}")
    
    git_args.append("--")
    
    output = run_git_command(git_args, cwd=repo_path)
    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        sha, author, date, message = line.split(",", 3)
        commits.append({
            "sha": sha,
            "author": author,
            "date": date,
            "message": message
        })
    
    return commits

def retrieve_commit_stats(commit_hash, repo_path="."):
    """Retrieve stats for a specific commit."""
    git_args = ["show", "--stat", "--oneline", commit_hash]
    output = run_git_command(git_args, cwd=repo_path)
    if not output:
        return {"loc_added": 0, "loc_removed": 0}

    # Parse output for lines of code added and removed
    lines = output.split("\n")
    stats = lines[-1] if lines else ""
    loc_added = loc_removed = 0
    if "insertions(+)" in stats or "deletions(-)" in stats:
        loc_added = int(stats.split(" insertion")[0].split()[-1]) if "insertion" in stats else 0
        loc_removed = int(stats.split(" deletion")[0].split()[-1]) if "deletion" in stats else 0
    
    return {"loc_added": loc_added, "loc_removed": loc_removed}
