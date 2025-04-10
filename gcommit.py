#!/usr/bin/env python3.11
import os
import subprocess
from groq import Groq  # type: ignore
import argparse
import tempfile
import re

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

# Ensure the Groq API key is set
if not os.environ.get("GROQ_API_KEY"):
    print("Please set your Groq API key as an environment variable GROQ_API_KEY.")
    exit(1)


def optimize_diff(diff):
    """Optimize the diff by removing file moves and unnecessary content."""
    if not diff:
        return ""

    # Split diff into individual file diffs
    file_diffs = re.split(r"^diff --git", diff, flags=re.MULTILINE)
    optimized_diffs = []

    for file_diff in file_diffs:
        if not file_diff.strip():
            continue

        # Handle file moves/renames
        rename_from = re.search(r"^rename from (.+)$", file_diff, re.MULTILINE)
        rename_to = re.search(r"^rename to (.+)$", file_diff, re.MULTILINE)
        if rename_from and rename_to:
            optimized_diffs.append(
                f"# file renamed from {rename_from.group(1)} to {rename_to.group(1)}\n"
            )
            continue

        # Handle binary files
        binary_match = re.search(
            r"^Binary files (.+) and (.+) differ$", file_diff, re.MULTILINE
        )
        if binary_match:
            optimized_diffs.append(
                f"# binary file changed: {binary_match.group(1)} -> {binary_match.group(2)}\n"
            )
            continue

        optimized_diffs.append(file_diff)

    return "".join(optimized_diffs)


def chunk_diff(diff, max_chunk_size=4000):
    """Split large diffs into smaller chunks."""
    if not diff:
        return []

    # Split by file diffs
    file_diffs = re.split(r"^diff --git", diff, flags=re.MULTILINE)
    chunks = []
    current_chunk = []
    current_size = 0

    for file_diff in file_diffs:
        if not file_diff.strip():
            continue

        # If adding this file would exceed chunk size, start a new chunk
        if current_size + len(file_diff) > max_chunk_size and current_chunk:
            chunks.append("".join(current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(file_diff)
        current_size += len(file_diff)

    # Add the last chunk if it exists
    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks


def summarize_diff_chunk(chunk):
    """Generate a summary of a diff chunk using Groq."""
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI that summarizes Git diffs concisely. "
                        "Focus on the key changes and their impact. "
                        "Keep the summary under 100 words."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this Git diff chunk:\n{chunk}",
                },
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print("Error summarizing diff chunk:", e)
        return None


def get_git_diff():
    """Get the current git diff as a string."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"], capture_output=True, text=True
        )
        diff = result.stdout.strip()

        # Optimize the diff
        optimized_diff = optimize_diff(diff)

        # If diff is too large, chunk it
        if len(optimized_diff) > 4000:
            chunks = chunk_diff(optimized_diff)
            summaries = []
            for chunk in chunks:
                summary = summarize_diff_chunk(chunk)
                if summary:
                    summaries.append(summary)
            return "\n\n".join(summaries)

        return optimized_diff
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
    """Use Groq API to generate a commit message based on the diff."""
    if not diff:
        print("No staged changes to commit.")
        return None

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI that writes concise and meaningful Git commit messages following the Conventional Commits standard. "
                        "The commit message MUST follow this exact format: type: description\n"
                        "Where type is one of: feat, fix, chore, docs, refactor, test, etc.\n"
                        "The description should be a short summary of changes.\n"
                        "DO NOT use parentheses in the output.\n"
                        "DO NOT include quotes.\n"
                        "Keep it under 30 words and all lowercase.\n"
                        "Example good format: 'fix: optimize git diff for large files'\n"
                        "Example bad format: 'fix(get_git_diff): optimize for large files'"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Generate a properly formatted Git commit message following Conventional Commits based on the following changes:\n"
                        f"{diff}"
                    ),
                },
            ],
            model="llama-3.1-8b-instant",
        )
        message = chat_completion.choices[0].message.content.strip()
        
        # Clean up any remaining parentheses if they somehow got through
        message = re.sub(r'\([^)]*\):', ':', message)
        message = re.sub(r'\s+', ' ', message).strip()
        
        return message
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
        description="Automatically generate a Git commit message using Groq."
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
