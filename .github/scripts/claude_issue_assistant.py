#!/usr/bin/env python3
"""
Claude AI Issue Assistant

This script uses Anthropic's Claude API to analyze and provide assistance
for GitHub issues.
"""

import argparse
import html
import json
import os
import re
import sys
from typing import Any, Dict, List

try:
    import anthropic
    from github import Github, GithubException, UnknownObjectException
    import yaml
except ImportError as e:
    print(f"Error: Missing required package: {e.name if hasattr(e, 'name') else str(e)}")
    print("Installing required packages...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic", "PyGithub", "PyYAML"])
        import anthropic
        from github import Github, GithubException, UnknownObjectException
        import yaml
    except Exception as install_error:
        print(f"Failed to install packages: {install_error}")
        sys.exit(1)


class ClaudeIssueAssistant:
    """Automated issue assistant using Claude AI."""

    # Constants for limits
    MAX_SIMILAR_ISSUES = 5  # Limit similar issues to avoid overwhelming context
    MAX_RECENT_COMMENTS = 5  # Balance context vs. prompt size
    MAX_TITLE_LENGTH_FOR_SEARCH = 50  # GitHub search API limitations
    MAX_ISSUE_BODY_LENGTH = 1000  # Prevent excessive prompt size from issue content
    MAX_CODE_FILES = 3  # Limit file fetching to avoid rate limits
    MAX_CODE_SNIPPET_LENGTH = 1000  # Keep code context focused and relevant

    def __init__(self, api_key: str, github_token: str) -> None:
        """Initialize the assistant with API credentials.
        
        Args:
            api_key: Anthropic API key (must start with 'sk-ant-')
            github_token: GitHub personal access token
            
        Raises:
            ValueError: If API key or GitHub token is invalid
        """
        if not api_key or not api_key.startswith('sk-ant-'):
            raise ValueError("Invalid or missing Claude API key")
        if not github_token:
            raise ValueError("Invalid or missing GitHub token")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.github = Github(github_token)
        self.model = self._load_model_from_config()

    def _load_model_from_config(self) -> str:
        """Load model name from configuration file."""
        config_path = ".github/CLAUDE_CONFIG.yml"
        default_model = "claude-sonnet-4-5-20250929"
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    model = config.get('model', {}).get('name', default_model)
                    if not model or not isinstance(model, str):
                        print(f"Warning: Invalid model name in config, using default")
                        return default_model
                    return model
        except yaml.YAMLError as e:
            print(f"Warning: YAML parsing error in config: {e}")
        except (IOError, OSError) as e:
            print(f"Warning: Could not read config file: {e}")
        except Exception as e:
            print(f"Warning: Unexpected error loading config: {e}")
        
        return default_model

    def get_issue_context(self, repo_name: str, issue_number: int) -> Dict[str, Any]:
        """Get context about the issue.
        
        Args:
            repo_name: Repository in owner/name format
            issue_number: Issue number to analyze
            
        Returns:
            Dictionary containing issue metadata
            
        Raises:
            GithubException: If GitHub API call fails
        """
        try:
            repo = self.github.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
        except GithubException as e:
            print(f"GitHub API error: {e.status} - {e.data}")
            raise
        except Exception as e:
            print(f"Unexpected error fetching issue: {str(e)}")
            raise

        # Get comments
        comments = []
        for comment in issue.get_comments():
            comments.append({
                "author": comment.user.login,
                "body": comment.body,
                "created_at": comment.created_at.isoformat()
            })

        # Get labels
        labels = [label.name for label in issue.labels]

        # Sanitize issue body to prevent injection attacks
        raw_body = issue.body or ""
        sanitized_body = html.escape(raw_body[:self.MAX_ISSUE_BODY_LENGTH])
        
        return {
            "number": issue.number,
            "title": issue.title,
            "body": sanitized_body,
            "author": issue.user.login,
            "state": issue.state,
            "labels": labels,
            "comments": comments,
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
        }

    def search_similar_issues(self, repo_name: str, title: str) -> List[Dict[str, Any]]:
        """Search for similar issues in the repository.
        
        Args:
            repo_name: Repository in owner/name format
            title: Issue title to search for similarities
            
        Returns:
            List of similar issues with metadata
        """
        try:
            # Sanitize title for search
            safe_title = title[:self.MAX_TITLE_LENGTH_FOR_SEARCH]
            
            # Search for similar issues
            query = f"repo:{repo_name} is:issue {safe_title}"
            results = self.github.search_issues(query)

            similar_issues = []
            for issue in list(results)[:self.MAX_SIMILAR_ISSUES]:
                similar_issues.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "url": issue.html_url
                })

            return similar_issues
        except GithubException as e:
            print(f"Warning: Could not search similar issues: {e.status}")
            return []
        except Exception as e:
            print(f"Warning: Error searching similar issues: {str(e)}")
            return []

    def get_relevant_code(self, repo_name: str, issue_body: str) -> str:
        """Extract file paths from issue and get relevant code snippets.
        
        Args:
            repo_name: Repository in owner/name format
            issue_body: Issue body text to extract file references from
            
        Returns:
            String containing code snippets from referenced files
        """
        try:
            repo = self.github.get_repo(repo_name)
        except GithubException as e:
            print(f"Warning: Could not access repository: {e.status}")
            return "No code files referenced"

        # Extract file paths from full body first (before truncation)
        # to avoid cutting off file references at arbitrary positions
        # Look for patterns like: src/file.py, file.py:123, etc.
        # Using a more restrictive pattern to prevent injection
        file_pattern = r'(?:src/)?[\w/]+\.py(?::\d+)?'
        try:
            # Extract from full body to avoid missing file paths due to truncation
            files = re.findall(file_pattern, issue_body)
        except re.error as e:
            print(f"Warning: Regex error: {e}")
            return "No code files referenced"

        code_snippets = []
        for file_ref in files[:self.MAX_CODE_FILES]:
            file_path = file_ref.split(':')[0]
            
            # Validate file path to prevent path traversal and other attacks
            # Check for dangerous patterns in the extracted path
            if '..' in file_path or file_path.startswith('/'):
                continue
            
            # Additional validation: ensure path doesn't exceed reasonable length
            if len(file_path) > 200:
                continue
                
            try:
                content = repo.get_contents(file_path)
                if hasattr(content, 'decoded_content'):
                    code = content.decoded_content.decode('utf-8')
                    code_snippet = code[:self.MAX_CODE_SNIPPET_LENGTH]
                    code_snippets.append(f"### {file_path}\n\n```python\n{code_snippet}\n```")
            except UnknownObjectException:
                continue
            except Exception as e:
                print(f"Warning: Could not fetch {file_path}: {str(e)}")
                continue

        return "\n\n".join(code_snippets) if code_snippets else "No code files referenced"

    def create_analysis_prompt(
        self, context: Dict[str, Any], similar: List[Dict[str, Any]], code: str
    ) -> str:
        """Create the prompt for Claude to analyze the issue."""
        comments_text = "\n".join([
            f"- {c['author']}: {c['body'][:200]}"
            for c in context['comments'][:self.MAX_RECENT_COMMENTS]
        ]) if context['comments'] else "No comments yet"

        similar_text = "\n".join([
            f"- #{s['number']}: {s['title']} ({s['state']})"
            for s in similar[:self.MAX_SIMILAR_ISSUES]
        ]) if similar else "No similar issues found"

        return f"""You are an expert technical assistant for a Python project called "arena-improver",
an AI-powered Magic: The Gathering Arena deck analysis platform.

Project Technology Stack:
- Python 3.9+ with FastAPI
- SQLAlchemy + SQLite for database
- OpenAI API for AI features
- Sentence Transformers for embeddings
- Pytest for testing
- AGPL-3.0 license

Issue Information:
- Number: #{context['number']}
- Title: {context['title']}
- Author: {context['author']}
- Labels: {', '.join(context['labels']) if context['labels'] else 'None'}
- State: {context['state']}

Issue Description:
{context['body']}

Recent Comments:
{comments_text}

Similar Issues:
{similar_text}

Relevant Code:
{code}

Please analyze this issue and provide:

1. **Root Cause Analysis**: What is likely causing this issue?
2. **Recommended Solution**: Step-by-step fix or implementation
3. **Code Examples**: Provide specific code changes if applicable
4. **Testing Strategy**: How to verify the fix works
5. **Prevention**: How to prevent similar issues in the future
6. **Related Issues**: Connections to other parts of the codebase

Provide your response in this markdown format:

## Analysis

### Issue Type
[bug | feature request | question | enhancement | documentation]

### Root Cause
[Detailed explanation of what's causing the issue]

### Recommended Solution

#### Step 1: [Description]
```python
# Code example if applicable
```

#### Step 2: [Description]
```python
# Code example if applicable
```

[Continue as needed]

### Testing Strategy
- [ ] [Test case 1]
- [ ] [Test case 2]
- [ ] [Test case 3]

### Prevention
[How to prevent this issue in the future]

### Additional Notes
[Any other relevant information, warnings, or considerations]

### Related Files
[List of files that may need changes]

---

**Confidence Level**: [High | Medium | Low]
**Estimated Effort**: [Simple | Moderate | Complex]
"""

    def analyze_issue(
        self, repo_name: str, issue_number: int
    ) -> tuple[str, Dict[str, Any]]:
        """Analyze a GitHub issue.
        
        Args:
            repo_name: Repository in owner/name format
            issue_number: Issue number to analyze
            
        Returns:
            Tuple of (analysis text, metrics dictionary)
            
        Raises:
            GithubException: If GitHub API call fails
            APIError: If Claude API call fails
        """
        print(f"Fetching issue #{issue_number} from {repo_name}...")
        context = self.get_issue_context(repo_name, issue_number)

        print("Searching for similar issues...")
        similar = self.search_similar_issues(repo_name, context['title'])

        print("Gathering relevant code...")
        code = self.get_relevant_code(repo_name, context['body'])

        print("Requesting Claude analysis...")
        prompt = self.create_analysis_prompt(context, similar, code)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            analysis_text = message.content[0].text

            # Compile metrics
            metrics = {
                "issue_number": issue_number,
                "model_used": self.model,
                "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
                "similar_issues_found": len(similar),
                "comments_analyzed": len(context['comments']),
            }

            print("✓ Analysis completed successfully")
            return analysis_text, metrics

        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            print(f"✗ {error_msg}")
            return f"## Error\n\n{error_msg}", {}

    def save_analysis(
        self, analysis_text: str, metrics: Dict[str, Any],
        output_file: str = "claude_issue_response.md"
    ) -> None:
        """Save the analysis to a file."""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(analysis_text)

        # Save detailed metrics
        with open("claude_issue_details.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(f"✓ Analysis saved to {output_file}")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Claude AI Issue Assistant")
    parser.add_argument("--issue-number", type=int, required=True, help="Issue number")
    parser.add_argument("--repo", required=True, help="Repository (owner/name)")
    parser.add_argument(
        "--output", default="claude_issue_response.md", help="Output file for analysis"
    )

    args = parser.parse_args()

    # Get API keys from environment with validation
    api_key = os.getenv("ANTHROPIC_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")

    if not api_key or not api_key.startswith('sk-ant-'):
        print("Error: Invalid ANTHROPIC_API_KEY format")
        sys.exit(1)

    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        sys.exit(1)

    # Perform analysis
    assistant = ClaudeIssueAssistant(api_key, github_token)
    analysis_text, metrics = assistant.analyze_issue(args.repo, args.issue_number)

    # Save results
    assistant.save_analysis(analysis_text, metrics, args.output)

    print("\n" + "="*80)
    print("Analysis Summary:")
    print("="*80)
    print(analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text)
    print("="*80)


if __name__ == "__main__":
    main()
