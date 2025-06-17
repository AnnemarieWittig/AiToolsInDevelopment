import re
from .general_purpose import hash_string_sha256
from .git_console_access import run_git_command
import pandas as pd
import json

def format_username(name):
    """
    Format the username by taking the first letter of the first word and the rest of the last word,
    all in lowercase, with spaces removed.
    Example: "Mario Mauer" -> "mmauer"
    """
    parts = name.split()
    if len(parts) > 1:
        formatted_name = parts[0][0].lower() + parts[-1].lower()
    else:
        formatted_name = name.lower()
    return formatted_name

def get_local_git_users(repo_path=None):
    """
    Retrieve all unique usernames and emails from local Git history.
    """
    users = {}

    # Get all unique commit authors and their emails
    git_output = run_git_command(['log', '--format=%aN <%aE>', '--all'], repo_path=repo_path)
    git_output = sorted(set(git_output.splitlines()), key=str.casefold)  # Remove duplicates and sort

    if git_output:
        for line in git_output:  # Ensure no duplicate lines are processed
            if "<" in line and ">" in line:
                name, email = line.rsplit(" <", 1)
                email = email.rstrip(">")
                formatted_name = format_username(name)  
                hashed_email = hash_string_sha256(email)
                users[formatted_name] = hashed_email  
                users[name] = hashed_email  
                users[email] = hashed_email
                mail_prefix = email.split('@')[0]
                users[mail_prefix] = hashed_email

    return users

def replace_user_data(df, users_mapping):
    df_copy = df.copy()

    # Case-insensitive mapping: lowercase keys
    ci_mapping = {k.lower(): v for k, v in users_mapping.items()}

    # Sort usernames by length (longest first)
    sorted_usernames = sorted(users_mapping.keys(), key=len, reverse=True)

    # Compile regex with case-insensitive flag
    pattern = r'\b(' + '|'.join(re.escape(user) for user in sorted_usernames) + r')\b'
    regex = re.compile(pattern, flags=re.IGNORECASE)

    # Replacement function using lowercase lookup
    def replacer(match):
        matched_text = match.group(0)
        return ci_mapping.get(matched_text.lower(), matched_text)

    # Only apply to string-type columns
    str_cols = df_copy.select_dtypes(include='object')

    # Apply replacement with precompiled regex
    df_copy[str_cols.columns] = str_cols.map(
        lambda x: regex.sub(replacer, x) if isinstance(x, str) else x
    )

    return df_copy

def replace_user_data_manual(df, users_mapping):
    df_copy = df.copy()

    # Sort usernames by length (longest first) for better replacement
    sorted_usernames = sorted(users_mapping.keys(), key=len, reverse=True)

    # Only apply to string-type columns
    str_cols = df_copy.select_dtypes(include='object')

    # For each string column, replace each username one by one (case-insensitive)
    for col in str_cols.columns:
        col_data = df_copy[col]
        for username in sorted_usernames:
            pattern = re.compile(rf'\b{re.escape(username)}\b', flags=re.IGNORECASE)
            hashed_email = users_mapping[username]
            col_data = col_data.map(lambda x: pattern.sub(hashed_email, x) if isinstance(x, str) else x)
        df_copy[col] = col_data

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

def replace_all_user_occurences(df, repo_path):
    users_mapping = get_local_git_users(repo_path)

    # with open('mapping.json', 'w') as f:
    #     json.dump(users_mapping, f, indent=4)

    df = replace_user_data(df, users_mapping)
    
    return df

def anonymize_csv(input_path, output_path, repo_path):
    """
    Anonymize a CSV file by replacing user data with hashed values.

    :param input_path: Path to the input CSV file.
    :param output_path: Path to save the anonymized CSV file.
    :param repo_path: Path to the Git repository for extracting user data.
    """
    # Read the CSV file into a DataFrame
    df = pd.read_csv(input_path)

    # Apply the anonymization process
    anonymized_df = replace_all_user_occurences(df, repo_path)

    # Save the anonymized DataFrame to the output path
    anonymized_df.to_csv(output_path, index=False)