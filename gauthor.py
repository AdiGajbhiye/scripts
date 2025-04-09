#!/usr/bin/env python3.11

import subprocess
import argparse
import os
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Optional
import time
import json
from groq import Groq  # type: ignore

# Constants for chunking
MAX_COMMITS_PER_CHUNK = 50
MAX_TOKENS_PER_CHUNK = 8000  # Conservative limit for Groq's context window

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Ensure the Groq API key is set
if not os.environ.get("GROQ_API_KEY"):
    print("Please set your Groq API key as an environment variable GROQ_API_KEY.")
    exit(1)


def get_author_commits(
    author_name: str, max_commits: Optional[int] = None
) -> Optional[str]:
    """Get all commits by the specified author."""
    try:
        cmd = [
            "git",
            "log",
            "--author=" + author_name,
            "--pretty=format:%h|%ad|%s",
            "--date=short",
            "--name-status",
        ]
        if max_commits:
            cmd.extend(["-n", str(max_commits)])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git log: {e}")
        return None


def chunk_commits(commit_log: str) -> List[str]:
    """Split commits into manageable chunks for API processing."""
    if not commit_log:
        return []

    commits = commit_log.split("\n\n")
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_chunk_size = 0

    for commit in commits:
        # Rough estimate of tokens (1 token ≈ 4 chars)
        commit_size = len(commit) // 4

        if current_chunk_size + commit_size > MAX_TOKENS_PER_CHUNK:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [commit]
            current_chunk_size = commit_size
        else:
            current_chunk.append(commit)
            current_chunk_size += commit_size

        if len(current_chunk) >= MAX_COMMITS_PER_CHUNK:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_chunk_size = 0

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def analyze_commit_chunk(chunk: str) -> Dict[str, List[str]]:
    """Analyze a chunk of commits using Groq API."""
    prompt = f"""Analyze the following git commit history and categorize the contributions. 
    Focus on identifying:
    1. New features or enhancements
    2. Bug fixes
    3. Documentation changes
    4. Refactoring or code improvements
    5. Infrastructure or dependency changes
    
    For each category, provide a concise bullet-point summary.
    If a category has no entries, omit it.
    
    Git commit history:
    {chunk}
    
    Respond in the following JSON format:
    {{
        "features": ["feature 1", "feature 2", ...],
        "bug_fixes": ["fix 1", "fix 2", ...],
        "documentation": ["doc change 1", "doc change 2", ...],
        "refactoring": ["refactor 1", "refactor 2", ...],
        "infrastructure": ["infra change 1", "infra change 2", ...]
    }}
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that analyzes git commit histories.",
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2000,
        )
        
        response = completion.choices[0].message.content
        # Extract JSON from the response
        json_str = response[response.find("{") : response.rfind("}") + 1]
        return json.loads(json_str)
    except Exception as e:
        print(f"Error analyzing commits with Groq: {e}")
        return {
            "features": [],
            "bug_fixes": [],
            "documentation": [],
            "refactoring": [],
            "infrastructure": [],
        }


def merge_analyses(analyses: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
    """Merge multiple chunk analyses into a single summary."""
    merged: Dict[str, List[str]] = {
        "features": [],
        "bug_fixes": [],
        "documentation": [],
        "refactoring": [],
        "infrastructure": [],
    }

    for analysis in analyses:
        for category in merged:
            merged[category].extend(analysis.get(category, []))

    # Remove duplicates while preserving order
    for category in merged:
        merged[category] = list(dict.fromkeys(merged[category]))

    return merged


def format_summary(summary: Dict[str, List[str]], author_name: str) -> str:
    """Format the analysis summary into a readable report."""
    report = [
        f"\n📊 Contribution Analysis for {author_name}",
        "=" * (len(author_name) + 25),
    ]

    # Add each category if it has entries
    categories = {
        "features": "✨ Features & Enhancements",
        "bug_fixes": "🐛 Bug Fixes",
        "documentation": "📚 Documentation",
        "refactoring": "♻️  Refactoring & Improvements",
        "infrastructure": "🔧 Infrastructure & Dependencies",
    }

    for key, title in categories.items():
        items = summary.get(key, [])
        if items:
            report.append(f"\n{title}:")
            for item in items:
                report.append(f"   • {item}")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze git contributions by author using AI"
    )
    parser.add_argument("author", help="Author name to analyze")
    parser.add_argument(
        "--max-commits", type=int, help="Maximum number of commits to analyze"
    )
    args = parser.parse_args()

    # Get commits
    commit_log = get_author_commits(args.author, args.max_commits)
    if not commit_log:
        print(f"No commits found for author: {args.author}")
        return

    # Split into chunks and analyze
    chunks = chunk_commits(commit_log)
    print(f"\nAnalyzing {len(chunks)} chunks of commit history...")

    analyses = []
    for i, chunk in enumerate(chunks, 1):
        print(f"Processing chunk {i}/{len(chunks)}...")
        analysis = analyze_commit_chunk(chunk)
        analyses.append(analysis)
        if i < len(chunks):
            time.sleep(1)  # Rate limiting

    # Merge analyses and format report
    merged_summary = merge_analyses(analyses)
    report = format_summary(merged_summary, args.author)
    print(report)


if __name__ == "__main__":
    main()
