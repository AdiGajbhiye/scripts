#!/usr/bin/env python3.11
import os
import subprocess
from openai import OpenAI
import argparse
import tempfile

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
client = OpenAI(api_key=OPENAI_API_KEY)
# Ensure the OpenAI API key is set
if OPENAI_API_KEY == "your-api-key-here":
    print(
        "Please set your OpenAI API key as an environment variable or replace 'your-api-key-here' with your actual key."
    )
    exit(1)


def get_git_diff():
    """Get the current git diff as a string."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"], capture_output=True, text=True
        )
        return result.stdout.strip()
    except Exception as e:
        print("Error fetching git diff:", e)
        return None


def get_git_commit_content(commit_hash):
    """Get the git diff for a specific commit."""
    try:
        result = subprocess.run(
            ["git", "show", commit_hash, "--pretty=format:", "--unified=0"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error fetching git diff for {commit_hash}:", e)
        return None


def generate_commit_message(diff):
    """Use OpenAI API to generate a commit message based on the diff."""
    if not diff:
        print("No staged changes to commit.")
        return None

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI that writes concise and meaningful Git commit messages following the Conventional Commits standard. "
                        "Ensure the commit message includes a type tag like 'feat:', 'fix:', 'chore:', 'docs:', 'refactor:', 'test:', etc. "
                        "Just ouput the commit message. Should be less than 30 words and all lowercase. Should not include quotes."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Generate a properly formatted Git commit message following Conventional Commits based on the following diff:\n"
                        f"{diff}"
                    ),
                },
            ],
            max_tokens=350,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error generating commit message:", e)
        return None


def edit_message(initial_message):
    """Open a temporary file for the user to edit the commit message."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
        temp_file.write(initial_message)
        temp_file.flush()

        editor = os.getenv("EDITOR", "nano")  # Default to nano if EDITOR is not set
        subprocess.run([editor, temp_file.name])

        with open(temp_file.name, "r") as f:
            edited_message = f.read().strip()

        os.unlink(temp_file.name)  # Remove temp file
    return edited_message


def commit_changes(message):
    """Commit changes with the given message."""
    try:
        subprocess.run(["git", "commit", "-m", message], check=True)
        print("Committed with message:", message)
    except subprocess.CalledProcessError as e:
        print("Error committing changes:", e)


def get_last_commit_messages():
    """Retrieve diffs for the last 10 commits and generate commit messages."""
    try:
        result = subprocess.run(
            ["git", "log", "-n", "10", "--pretty=format:%H"],
            capture_output=True,
            text=True,
        )
        commit_hashes = result.stdout.split("\n")

        for commit_hash in commit_hashes:
            diff = get_git_commit_content(commit_hash)
            if diff:
                generated_message = generate_commit_message(diff)
                print(f"Commit {commit_hash[:7]}: {generated_message}")
    except Exception as e:
        print("Error fetching commit diffs:", e)


def main():
    parser = argparse.ArgumentParser(
        description="Automatically generate a Git commit message using OpenAI."
    )
    parser.add_argument(
        "-e",
        "--edit",
        action="store_true",
        help="Edit the generated commit message before committing.",
    )
    parser.add_argument(
        "-t",
        "--last-ten",
        action="store_true",
        help="Output generated commit messages for the last 10 commits.",
    )
    args = parser.parse_args()

    if args.last_ten:
        get_last_commit_messages()
        return

    diff = get_git_diff()
    if not diff:
        print("No staged changes. Use 'git add' before running gcommit.")
        return

    commit_message = generate_commit_message(diff)
    if not commit_message:
        print("Failed to generate commit message.")
        return

    if args.edit:
        commit_message = edit_message(commit_message)

    commit_changes(commit_message)


if __name__ == "__main__":
    main()
