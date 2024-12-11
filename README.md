# AiToolsInDevelopment
The analysis for my masters thesis


## File-Per-Commit Comparison Process

The file-per-commit comparison process involves several key steps to gather a comprehensive understanding of changes made in each commit.

1. **Identifying Commit SHA**
   - For each commit, I identify its unique **SHA** (hash). This SHA is essential for subsequent commands, serving as the unique reference for each commit.

2. **Getting File Changes for the Commit**
   - I extract file-level changes using the command:
     ```sh
     git diff-tree --no-commit-id --numstat -r <commit_sha>
     ```
   - This command provides a summary of changes for each file, including the number of lines **added** and **removed**, along with the file path. This step allows me to quantify the changes introduced in each file.

3. **Retrieving File SHAs**
   - I retrieve the SHA of each file within the commit using:
     ```sh
     git ls-tree -r <commit_sha>
     ```
   - This command lists all files in the commit, including their **SHAs**. These SHAs help me track specific versions of each file, which is crucial for understanding how files evolve over time.

4. **Calculating Word-Level Changes**
   - To capture word-level changes, including whitespace modifications, I use the following command:
     ```sh
     git diff --word-diff-regex=. <commit_sha>^ <commit_sha>
     ```
   - This command compares the specified commit against its parent, highlighting changes at the **word level**. The `--word-diff-regex=.` option ensures that **every character**, including spaces, is treated as a significant change. This provides a very granular view of the modifications.

5. **Storing Results**
   - For each file, I record the following details:
     - **File path**.
     - **Number of lines added, removed, and changed**.
     - **File SHA** to uniquely identify file versions.

This process allows me to have both a high-level overview and a detailed analysis of changes, providing insights into the evolution of every file modified in a commit. By tracking additions, removals, and modifications at both line and word levels, I ensure a thorough understanding of the nature of each change.

