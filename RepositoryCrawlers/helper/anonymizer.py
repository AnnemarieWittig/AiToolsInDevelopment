import re
from .general_purpose import hash_string_sha256
from .git_console_access import run_git_command
import logging
import json


def get_local_git_users(repo_path=None):
    """
    Retrieve all unique usernames and emails from local Git history.
    """
    users = {}

    # Get all unique commit authors and their emails
    git_output = run_git_command(['log', '--format=%aN <%aE>', '--all'], repo_path=repo_path)

    if git_output:
        for line in git_output.split("\n"):
            if "<" in line and ">" in line:
                name, email = line.rsplit(" <", 1)
                email = email.rstrip(">")
                hashed_email = hash_string_sha256(email)
                users[name] = hashed_email  # Store hashed email by username
                users[email] = hashed_email

                # Add transformed username
                if " " in name:
                    parts = name.split()
                    transformed_name = parts[0][0].lower() + ''.join(parts[1:]).lower()
                    users[transformed_name] = hashed_email

    return users

def replace_user_data(df, users_mapping):
    """
    Replace occurrences of usernames and emails in the dataframe with the corresponding hashed email.

    :param df: Pandas DataFrame containing data to replace.
    :param users_mapping: Dictionary {username: hashed_email}.
    :return: Modified DataFrame.
    """
    df_copy = df.copy()

    def replace_in_cell(cell, users_mapping):
        if isinstance(cell, str):
            for username, hashed_email in users_mapping.items():
                pattern = re.escape(username)
                cell = re.sub(pattern, hashed_email, cell)
        elif isinstance(cell, list):
            cell = [replace_in_cell(item, users_mapping) for item in cell]
        return cell

    for col in df_copy.columns:
        df_copy[col] = df_copy[col].apply(lambda x: replace_in_cell(x, users_mapping))

    return df_copy

def replace_user_data_in_dict(data_dict, users_mapping):
    """
    Replace occurrences of usernames and emails in the dictionary with the corresponding hashed email.

    :param data_dict: Dictionary containing data to replace.
    :param users_mapping: Dictionary {username: hashed_email}.
    :return: Modified dictionary.
    """
    def replace_in_value(value, users_mapping):
        if isinstance(value, str):
            for username, hashed_email in users_mapping.items():
                pattern = rf"\b{re.escape(username)}\b"
                value = re.sub(pattern, hashed_email, value)
        elif isinstance(value, dict):
            value = replace_user_data_in_dict(value, users_mapping)
        elif isinstance(value, list):
            value = [replace_in_value(item, users_mapping) for item in value]
        return value

    return {key: replace_in_value(value, users_mapping) for key, value in data_dict.items()}

def overwrite_automated_mapping(automated_users_mapping):
    with open('./mapping.json', 'r') as f:
        manual_mapping = json.load(f)

    # Log and prepend "EX_" to keys not in manual_mapping
    for key in automated_users_mapping:
        automated_users_mapping[key] = f"EX_{automated_users_mapping[key]}"

    return manual_mapping, automated_users_mapping

def replace_all_user_occurences(df, repo_path, use_custom_mapping=False, filter_columns=[]):
    users_mapping = get_local_git_users(repo_path)

    if use_custom_mapping:
        manual_users_mapping, users_mapping = overwrite_automated_mapping(users_mapping)

        if filter_columns:
            # Filter rows where at least one of the cell values in filter_columns is a key in manual_users_mapping
            df = df[df[filter_columns].apply(
                lambda row: any(cell in manual_users_mapping for cell in row if isinstance(cell, str)), axis=1
            )]

        df = replace_user_data(df, manual_users_mapping)

    df = replace_user_data(df, users_mapping)
    
    return df