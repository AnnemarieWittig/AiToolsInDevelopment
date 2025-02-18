# AiToolsInDevelopment
This repository stores scripts for data retrieval in Github repositories. They should be easily adjusted for other git-based repository managers.

## Setup
To run the scripts, they require a few **environment variables**, an **internet connection** to use the Github API and a **locally cloned version of the repository**

The environment file (a `.env` file in root) requires the following information:
- GITHUB_ACCESS_TOKEN: Access token to Github
- REPO_PATH: Local path to the cloned repository to be analyzed 
- STORAGE_PATH: Path where the script results are stored
- OWNER: Owner of the repository
- REPO: Name of the repository
- MAIN_BRANCH: Primary branch of the analysed repository

If the used repository manager is a private instance of Github, some endpoints might need to be updated in the helper files.
These endpoints are in the [api_access](/RepositoryCrawlers/helper/api_access.py) file, lines 17-24.

## Analysis

The scripts for analysis can be run without changes if Github is used in accordance to the setup. For other repository-managers, the handling of responses might be adjusted due to different structures.

Scripts for analysing repositories and retrieve data on:
- [Commits](/RepositoryCrawlers/generate_commit_data.py)
  -  Produces: `STORAGE_PATH/commits.csv`
- [Files per commit, specifically their changes](/RepositoryCrawlers/generate_file_data.py) (MUST be run **after** commits, accesses the commits file)
  -  Produces: `STORAGE_PATH/files.json`
- [Releases](/RepositoryCrawlers/generate_release_data.py)
  -  Produces: `STORAGE_PATH/releases.csv`
- [Issues and issue data](/RepositoryCrawlers/generate_issue_data.py)
  -  Produces: `STORAGE_PATH/issues.csv`
  - The issue retrievals filters for bot-made changes. If a bot interacts with your repository, you can add their name to the list in l.19
- [Branches](/RepositoryCrawlers/generate_branch_data.py)
  -  Produces: `STORAGE_PATH/branches.csv`
- [Builds](/RepositoryCrawlers/generate_build_data.py)
  -  Produces: `STORAGE_PATH/workflow_runs.csv`
  -  Intermediate file (only as a safety net in case the processing of the workflows runs into errors): `STORAGE_PATH/workflow_runs.json`
- [Pull requests](/RepositoryCrawlers/generate_pull_request_data.py)
  -  Produces: `STORAGE_PATH/pull_requests.csv`
  -  Intermediate file (only as a safety net in case the processing of the workflows runs into errors): `STORAGE_PATH/pull_requests.json`

Primary scripts are in `/RepositoryCrawlers` and the functions interacting with the console and API are in `/RepositoryCrawlers/helpers`.
The produced files are the ones needed for analysis.

It is recommended to run the scripts in the same order as here, but aside from the files non of them have to. Depending on the repository size, they may take up some time to complete. 