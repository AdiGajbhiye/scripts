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
    author_email: str, max_commits: Optional[int] = None
) -> Optional[str]:
    """Get all commits by the specified author with detailed information."""
    try:
        cmd = [
            "git",
            "log",
            "--author=" + author_email,
            "--pretty=format:%h|%ad|%s",
            "--date=short",
            "--name-status",
            "--stat",
            "--patch",
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


def analyze_commit_chunk(chunk: str) -> Dict[str, Any]:
    """Analyze a chunk of commits using Groq API to generate a detailed summary."""
    prompt = f"""Analyze the following git commit history and provide a detailed summary of the author's contributions.
    
    Focus on:
    1. Overall impact on the codebase
    2. Specific features implemented (what they do, how they work)
    3. Libraries, frameworks, and technologies used
    4. Code quality indicators (patterns, architecture decisions)
    5. Notable achievements or improvements
    6. Technical skills demonstrated (programming languages, tools, methodologies)
    
    Be specific and detailed. Highlight concrete examples from the code changes.
    
    Git commit history:
    {chunk}
    
    Respond in the following JSON format:
    {{
        "summary": "A concise paragraph summarizing the author's overall contributions",
        "features": ["Detailed description of feature 1", "Detailed description of feature 2", ...],
        "technologies": ["Technology 1 with context", "Technology 2 with context", ...],
        "code_quality": "Analysis of code quality, patterns, and architecture decisions",
        "technical_skills": ["Skill 1 with evidence", "Skill 2 with evidence", ...],
        "notable_achievements": ["Achievement 1 with impact", "Achievement 2 with impact", ...]
    }}
    """

    try:
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that analyzes git commit histories to provide detailed summaries of contributions, focusing on technical skills and implementation details.",
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
            "summary": "Unable to analyze contributions due to an error.",
            "features": [],
            "technologies": [],
            "code_quality": "No code quality analysis available.",
            "technical_skills": [],
            "notable_achievements": [],
        }


def merge_analyses(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple chunk analyses into a single comprehensive summary."""
    if not analyses:
        return {
            "summary": "No contributions found.",
            "features": [],
            "technologies": [],
            "code_quality": "No code quality analysis available.",
            "technical_skills": [],
            "notable_achievements": [],
        }

    # Initialize merged result
    merged: Dict[str, Any] = {
        "summary": "",
        "features": [],
        "technologies": [],
        "code_quality": "",
        "technical_skills": [],
        "notable_achievements": [],
    }

    # Combine summaries
    summaries = [a.get("summary", "") for a in analyses if a.get("summary")]
    if summaries:
        merged["summary"] = " ".join(summaries)

    # Combine lists (features, technologies, skills, achievements)
    for key in ["features", "technologies", "technical_skills", "notable_achievements"]:
        for analysis in analyses:
            if key in analysis and isinstance(analysis[key], list):
                merged[key].extend(analysis[key])

    # Combine code quality analysis
    code_quality = [
        a.get("code_quality", "") for a in analyses if a.get("code_quality")
    ]
    if code_quality:
        merged["code_quality"] = " ".join(code_quality)

    # Remove duplicates while preserving order
    for key in ["features", "technologies", "technical_skills", "notable_achievements"]:
        if isinstance(merged[key], list):
            merged[key] = list(dict.fromkeys(merged[key]))

    return merged


def format_summary(summary: Dict[str, Any], author_email: str) -> str:
    """Format the analysis summary into a readable report."""
    report = [
        f"\n📊 Detailed Contribution Analysis for {author_email}",
        "=" * (len(author_email) + 35),
        f"\n📝 Summary:",
        f"   {summary.get('summary', 'No summary available.')}",
    ]

    # Add features if available
    features = summary.get("features", [])
    if features:
        report.append(f"\n✨ Implemented Features:")
        for feature in features:
            report.append(f"   • {feature}")

    # Add technologies if available
    technologies = summary.get("technologies", [])
    if technologies:
        report.append(f"\n🔧 Technologies & Libraries:")
        for tech in technologies:
            report.append(f"   • {tech}")

    # Add code quality analysis if available
    code_quality = summary.get("code_quality", "")
    if code_quality:
        report.append(f"\n📈 Code Quality & Architecture:")
        report.append(f"   {code_quality}")

    # Add technical skills if available
    skills = summary.get("technical_skills", [])
    if skills:
        report.append(f"\n💻 Technical Skills Demonstrated:")
        for skill in skills:
            report.append(f"   • {skill}")

    # Add notable achievements if available
    achievements = summary.get("notable_achievements", [])
    if achievements:
        report.append(f"\n🏆 Notable Achievements:")
        for achievement in achievements:
            report.append(f"   • {achievement}")

    return "\n".join(report)


def generate_final_analysis(summary: Dict[str, Any], author_email: str) -> str:
    """Generate a final consolidated analysis using the LLM."""
    # Format the initial summary
    initial_summary = format_summary(summary, author_email)

    prompt = f"""Based on the following detailed contribution analysis, generate a final consolidated analysis.
    
    Focus on:
    1. A comprehensive summary of the author's overall impact
    2. A consolidated list of key features implemented (without duplicates)
    3. A consolidated list of technologies and libraries used (without duplicates)
    4. A clear assessment of code quality and architecture decisions
    5. A consolidated list of technical skills demonstrated (without duplicates)
    6. A consolidated list of notable achievements (without duplicates)
    
    Be concise, avoid repetition, and highlight the most significant contributions.
    
    Initial analysis:
    {initial_summary}
    
    Respond with a well-structured final analysis that eliminates any redundancy while preserving all important information.
    """

    try:
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that consolidates and refines technical contribution analyses to create clear, non-redundant summaries.",
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2000,
        )

        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error generating final analysis with Groq: {e}")
        return initial_summary


def main():
    parser = argparse.ArgumentParser(
        description="Analyze git contributions by author using AI"
    )
    parser.add_argument("email", help="Author email to analyze")
    parser.add_argument(
        "--max-commits", type=int, help="Maximum number of commits to analyze"
    )
    args = parser.parse_args()

    # Get commits
    commit_log = get_author_commits(args.email, args.max_commits)
    if not commit_log:
        print(f"No commits found for author email: {args.email}")
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

    # Merge analyses and generate final report
    merged_summary = merge_analyses(analyses)
    final_analysis = generate_final_analysis(merged_summary, args.email)
    print(final_analysis)


if __name__ == "__main__":
    main()
