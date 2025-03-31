import subprocess
import json
from datetime import datetime
import logging
import concurrent.futures
import sys
import re

# Configure logging (file or console; adjust as needed)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def run_git_command(args, cwd=None, repo_path=None):
    """
    Run a Git command and return its output.

    Supports running commands with a specified repository path (repo_path) or a working directory (cwd).

    :param args: A list of arguments for the Git command.
    :type args: list
    :param cwd: The working directory where the command should be run. Defaults to None.
    :type cwd: str, optional
    :param repo_path: The path to the Git repository. If specified, the command will be run with this repository. Defaults to None.
    :type repo_path: str, optional

    :return: The output of the Git command, decoded as UTF-8 or 'latin-1' if UTF-8 decoding fails.
    :rtype: str
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
        if 'does not exist in' in str(e.stderr):
            logging.debug(f"Error running command: {' '.join(e.cmd)}")
            logging.debug(e.stderr)
            return None
        logging.error(f"Error running command: {' '.join(e.cmd)}")
        logging.error(e.stderr)
        return None

def run_console_command(args, path = '.'):
    """
    Run a console command and return its output.

    This function runs a console command in a specified working directory and returns its output.

    :param args: A list of arguments for the console command.
    :type args: list
    :param path: The working directory where the command should be run. Defaults to the current directory.
    :type path: str, optional

    :return: The output of the console command, decoded as UTF-8 or 'latin-1' if UTF-8 decoding fails.
    :rtype: str
    """
    try:
        working_directory = path
        result = subprocess.run(
            args,
            cwd=working_directory,
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
        if "Commit is directly on this branch" in str(e.stderr):
            return str(e.stderr)
        elif "git-when-merged" in ' '.join(e.cmd):
            logging.debug(f"Issue when checking time until branch was merged using  command: {' '.join(e.cmd)}")
            logging.debug(e.stderr)
            return None
        logging.error(f"Error running command: {' '.join(e.cmd)}")
        logging.error(e.stderr)
        return None

########################## Commit Retrievals
"""
Functions for retrieving commit data from a local Git repository
"""

def retrieve_commits(repo_path="."):
    """
    Retrieve all commits using Git command line.

    This function retrieves commit data from a Git repository, including the commit SHA, author, date, and message.

    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: A list of commit dictionaries, where each dictionary contains:
                {
                    "sha": str,
                    "author": str,
                    "date": str,
                    "message": str
                }
    :rtype: list
    """
    # 1. Get the total number of commits
    total_count_cmd = ["rev-list", "--all", "--count"]
    total_count_output = run_git_command(total_count_cmd, cwd=repo_path)
    if not total_count_output:
        logging.debug("Could not determine total commit count.")
        return []
    
    try:
        total_commits = int(total_count_output)
    except ValueError:
        logging.debug("Total commit count is not a valid integer.")
        return []

    logging.info(f"Total commits in repo: {total_commits}")

    # 2. Retrieve commit data
    # Format: each commit line contains: <sha>,<author>,<date>,<message>
    rev_list_cmd = [
        "rev-list",
        "--all",
        "--pretty=format:%H,%an,%ad,%s",
        "--date=iso"
    ]
    output = run_git_command(rev_list_cmd, cwd=repo_path)
    if not output:
        logging.debug("No commit data returned.")
        return []

    lines = output.splitlines()
    all_commits = []
    processed = 0

    for line in lines:
        # rev-list output often includes lines like "commit <sha>" 
        # when using --pretty, so skip them
        if line.startswith("commit "):
            continue
        
        parts = line.split(",", 3)
        if len(parts) == 4:
            sha, author, date, message = parts
            all_commits.append({
                "sha": sha.strip(),
                "author": author.strip(),
                "date": date.strip(),
                "message": message.strip()
            })

        processed += 1
        # Log progress every 1,000 commits (adjust as needed)
        if processed % 1000 == 0:
            logging.info(f"Processed {processed}/{total_commits} commits...")

    # One last log message confirming completion
    logging.info(f"Finished processing {processed} commits.")
    return all_commits

def get_full_information(commit_args):
    """
    Get full information for a commit.

    This function extracts the commit hash, commit time, and author from the commit arguments.

    :param commit_args: List of commit arguments.
    :type commit_args: list

    :return: A dictionary containing the commit hash, commit time, and author.
    :rtype: dict
    """
    return {
            'commit_hash': commit_args[0],
            'commit_time': commit_args[1],
            'author': commit_args[2],
        }

def retrieve_commit_stats(commit_hash, repo_path="."): 
    """
    Retrieve stats for a specific commit, including accurate modified lines.

    This function retrieves the number of lines added and deleted for a specific commit.

    :param commit_hash: The hash of the commit.
    :type commit_hash: str
    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: A dictionary containing the number of lines added and deleted.
    :rtype: dict
    """
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
    """
    Retrieve details for a specific commit.

    This function retrieves the SHA, author, date, and message for a specific commit.

    :param commit_hash: The hash of the commit.
    :type commit_hash: str
    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: A dictionary containing the commit details.
    :rtype: dict
    """
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
    """
    Retrieve file-specific changes (lines added/deleted) for a given commit, including file SHAs.

    This function retrieves the changes made to files in a specific commit, including the number of lines added and deleted, and the file SHAs.

    :param commit_hash: The hash of the commit.
    :type commit_hash: str
    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: A list of dictionaries containing file changes.
    :rtype: list
    """
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
            # else:
            #     print(f"Skipping line: {line}")

    return file_changes

def retrieve_commits_with_stats(
    parameters=None,
    repo_path=".",
    progress_interval=1000
):
    """
    Retrieve commits, including line-level stats, from a Git repository in a single pass.

    This method performs the following steps:
        1. Uses the 'git rev-list' command with optional parameters (e.g., 'since', 'until')
            to determine the total number of commits that match the given criteria.
        2. Invokes 'git log --numstat' with a custom pretty format to collect commit metadata,
            parent SHAs, and file-level added/deleted line counts, all in a single traversal.
        3. Parses the output line by line, aggregating additions and deletions per commit,
            and logging progress at regular intervals (e.g., every 1,000 commits).

    :param parameters: Dictionary of optional parameters to filter commits (e.g., {"since": "2023-01-01", "until": "2023-12-31"}).
                    Supported keys:
                        - "since": Commits more recent than a specific date (e.g., "2023-01-01")
                        - "until": Commits older than a specific date
                        - Add more keys if needed (e.g., "author", "grep", etc.) to extend functionality.
    :type parameters: dict, optional
    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional
    :param progress_interval: Number of commits to process before logging a progress message, defaults to 1000.
    :type progress_interval: int, optional

    :return: A list of commit dictionaries, where each dictionary contains:
                {
                    "sha": str,
                    "author": str,
                    "date": datetime,
                    "message": str,
                    "parents": list of parent SHAs,
                    "loc_added": int,
                    "loc_deleted": int
                }
    :rtype: list

    Example Usage:
        >>> retrieve_commits_with_stats(
                parameters={"since": "2023-01-01", "until": "2023-12-31"},
                repo_path="/path/to/repo",
                progress_interval=5000
            )
    """
    if parameters is None:
        parameters = {}

    # 1) Determine total commits matching the criteria with git rev-list
    rev_list_count_args = ["rev-list", "--count"]
    if "since" in parameters:
        rev_list_count_args.append(f"--since={parameters['since']}")
    if "until" in parameters:
        rev_list_count_args.append(f"--until={parameters['until']}")
    rev_list_count_args.append("--all")

    # Separator indicating the end of additional path arguments
    rev_list_count_args.append("--")

    try:
        total_count_output = run_git_command(rev_list_count_args, cwd=repo_path).strip()
        total_commits = int(total_count_output)
    except ValueError:
        total_commits = 0

    if total_commits == 0:
        logging.info("No commits found given the specified parameters.")
        return []

    logging.info(f"Total commits matching parameters: {total_commits}")

    # 2) Build the git log --numstat command in a single pass
    log_args = [
        "log",
        "--numstat",
        "--date=iso",
        "--pretty=format:COMMIT|%H|%an|%ad|%s|%P"
    ]

    # Add optional filters
    if "since" in parameters:
        log_args.append(f"--since={parameters['since']}")
    if "until" in parameters:
        log_args.append(f"--until={parameters['until']}")
    # Append other potential parameters if needed (e.g., author, grep, etc.)

    log_args.append("--all")
    log_args.append("--")

    output = run_git_command(log_args, cwd=repo_path)
    lines = output.splitlines()

    # 3) Parse the output
    detailed_commits = []
    current_commit = None
    processed = 0

    for line in lines:
        if line.startswith("COMMIT|"):
            # Store the previous commit
            if current_commit:
                detailed_commits.append(current_commit)

            parts = line.split("|", 6)
            if len(parts) < 6:
                continue

            sha = parts[1]
            author = parts[2]
            date_str = parts[3]
            message = parts[4]
            parent_shas = parts[5].split() if parts[5] else []

            current_commit = {
                "sha": sha,
                "author": author,
                "date": datetime.fromisoformat(date_str),
                "message": message,
                "parents": parent_shas,
                "loc_added": 0,
                "loc_deleted": 0,
            }

            processed += 1
            if processed % progress_interval == 0:
                logging.info(f"Processed {processed} of {total_commits} commits...")

        else:
            # Expecting numstat lines: <added>\t<deleted>\t<filename>
            parts = line.split("\t")
            if len(parts) == 3:
                added_str, deleted_str, _filename = parts
                added = int(added_str) if added_str.isdigit() else 0
                deleted = int(deleted_str) if deleted_str.isdigit() else 0
                if current_commit:
                    current_commit["loc_added"] += added
                    current_commit["loc_deleted"] += deleted

    # Add the last commit
    if current_commit:
        detailed_commits.append(current_commit)

    logging.info(f"Finished processing {processed} commits out of {total_commits} expected.")

    return detailed_commits

def retrieve_all_commits_with_stats_and_logging(repo_path="."):
    """
    Retrieve all commits (including parents, stats) in a single pass,
    and log progress at regular intervals.

    This function retrieves all commits from a Git repository, including parent SHAs and line-level stats, and logs progress at regular intervals.

    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: A list of commit dictionaries, where each dictionary contains:
                {
                    "sha": str,
                    "author": str,
                    "date": datetime,
                    "message": str,
                    "parents": list of parent SHAs,
                    "loc_added": int,
                    "loc_deleted": int
                }
    :rtype: list
    """
    # 1) Get total commit count so you know how many commits there are in total
    count_cmd = ["rev-list", "--all", "--count"]
    total_count_output = run_git_command(count_cmd, cwd=repo_path)
    try:
        total_commits = int(total_count_output.strip())
    except ValueError:
        total_commits = 0

    if total_commits == 0:
        logging.debug("No commits found in repository.")
        return []

    logging.info(f"Total commits: {total_commits}")

    # 2) Prepare a single git command to get all data in one pass
    #    Using a special delimiter (e.g., 'COMMIT|') for easy parsing.
    #    %P for parents; %an for author; %ad for date; %s for subject.
    git_cmd = [
        "log",
        "--all",
        "--numstat",
        "--date=iso-strict",
        "--pretty=format:COMMIT|%H|%ae|%ad|%s|%P"
    ]
    output = run_git_command(git_cmd, cwd=repo_path)

    detailed_commits = []
    current_commit = None
    processed = 0  # How many commits processed so far

    # 3) Parse the output line by line
    for line in output.splitlines():
        if line.startswith("COMMIT|"):
            # Save the previous commit (if any) before starting a new one
            if current_commit:
                detailed_commits.append(current_commit)

            # Parse commit metadata: COMMIT|<sha>|<author>|<date>|<message>|<parents...>
            parts = line.split("|")
            # Make sure we have at least 6 parts:
            #   0: "COMMIT"
            #   1: sha
            #   2: author
            #   3: date
            #   4: message
            #   5: parents
            if len(parts) < 6:
                continue

            sha = parts[1]
            author = parts[2]
            date_str = parts[3]
            message = parts[4]
            parent_shas = parts[5].split() if parts[5] else []
            
            # Explicit check here:
            if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha.lower()):
                logging.warning(f"Invalid commit SHA detected: '{sha}' in line: {line}")
                continue

            current_commit = {
                "sha": sha,
                "author": author,
                "date": datetime.fromisoformat(date_str),
                "message": message,
                "parents": parent_shas,
                "loc_added": 0,
                "loc_deleted": 0,
            }

            processed += 1
            # Log every 1,000 commits (adjust this interval as needed)
            if processed % 1000 == 0:
                logging.info(f"Processed {processed} of {total_commits} commits...")
        
        else:
            # Parse numstat lines: <added>\t<deleted>\t<filename>
            parts = line.split("\t")
            if len(parts) == 3:
                added_str, deleted_str, _filename = parts
                added = int(added_str) if added_str.isdigit() else 0
                deleted = int(deleted_str) if deleted_str.isdigit() else 0
                
                if current_commit is not None:
                    current_commit["loc_added"] += added
                    current_commit["loc_deleted"] += deleted
    
    # Add the last commit processed
    if current_commit:
        detailed_commits.append(current_commit)

    logging.info(f"Finished processing {processed} commits in total.")

    # Optional: Cross-check final count
    if processed != total_commits:
        logging.debug(f"Expected {total_commits} commits but only parsed {processed}")

    return detailed_commits

def calculate_diff_stats(repo_path, merge_commit_sha):
    """
    Calculate diff statistics for a single merge commit.

    This function calculates the number of files changed, lines added, and lines deleted for a specific merge commit.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str
    :param merge_commit_sha: The SHA of the merge commit.
    :type merge_commit_sha: str

    :return: A tuple containing the number of files changed, lines added, and lines deleted.
    :rtype: tuple
    """
    if not merge_commit_sha:
        return 0, 0, 0

    diff_stats_args = ["diff", "--shortstat", f"{merge_commit_sha}^1..{merge_commit_sha}"]
    diff_stats_output = run_git_command(diff_stats_args, repo_path=repo_path)

    lines_added = lines_deleted = files_changed = 0
    if diff_stats_output:
        parts = diff_stats_output.split(',')
        for part in parts:
            if 'files changed' in part or 'file changed' in part:
                files_changed = int(part.strip().split()[0])
            elif 'insertion' in part:
                lines_added = int(part.strip().split()[0])
            elif 'deletion' in part:
                lines_deleted = int(part.strip().split()[0])

    return files_changed, lines_added, lines_deleted

########################## Branch Retrievals
"""
Functions for retrieving branch data from a local Git repository
"""

def clear_branch_name(branch_name):
    """
    Clear and normalize the branch name.

    This function removes unnecessary parts from the branch name and normalizes it.

    :param branch_name: The name of the branch.
    :type branch_name: str

    :return: The normalized branch name.
    :rtype: str
    """
    return branch_name.split(' -> ')[-1].replace("* main", "").strip()

def grab_branch_name (ref):
    """
    Normalize the branch reference name.

    This function normalizes the branch reference name by removing unnecessary parts.

    :param ref: The branch reference name.
    :type ref: str

    :return: The normalized branch name.
    :rtype: str
    """
    ref = ref.replace("* main", "main").strip()
    if (ref.startswith("refs/heads/") or
        ref.startswith("refs/remotes/") or 
        ref.startswith("origin/") or
        ref.startswith("remotes/origin")):
        return ref.split("/", 2)[-1]
    elif ref.startswith("refs/remotes/") or ref.startswith("origin/"):
        return ref.split("/", 2)[-1]
    elif ref.startswith("HEAD -> "):
        return ref.split(" -> ", 1)[-1]
    else:
        if ref != "main":
            logging.debug(f"Unhandled reference format: {ref}")
        return ref.split("/", 2)[-1]
    
def validate_branch(branch_name):
    """
    Validate the branch name.

    This function checks if the branch name is valid and not a pull request or empty.

    :param branch_name: The name of the branch.
    :type branch_name: str

    :return: True if the branch name is valid, False otherwise.
    :rtype: bool
    """
    if (branch_name.startswith("origin/pull/") or 
        # branch_name.startswith("tag: ") or
        branch_name.startswith("remotes/origin/pull/") or
        branch_name == ""):
        return False
    return True

def retrieve_branch_information(branch_name, retrieval_arguments, repo_path, merged=False):
    """
    Retrieve information for a specific branch.

    This function retrieves commit information for a specific branch, including the first and last commit details.

    :param branch_name: The name of the branch.
    :type branch_name: str
    :param retrieval_arguments: The arguments to use for retrieving branch information.
    :type retrieval_arguments: list
    :param repo_path: Path to the local Git repository.
    :type repo_path: str
    :param merged: Indicates if the branch is merged, defaults to False.
    :type merged: bool, optional

    :return: A dictionary containing branch information.
    :rtype: dict
    """

    commits = []
    commits_on_branch = run_git_command(retrieval_arguments, repo_path=repo_path)
    
    if commits_on_branch:
    
        first_commit = None
        last_commit = None
        
        for commit in commits_on_branch.splitlines():
            commit_args = commit.split("'")
            if len(commit_args) < 3:
                logging.debug(f"Unvalid commit output for branch {branch_name} {commit}")
                continue    
            
            commits.append(commit_args[0])
            if first_commit is None:
                first_commit = get_full_information(commit_args)
                
            last_commit = get_full_information(commit_args)
        
        return {
            'branch_name': branch_name,
            'commits' : commits,
            'created_at' : first_commit['commit_time'],
            'created_by' : first_commit['author'],
            'first_commit_sha' : first_commit['commit_hash'],
            'last_active' : last_commit['commit_time'],
            'last_commit_sha' : last_commit['commit_hash'],
            'last_author' : last_commit['author'],
            'merged' : merged
            }
    return  {
            'branch_name': branch_name,
            'commits' : commits,
            'created_at' : None,
            'created_by' : None,
            'first_commit_sha' : None,
            'last_active' : None,
            'last_commit_sha' : None,
            'last_author' : None,
            'merged' : merged
            }
        
def format_fast_forwarded_branch(branch):
    """
    Format a fast-forwarded branch-object to be used in later retrieval.

    This function returns a dictionary with default values for a fast-forwarded branch.

    :param branch: The name of the branch.
    :type branch: str

    :return: A dictionary containing branch information with default values.
    :rtype: dict
    """
    return {
            'branch_name': branch,
            'commits' : None,
            'created_at' : None,
            'created_by_username' : None,
            'created_by' : None,
            'first_commit_sha' : None,
            'last_active' : None,
            'last_commit_sha' : None,
            'last_author' : None,
            'merged' : 'fast-forwarded'
            }
        
import os
def retrieve_branch_data_new(repo_path = ".", main_branch="main", path_to_environment = '.'):
    """
    Retrieve data for all branches in the repository.

    This function retrieves information for all branches in the repository, including unmerged and merged branches.

    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional
    :param main_branch: Name of the main branch, defaults to "main".
    :type main_branch: str, optional

    :return: A list of dictionaries containing branch information.
    :rtype: list
    """
    branch_args = ["branch", "--all", "--no-merged"]
    unmerged = run_git_command(branch_args, None, repo_path)
    
    unmerged_split = unmerged.splitlines()
    logging.info(f"Retrieved {len(unmerged_split)} unmerged branches.")
    branches = []
    
    for branch_name in unmerged_split:
        branch_name = branch_name.split(' -> ')[-1].strip()
        if validate_branch(branch_name):
            unmerged_args = ["show", "--summary", branch_name, "--pretty=format:%H'%ad'%an", "--date=iso-strict", "--no-patch", f"^{main_branch}"]
            branches.append(retrieve_branch_information(branch_name, unmerged_args,repo_path=repo_path))
    
    branch_args = ["branch", "--all", "--merged"]
    merged = run_git_command(branch_args, None, repo_path)
    merged_split = merged.splitlines()
    logging.info(f"Retrieved {len(merged_split)} unmerged branches.")
    
    for branch_name in merged_split:
        branch_name = clear_branch_name(branch_name)
        if validate_branch(branch_name):
            
            merge_sha = run_console_command([f"{path_to_environment}/git-when-merged", "-c", branch_name], path=repo_path)
            
            if merge_sha:
                if "Commit is directly on this branch" in merge_sha:
                    branches.append(format_fast_forwarded_branch(branch_name))
                else:
                    merged_args = ["log", f"{merge_sha}^-",  "--pretty=format:%H'%ad'%an", "--date=iso-strict"]
                    branches.append(retrieve_branch_information(branch_name, merged_args,repo_path=repo_path, merged=True))
            else:
                logging.debug(f"No merge sha for merged branch {branch_name}")
    
    main_args = ["log", main_branch, "--all", "--pretty=format:%H'%ad'%an", "--date=iso-strict"]
    branches.append(retrieve_branch_information(main_branch, main_args, repo_path=repo_path, merged=True))
    
    return branches

def process_commits_individually(commit_list, repo_path, branch_commits, error_path):
    """
    Process commits individually to determine their branches.

    This function processes a list of commits to determine which branches they belong to and logs unreferenced commits.

    :param commit_list: List of commit hashes to process.
    :type commit_list: list
    :param repo_path: Path to the local Git repository.
    :type repo_path: str
    :param branch_commits: Dictionary to store branch commits.
    :type branch_commits: dict
    :param error_path: Path to the file where unreferenced commits will be logged.
    :type error_path: str

    :return: Updated dictionary of branch commits.
    :rtype: dict
    """
    unreferenced_commits = []
    
    logging.info(f"Processing {len(commit_list)} commits for branches individually...")

    counter = 0
    for commit_hash in commit_list:
        counter += 1
        if counter % 1000 == 0:
            logging.info(f"Processed {counter} of {len(commit_list)} commits")
        try:
            # Check which branches contain the commit
            branches_args = ["branch", "-a", "--contains", commit_hash]
            branches_output = run_git_command(branches_args, repo_path=repo_path)

            if branches_output:
                # Add the commit to the relevant branches
                for branch_name in branches_output.splitlines():
                    branch_name = grab_branch_name(branch_name)  # Normalize branch name
                    branch_commits.setdefault(branch_name, []).append(commit_hash)
            else:
                # No branches contain this commit
                unreferenced_commits.append(commit_hash)
        except Exception as e:
            logging.error(f"Error processing commit {commit_hash}: {e}")
            unreferenced_commits.append(commit_hash)

    # Write unreferenced commits to an error file
    with open(error_path, "w") as error_file:
        for commit in unreferenced_commits:
            error_file.write(f"{commit}\n")
            
    return branch_commits

def retrieve_branches(repo_path):
    """
    Retrieve all branches from the repository.

    This function retrieves all branches from the remote repository to ensure they are available locally.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A list of dictionaries containing branch information.
    :rtype: list
    """
    # Fetch all branches from the remote repository to ensure they are available locally
    fetch_args = ["fetch", "--all"]
    run_git_command(fetch_args, repo_path=repo_path)

    # Retrieve all branches (local and remote) and their references
    branch_refs_args = ["for-each-ref", "--format=%(refname:short)"]
    branch_refs_output = run_git_command(branch_refs_args, repo_path=repo_path)

    length = len(branch_refs_output.splitlines())
    logging.info(f"Found {length} branch references.")

    # Retrieve all commits for all branches in one call
    commits_args = ["log", "--all", "--pretty=format:%H %D", "--no-merges", "--date=iso-strict"]
    commits_output = run_git_command(commits_args, repo_path=repo_path)

    branch_commits = {}
    pull_request_refs = {}
    check_manually = []

    for line in commits_output.splitlines():
        parts = line.split(" ", 1)
        
        if len(parts) < 2 or parts[1] == "":
            check_manually.append(parts[0])
            continue
        
        commit_hash = parts[0]
        refs = parts[1].split(", ") if len(parts) > 1 else []

        if refs:
            for ref in refs:
                if validate_branch(ref):
                    # Skip pull request references
                    branch_name = grab_branch_name(ref)
                    branch_commits.setdefault(branch_name, []).append(commit_hash)
                else:
                    if ref.startswith("tag: "):
                        check_manually.append(commit_hash)
                    else:
                        continue
        else:
            logging.debug(f"Commit {commit_hash} has no refs and is skipped.")

    branch_commits = process_commits_individually(check_manually, repo_path, branch_commits, "unreferenced_commits.txt")

    with open("branchding.json", "w") as f:
        json.dump(branch_commits, f, indent=4)
    
    # Retrieve reflog data for all branches in one call
    reflog_args = ["reflog", "show", "--all", "--pretty=format:%H,%cn,%cd", "--date=iso-strict"]
    reflog_output = run_git_command(reflog_args, repo_path=repo_path)

    branch_reflogs = {}
    for line in reflog_output.splitlines():
        sha, creator_name, creation_date_str = line.split(",", 2)
        branch_reflogs[sha] = (creator_name.strip(), creation_date_str.strip())

    branches = []
    counter = 0
    for branch_name in branch_refs_output.splitlines():
        counter += 1
        if counter % 100 == 0:
            logging.info(f"Processed {counter} of {length} branches")

        branch_name = grab_branch_name(branch_name)
        if branch_name == None or branch_name not in branch_commits:
            logging.debug(f"Skipping branch {branch_name} without commits.")
            continue
        commits = branch_commits.get(branch_name, [])
        first_commit_sha = commits[0] if commits else None
        last_commit_sha = commits[-1] if commits else None

        branch_creator, branch_creation_time = branch_reflogs.get(first_commit_sha, (None, None))
        if branch_creation_time:
            branch_creation_time = datetime.fromisoformat(branch_creation_time)

        branches.append({
            'branch_name': branch_name,
            'commits': commits,
            'creation_time': branch_creation_time.isoformat() if branch_creation_time else None,
            'creator': branch_creator,
            'first_commit_sha': first_commit_sha,
            'last_commit_sha': last_commit_sha,
        })

    return branches

########################## File information Retrievals
"""
Functions for retrieving file-specific data from a local Git repository
Due to the high amount of files in a repository per commit, these function can take up more time than others.
"""

def calculate_file_changes(commit_hash, file_path, repo_path="."):
    """
    Calculate the number of lines added, deleted, and changed for a given file in a commit.

    This function runs `git diff` with `--word-diff` to calculate the changes in a file for a specific commit.
    It String-matches the result to determine if an entire line was added, removed or if only parts were changed.

    :param commit_hash: The hash of the commit.
    :type commit_hash: str
    :param file_path: The path to the file.
    :type file_path: str
    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: A dictionary containing the number of lines added, removed, and changed.
    :rtype: dict
    """
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
            if ("{+" not in inner_content and "+}" not in inner_content) and ("[-" not in inner_content and "-]" not in inner_content):
                added_lines += 1
            else:
                changed_lines += 1

        # Count Removed Lines
        elif stripped_line.startswith("[-") and stripped_line.endswith("-]") and stripped_line.count("[-") == 1 and stripped_line.count("-]") == 1:
            # Ensure there are no additional markers within the line
            inner_content = stripped_line[2:-2].strip()
            if ("{+" not in inner_content and "+}" not in inner_content) and ("[-" not in inner_content and "-]" not in inner_content):
                removed_lines += 1
            else:
                changed_lines += 1

        # Count Modified Lines
        elif ("{+" in stripped_line and "+}" in stripped_line) or ("[-" in stripped_line and "-]"):
            changed_lines += 1
                
        # else:
        #     print(stripped_line)

    return {
        "calculated_loc_added": added_lines,
        "calculated_loc_removed": removed_lines,
        "calculated_loc_changed": changed_lines
    }

def retrieve_file_content(commit_hash, file_path, repo_path="."):
    """
    Retrieve the content of a file at a specific commit.

    This function retrieves the content of a file at a specific commit in the Git repository.

    :param commit_hash: The hash of the commit.
    :type commit_hash: str
    :param file_path: The path to the file.
    :type file_path: str
    :param repo_path: Path to the local Git repository, defaults to ".".
    :type repo_path: str, optional

    :return: The content of the file as a string, or None if the file does not exist in the commit.
    :rtype: str or None
    """
    # Verify if the file exists in the commit
    verify_args = ["ls-tree", "-r", "--name-only", commit_hash]
    files_in_commit = run_git_command(verify_args, repo_path=repo_path)
    
    if file_path not in files_in_commit.splitlines():
        # print(f"Skipping: File {file_path} does not exist in commit {commit_hash}")
        return None
    
    # If it exists, proceed to show the file
    git_args = ["show", f"{commit_hash}:{file_path}"]
    return run_git_command(git_args, repo_path=repo_path)

def retrieve_pull_requests(repo_path):
    """
    Retrieve pull requests from the repository.

    This function fetches pull request references from the remote repository and retrieves detailed information about each pull request.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A list of dictionaries containing pull request information.
    :rtype: list
    """
    # Fetch pull request references from the remote repository to ensure they are available locally
    fetch_args = ["fetch", "origin", "+refs/pull/*:refs/remotes/origin/pull/*"]
    run_git_command(fetch_args, repo_path=repo_path)

    # Retrieve all PR refs using git for-each-ref
    pr_refs_args = ["for-each-ref", "--format=%(refname)", "refs/remotes/origin/pull"]
    pr_refs_output = run_git_command(pr_refs_args, repo_path=repo_path)
    
    length = len(pr_refs_output.splitlines())
    logging.info(f"Found {length} pull request references.")
    counter = 0

    pull_requests = []
    if pr_refs_output:
        for ref in pr_refs_output.splitlines():
            counter += 1
            if counter % 100 == 0:
                logging.info(f"Processed {counter} of {length} pull requests")
            
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

########################## Build and Release Retrievals
"""
Functions for retrieving build and release data (using tags) from a local Git repository
"""

def get_tag_info_for_unusal_layouts(tag_output):
    tag_output.split

def retrieve_releases(repo_path):
    """
    Retrieve release information from the repository.

    This function fetches all tags (assuming tags are used for releases) from the repository and retrieves detailed information about each release.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A list of dictionaries containing release information.
    :rtype: list
    """
    # fetch_args = ["fetch", "--tags"]
    # run_git_command(fetch_args, repo_path=repo_path)

    tags_args = ["tag"]
    tags_output = run_git_command(tags_args, repo_path=repo_path)

    releases = []
    if tags_output:
        for tag in tags_output.splitlines():
            # Get details for each tag
            tag_details_args = ["show", "--pretty=format:%H|%ae|%ad|%s", "--date=iso-strict", tag]
            tag_details_output = run_git_command(tag_details_args, repo_path=repo_path)
            
            if tag_details_output:
                tag_information = tag_details_output.splitlines()
                for line in tag_information:
                    tag_info=line.split("|")
                    if len(tag_info) < 4:
                        continue
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
                    break
    return releases

def retrieve_builds(repo_path):
    """
    Retrieve build information from the repository.

    This function fetches all commits with build-related messages (assuming builds are marked by the "build" keyword in commit messages) from the repository and retrieves detailed information about each build.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A list of dictionaries containing build information.
    :rtype: list
    """
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

########################## Pull Request Retrievals
"""
Functions for retrieving pull request data from a local Git repository
"""

def retrieve_pr_metadata_bulk(repo_path):
    """
    Retrieve metadata for all PRs in a single bulk operation.

    This function uses `git for-each-ref` to get basic metadata for all pull requests.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A list of dictionaries containing pull request metadata.
    :rtype: list
    """
    # Use `git for-each-ref` to get basic metadata for all PRs
    pr_refs_args = [
        "for-each-ref",
        "--format=%(refname)|%(objectname)|%(authorname)|%(authordate)|%(subject)", 
        "refs/remotes/origin/pull"
    ]
    pr_refs_output = run_git_command(pr_refs_args, repo_path=repo_path)
    pr_metadata = []

    for line in pr_refs_output.splitlines():
        # logging.debug("\'" + line + "\'")
        parts = line.split("|", 4)
        
        if len(parts) < 5:
            continue
        
        ref, sha, author, date, title = parts
        pr_number = ref.split("/")[-2]
        pr_metadata.append({
            'number': pr_number,
            'sha': sha,
            'author': author,
            'created_at': date,
            'title': title.strip(),
            'ref': ref
        })

    return pr_metadata

def retrieve_pr_metadata_via_ls_remote(repo_path):
    """
    Retrieve metadata for all PRs in a single bulk operation.

    This function uses `git ls-remote` to get PR metadata from the remote.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A list of dictionaries containing pull request metadata.
    :rtype: list
    """
    # Run `git ls-remote origin` to get all refs
    pr_refs_output = run_git_command(["ls-remote", "origin"], repo_path=repo_path)
    pr_metadata = []

    for line in pr_refs_output.splitlines():
        parts = line.split("\t")  # Git output is tab-separated
        if len(parts) == 2 and "refs/pull/" in parts[1]:  # Cross-platform filtering
            sha, ref = parts
            pr_number = ref.split("/")[-2]  # Extract PR ID
            pr_metadata.append({
                'number': pr_number
            })

    return pr_metadata


def retrieve_pull_requests_parallel(repo_path, max_workers=5):
    """
    Retrieve pull request data using optimized and parallel processing.

    This function utilizes ThreadPoolExecutor for parallel I/O-bound operations to fetch pull request data.

    :param repo_path: Path to the local Git repository.
    :type repo_path: str
    :param max_workers: Maximum number of threads to use for parallel processing, defaults to 5.
    :type max_workers: int, optional

    :return: A list of dictionaries containing pull request information.
    :rtype: list
    """
    # Fetch pull request metadata in bulk
    pr_metadata = retrieve_pr_metadata_bulk(repo_path)
    if pr_metadata == []:
        pr_metadata = retrieve_pr_metadata_via_ls_remote(repo_path)
    total_refs = len(pr_metadata)
    logging.info(f"Found {total_refs} pull request references.")

    # Process PRs in parallel
    pull_requests = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pr = {
            executor.submit(process_single_pr, pr, repo_path): pr for pr in pr_metadata
        }

        for i, future in enumerate(concurrent.futures.as_completed(future_to_pr), start=1):
            pr = future_to_pr[future]
            try:
                pr_data = future.result()
                if pr_data:
                    pull_requests.append(pr_data)
            except Exception as e:
                logging.error(f"Failed to process PR {pr['number']}: {e}")
                sys.exit(1)  # Exit on failure to ensure no corrupted data processing

            if i % 100 == 0 or i == total_refs:
                logging.info(f"Grabbed {i} of {total_refs} pull requests IDs...")

    logging.info(f"Finished grabbing all {total_refs} pull request IDs.")
    return pull_requests

def process_single_pr(pr, repo_path):
    """
    Process a single pull request.

    This function processes a single pull request to retrieve its merge commit SHA, files changed, lines added, and lines deleted.

    :param pr: A dictionary containing pull request metadata.
    :type pr: dict
    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A dictionary containing updated pull request information.
    :rtype: dict
    """
    pr_number = pr['number']
    merge_commit_args = ["log", "--merges", "--pretty=format:%H", "--grep", f'#{pr_number}']
    merge_commit_output = run_git_command(merge_commit_args, repo_path=repo_path)
    merge_commit_sha = merge_commit_output.strip().split('\n')[0] if merge_commit_output else None

    files_changed, lines_added, lines_deleted = calculate_diff_stats(repo_path, merge_commit_sha)

    pr.update({
        'merge_commit_sha': merge_commit_sha,
        'files_changed': files_changed,
        'lines_added': lines_added,
        'lines_deleted': lines_deleted
    })

    return pr
