# scripts

A list of AI-based utils which I found helpful in my daily life.

## gcommit - AI-powered Git commit message generator

### Setup (if not done already):
  1. Save the script as gcommit.py.
  2. Make it executable:
        ```chmod +x gcommit.py```
  3. Move it to /usr/local/bin for global access:
        ```sudo mv gcommit.py /usr/local/bin/gcommit```
Now you can run gcommit in any Git repository! 🚀

## gcmd - AI-powered command generator

A tool that generates and executes bash commands from natural language descriptions using Groq AI.

### Prerequisites:
  1. Install the Groq Python package:
        ```pip install groq```
  2. Set your Groq API key as an environment variable:
        ```export GROQ_API_KEY=your_api_key_here```

### Setup:
  1. Save the script as gcmd.py.
  2. Make it executable:
        ```chmod +x gcmd.py```
  3. Move it to /usr/local/bin for global access:
        ```sudo mv gcmd.py /usr/local/bin/gcmd```

### Usage:
  1. Basic usage (shows command and output):
        ```gcmd "find all PDF files in the current directory"```
  
  2. Quiet mode (for piping):
        ```gcmd -q "find all PDF files in the current directory" | grep "document"```
  
  3. Dry run mode (only shows the command without executing):
        ```gcmd -d "find all PDF files in the current directory"```

Now you can generate and execute commands using natural language! 🚀

## gauthor - AI-powered Git author contribution analyzer

A tool that analyzes and summarizes a specific author's contributions to a Git repository using Groq AI. It intelligently categorizes commits into features, bug fixes, documentation changes, refactoring, and infrastructure updates.

### Prerequisites:
  1. Install the Groq Python package:
        ```pip install groq```
  2. Set your Groq API key as an environment variable:
        ```export GROQ_API_KEY=your_api_key_here```

### Setup:
  1. Save the script as gauthor.py.
  2. Make it executable:
        ```chmod +x gauthor.py```
  3. Move it to /usr/local/bin for global access:
        ```sudo mv gauthor.py /usr/local/bin/gauthor```

### Usage:
  1. Basic usage (analyzes all commits):
        ```gauthor "Author Name"```
  
  2. Limit the number of commits to analyze:
        ```gauthor "Author Name" --max-commits 100```

The script will generate a detailed summary including:
- ✨ Features & Enhancements
- 🐛 Bug Fixes
- 📚 Documentation Changes
- ♻️  Refactoring & Improvements
- 🔧 Infrastructure & Dependencies

Now you can get an AI-powered analysis of any author's contributions to your repository! 🚀







