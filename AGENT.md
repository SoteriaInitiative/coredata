# Branching Instructions

## Creating a new branch:

1.  Use `git checkout -b <branch_name>` to create and switch to the new branch.
2.  Replace `<branch_name>` with a descriptive name following these guidelines:
    *   Use a prefix indicating the type of change:
        *   `feature/`: For new features.
        *   `bugfix/`: For bug fixes.
        *   `hotfix/`: For urgent fixes.
    *   Example: `feature/add-new-functionality`
3.  Run the following commands to install dependencies and run tests:
    ```bash
    # Install dependencies
    pip install -r implementation/requirements.txt
