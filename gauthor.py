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


def analyze_commit_chunk(chunk: str) -> Dict[str, str]:
    """Analyze a chunk of commits using Groq API to generate a high-level summary."""
    prompt = f"""Analyze the following git commit history and provide a high-level summary of the author's contributions.
    
    Focus on:
    1. Overall impact on the codebase
    2. Key areas of contribution
    3. Notable achievements or improvements
    4. Patterns in their work (e.g., focusing on specific features, bug fixes, etc.)
    
    Be concise but informative. Highlight the most significant contributions.
    
    Git commit history:
    {chunk}
    
    Respond in the following JSON format:
    {{
        "summary": "A concise paragraph summarizing the author's overall contributions",
        "key_areas": "List of 2-3 key areas where the author made significant contributions",
        "notable_achievements": "List of 2-3 notable achievements or improvements"
    }}
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that analyzes git commit histories to provide high-level summaries of contributions.",
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2000,
        )
        
        response = completion.choices[0].message.content
        print(prompt, response)
        # Extract JSON from the response
        json_str = response[response.find("{") : response.rfind("}") + 1]
        return json.loads(json_str)
    except Exception as e:
        print(f"Error analyzing commits with Groq: {e}")
        return {
            "summary": "Unable to analyze contributions due to an error.",
            "key_areas": "No key areas identified.",
            "notable_achievements": "No notable achievements identified."
        }


def merge_analyses(analyses: List[Dict[str, str]]) -> Dict[str, str]:
    """Merge multiple chunk analyses into a single summary."""
    if not analyses:
        return {
            "summary": "No contributions found.",
            "key_areas": "No key areas identified.",
            "notable_achievements": "No notable achievements identified."
        }
    
    # For simplicity, just use the first analysis
    # In a more sophisticated version, we could combine insights from multiple chunks
    return analyses[0]


def format_summary(summary: Dict[str, str], author_name: str) -> str:
    """Format the analysis summary into a readable report."""
    report = [
        f"\n📊 Contribution Analysis for {author_name}",
        "=" * (len(author_name) + 25),
        f"\n📝 Summary:",
        f"   {summary.get('summary', 'No summary available.')}",
        f"\n🎯 Key Areas of Contribution:",
        f"   {summary.get('key_areas', 'No key areas identified.')}",
        f"\n🏆 Notable Achievements:",
        f"   {summary.get('notable_achievements', 'No notable achievements identified.')}"
    ]
    
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
