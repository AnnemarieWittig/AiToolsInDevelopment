import subprocess
import json
import requests
import base64
from datetime import datetime

URL_ENDING_PULLS = "pulls"
URL_ENDING_ISSUES = "issues"
URL_ENDING_COMMITS = "commits"
URL_ENDING_TREES = "git/trees/{tree_sha}"
URL_ENDING_BLOBS = "git/blobs/{blob_sha}"

def substract_and_format_time(start, end):
    time_diff = end - start
    days = time_diff.days
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    formatted_time = f"{days:02}:{hours:02}:{minutes:02}:{seconds:02}"
    return formatted_time

def run_git_command(args, cwd=None, repo_path=None):
    """Run a Git command and return its output.
    
    Supports running commands with a specified repository path (repo_path) or a working directory (cwd).
    """
    base_args = []
    if repo_path:
        base_args.extend([
            f"--git-dir={repo_path}/.git",
            f"--work-tree={repo_path}"
        ])
    
    try:
        result = subprocess.run(
            ["git"] + base_args + args,
            cwd=cwd,  # cwd is still supported for backward compatibility
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # Get raw bytes, not text
            check=True
        )
        # Attempt to decode with UTF-8, fallback to 'latin-1' if needed
        try:
            return result.stdout.decode('utf-8').strip()
        except UnicodeDecodeError:
            return result.stdout.decode('latin-1').strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(e.cmd)}\n{e.stderr.decode('utf-8', errors='ignore')}")
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
    """Retrieve stats for a specific commit, including accurate modified lines."""
    loc_added = loc_deleted = 0

    # Step 1: Run `git show --numstat` for quick additions/deletions
    numstat_args = ["show", "--numstat", "--format=", commit_hash]
    numstat_output = run_git_command(numstat_args, cwd=repo_path)
    if numstat_output:
        for line in numstat_output.splitlines():
            if line.strip():
                parts = line.split("\t")
                if len(parts) == 3:
                    added = int(parts[0]) if parts[0] != "-" else 0
                    deleted = int(parts[1]) if parts[1] != "-" else 0
                    loc_added += added
                    loc_deleted += deleted

    return {"loc_added": loc_added, "loc_deleted": loc_deleted}

def retrieve_commit(commit_hash, repo_path="."):
    """Retrieve details for a specific commit."""
    git_args = ["show", "--pretty=format:%H,%an,%ad,%s", "--date=iso", commit_hash]
    output = run_git_command(git_args, cwd=repo_path)

    if not output:
        return None

    commit_info = output.splitlines()[0].split(",")
    return {
        "sha": commit_info[0],
        "author": commit_info[1],
        "date": commit_info[2],
        "message": commit_info[3]
    }

def retrieve_commit_file_changes(commit_hash, repo_path="."):
    """Retrieve file-specific changes (lines added/deleted) for a given commit, including file SHAs."""
    # Step 1: Use `git diff-tree` to get file changes for a commit
    git_diff_args = ["diff-tree", "--no-commit-id", "--numstat", "-r", commit_hash]
    diff_output = run_git_command(git_diff_args, cwd=repo_path)

    # Step 2: Use `git ls-tree` to get the SHA for all files in the commit
    git_ls_tree_args = ["ls-tree", "-r", commit_hash]
    ls_tree_output = run_git_command(git_ls_tree_args, cwd=repo_path)

    # Create a dictionary of file paths to SHAs from the ls-tree output
    file_sha_map = {}
    if ls_tree_output:
        for line in ls_tree_output.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                file_sha = parts[2]  # The third part is the SHA
                file_path = parts[3]  # The fourth part is the file path
                file_sha_map[file_path] = file_sha

    # Step 3: Parse the diff-tree output to gather changes with SHAs
    file_changes = []
    if diff_output:
        for line in diff_output.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                added = int(parts[0]) if parts[0] != "-" else 0
                deleted = int(parts[1]) if parts[1] != "-" else 0
                file_path = parts[2]

                # Get the file SHA from the map created from ls-tree
                file_sha = file_sha_map.get(file_path)
                
                # Calculate changed lines for this file using the new function
                file_changes_stats = calculate_file_changes(commit_hash, file_path, repo_path=repo_path)
                
                result = {
                    "file_path": file_path,
                    "loc_added": added,
                    "loc_removed": deleted,
                    "file_sha": file_sha
                } | file_changes_stats

                file_changes.append(result)
            else:
                print(f"Skipping line: {line}")

    return file_changes

def calculate_file_changes(commit_hash, file_path, repo_path="."):
    """Calculate the number of lines added, deleted, and changed for a given file in a commit."""
    # Run git diff with --word-diff to calculate changes
    git_diff_args = ["diff", "--word-diff-regex=.", f"{commit_hash}^!", "--", file_path]
    diff_output = run_git_command(git_diff_args, cwd=repo_path)

    if not diff_output:
        return {"loc_added": 0, "loc_removed": 0, "loc_changed": 0}

    added_lines = 0
    removed_lines = 0
    changed_lines = 0

    for line in diff_output.splitlines():
        stripped_line = line.strip()
        
        # Count Added Lines
        if stripped_line.startswith("{+") and stripped_line.endswith("+}"):
            # Ensure there are no additional markers within the line
            inner_content = stripped_line[2:-2].strip()
            if "{+" not in inner_content and "+}" not in inner_content:
                added_lines += 1
            else:
                changed_lines += 1

        # Count Removed Lines
        elif stripped_line.startswith("[-") and stripped_line.endswith("-]") and stripped_line.count("[-") == 1 and stripped_line.count("-]") == 1:
            # Ensure there are no additional markers within the line
            inner_content = stripped_line[2:-2].strip()
            if "[-" not in inner_content and "-]" not in inner_content:
                removed_lines += 1

        # Count Modified Lines
        elif ("{+" in stripped_line and "+}" in stripped_line) or ("[-" in stripped_line and "-]"):
            changed_lines += 1
                
        else:
            print(stripped_line)

    return {
        "calculated_loc_added": added_lines,
        "calculated_loc_removed": removed_lines,
        "calculated_loc_changed": changed_lines
    }

# def retrieve_commit_file_changes_with_status(commit_hash, repo_path="."):
#     """Retrieve file-specific changes with status for a given commit."""
#     git_args = ["diff-tree", "--no-commit-id", "--name-status", "-r", commit_hash]
#     output = run_git_command(git_args, cwd=repo_path)
    
#     file_changes = []
#     if output:
#         for line in output.splitlines():
#             parts = line.split("\t")
#             if len(parts) >= 2:
#                 status = parts[0]
#                 file_path = parts[1]
#                 renamed_from = None

#                 # If the file was renamed, `git diff-tree` output includes the original path
#                 if status == "R" and len(parts) == 3:
#                     renamed_from = parts[1]
#                     file_path = parts[2]

#                 file_changes.append({
#                     "file_path": file_path,
#                     "status": status,
#                     "renamed_from": renamed_from
#                 })
#     return file_changes

def retrieve_file_content(commit_hash, file_path, repo_path="."):
    """Retrieve the content of a file at a specific commit."""
    # Verify if the file exists in the commit
    verify_args = ["ls-tree", "-r", "--name-only", commit_hash]
    files_in_commit = run_git_command(verify_args, repo_path=repo_path)
    
    if file_path not in files_in_commit.splitlines():
        print(f"Skipping: File {file_path} does not exist in commit {commit_hash}")
        return None
    
    # If it exists, proceed to show the file
    git_args = ["show", f"{commit_hash}:{file_path}"]
    return run_git_command(git_args, repo_path=repo_path)


def retrieve_pull_requests(repo_path):
    # Fetch pull request references from the remote repository to ensure they are available locally
    fetch_args = ["fetch", "origin", "+refs/pull/*:refs/remotes/origin/pull/*"]
    run_git_command(fetch_args, repo_path=repo_path)

    # Retrieve all PR refs using git for-each-ref
    pr_refs_args = ["for-each-ref", "--format=%(refname)", "refs/remotes/origin/pull"]
    pr_refs_output = run_git_command(pr_refs_args, repo_path=repo_path)

    pull_requests = []
    if pr_refs_output:
        for ref in pr_refs_output.splitlines():
            pr_number = ref.split("/")[-2]
            pr_log_args = ["log", "--pretty=format:%H,%an,%ad,%s", "--date=iso-strict", f"{ref}"]
            pr_log_output = run_git_command(pr_log_args, repo_path=repo_path)

            if pr_log_output:
                pr_lines = pr_log_output.splitlines()
                pr_info = pr_lines[0].split(",")
                sha = pr_info[0]
                author = pr_info[1]
                created_at = pr_info[2]
                title = pr_info[-1].strip()  # Extract title from the commit message

                # Get the merge commit SHA
                merge_commit_args = ["log", "--merges", "--pretty=format:%H", "--grep", f'#{pr_number}']
                merge_commit_output = run_git_command(merge_commit_args, repo_path=repo_path)
                merge_commit_sha = merge_commit_output.strip().split('\n')[0] if merge_commit_output else None

                # Get the list of commits contained in the pull request
                commits_args = ["rev-list", "--first-parent", f'{merge_commit_sha}^1..{merge_commit_sha}^2'] if merge_commit_sha else []
                commits_output = run_git_command(commits_args, repo_path=repo_path) if commits_args else ""
                commits = commits_output.strip().split('\n') if commits_output else []

                # Get diff statistics
                diff_stats_args = ["diff", "--shortstat", f'{merge_commit_sha}^1..{merge_commit_sha}'] if merge_commit_sha else []
                diff_stats_output = run_git_command(diff_stats_args, repo_path=repo_path) if diff_stats_args else ""
                diff_stats = diff_stats_output.strip() if diff_stats_output else ""

                # Parse diff statistics
                lines_added = lines_deleted = files_changed = 0
                if diff_stats:
                    parts = diff_stats.split(',')
                    for part in parts:
                        print(part)
                        if 'files changed' in part or 'file changed' in part:
                            files_changed = int(part.strip().split()[0])
                        elif 'insertion' in part:
                            lines_added = int(part.strip().split()[0])
                        elif 'deletion' in part:
                            lines_deleted = int(part.strip().split()[0])

                # Get branch names
                branch_name_args = ["name-rev", "--name-only", merge_commit_sha] if merge_commit_sha else []
                branch_name_output = run_git_command(branch_name_args, repo_path=repo_path) if branch_name_args else ""
                branch_name = branch_name_output.strip() if branch_name_output else ""

                pull_requests.append({
                    'number': pr_number,
                    'sha': sha,
                    'author': author,
                    'created_at': created_at,
                    'title': title,
                    'merge_commit_sha': merge_commit_sha,
                    'commits': commits,
                    'files_changed': files_changed,
                    'lines_added': lines_added,
                    'lines_deleted': lines_deleted,
                    'branch_name': branch_name
                })
    return pull_requests

def retrieve_releases(repo_path):
    # Get all tags (assuming tags are used for releases)
    tags_args = ["tag"]
    tags_output = run_git_command(tags_args, repo_path=repo_path)

    releases = []
    if tags_output:
        for tag in tags_output.splitlines():
            # Get details for each tag
            tag_details_args = ["show", "--pretty=format:%H,%an,%ad,%s", "--date=iso-strict", tag]
            tag_details_output = run_git_command(tag_details_args, repo_path=repo_path)

            if tag_details_output:
                tag_info = tag_details_output.splitlines()[0].split(",")
                commit_sha = tag_info[0].strip()
                author = tag_info[1].strip()
                date = tag_info[2].strip()
                message = tag_info[3].strip()

                releases.append({
                    'tag': tag,
                    'sha': commit_sha,
                    'author': author,
                    'date': date,
                    'message': message
                })
    return releases



def retrieve_builds(repo_path):
    # Get all commits with build-related messages (assuming builds are marked by "build" keyword in commit messages)
    build_log_args = ["log", "--grep=build", "--pretty=format:%H,%an,%ad,%s", "--date=iso-strict"]
    build_log_output = run_git_command(build_log_args, repo_path=repo_path)

    builds = []
    if build_log_output:
        for line in build_log_output.splitlines():
            sha, author, date, message = line.split(",", 3)
            builds.append({
                'sha': sha.strip(),
                'author': author.strip(),
                'date': date.strip(),
                'message': message.strip()
            })
    return builds

def retrieve_branches(repo_path):
    # Fetch all branches from the remote repository to ensure they are available locally
    fetch_args = ["fetch", "--all"]
    run_git_command(fetch_args, repo_path=repo_path)

    # Retrieve all branches including remote branches using git branch --all
    branch_refs_args = ["branch", "--all", "--format=%(refname:short)"]
    branch_refs_output = run_git_command(branch_refs_args, repo_path=repo_path)

    branches = []
    if branch_refs_output:
        for branch_name in branch_refs_output.splitlines():
            # Retrieve commits in the branch
            commits_args = ["log", branch_name, "--pretty=format:%H", "--date=iso-strict"]
            commits_output = run_git_command(commits_args, repo_path=repo_path)

            commits = []
            first_commit_sha = None
            last_commit_sha = None
            branch_creator = None
            branch_creation_time = None

            if commits_output:
                for line in commits_output.splitlines():
                    sha = line.strip()
                    commits.append(sha)

                    # Track the first and last commit sha
                    if first_commit_sha is None:
                        first_commit_sha = sha
                    last_commit_sha = sha

            # Use git reflog to determine the actual creator of the branch for all branches
            reflog_args = ["reflog", "show", branch_name, "--pretty=format:%cn,%cd", "--date=iso-strict"]
            reflog_output = run_git_command(reflog_args, repo_path=repo_path)
            if reflog_output:
                first_reflog_entry = reflog_output.splitlines()[0]
                creator_name, creation_date_str = first_reflog_entry.split(",", 1)
                branch_creator = creator_name.strip()
                branch_creation_time = datetime.fromisoformat(creation_date_str.strip())

            branches.append({
                'branch_name': branch_name,
                'commits': commits,
                'creation_time': branch_creation_time.isoformat() if branch_creation_time else None,
                'creator': branch_creator,
                'first_commit_sha': first_commit_sha,
                'last_commit_sha': last_commit_sha,
            })

    return branches