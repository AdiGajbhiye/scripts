#!/usr/bin/env python3.11
import os
import subprocess
from groq import Groq
import argparse

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

# Ensure the Groq API key is set
if not os.environ.get("GROQ_API_KEY"):
    print(
        "Please set your Groq API key as an environment variable GROQ_API_KEY."
    )
    exit(1)


def generate_command(natural_language_description):
    """Use Groq API to generate a bash command based on natural language description."""
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI that generates bash commands based on natural language descriptions. "
                        "Output ONLY the bash command without any explanation or additional text. "
                        "The command should be safe and follow best practices. "
                        "Do not include any markdown formatting or code blocks."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Generate a bash command for: {natural_language_description}",
                },
            ],
            model="llama-3.3-70b-specdec",
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print("Error generating command:", e)
        return None


def execute_command(command):
    """Execute the generated command."""
    try:
        result = subprocess.run(
            command, shell=True, text=True, capture_output=True
        )
        if result.stdout:
            print("Output:")
            print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print("Error executing command:", e)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate and execute bash commands using Groq."
    )
    parser.add_argument(
        "description",
        help="Natural language description of the command to generate",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Only display the command without executing it",
    )
    args = parser.parse_args()

    command = generate_command(args.description)
    if not command:
        print("Failed to generate command.")
        return

    print(f"Generated command: {command}")
    
    if args.dry_run:
        print("Dry run mode - command not executed.")
        return

    confirm = input("Do you want to execute this command? (y/n): ")
    if confirm.lower() == "y":
        success = execute_command(command)
        if success:
            print("Command executed successfully.")
        else:
            print("Command execution failed.")
    else:
        print("Command execution cancelled.")


if __name__ == "__main__":
    main() 