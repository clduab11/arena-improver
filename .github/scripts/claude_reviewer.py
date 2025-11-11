#!/usr/bin/env python3
"""
Claude AI Code Reviewer

This script uses Anthropic's Claude API to perform automated code reviews
on GitHub pull requests.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict

try:
    import anthropic
    from github import Github, GithubException
    import yaml
except ImportError as e:
    print(f"Error: Missing required package: {e.name if hasattr(e, 'name') else str(e)}")
    print("Installing required packages...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic", "PyGithub", "PyYAML"])
        import anthropic
        from github import Github, GithubException
        import yaml
    except Exception as install_error:
        print(f"Failed to install packages: {install_error}")
        sys.exit(1)


class ClaudeReviewer:
    """Automated code reviewer using Claude AI."""

    # Resource limits
    MAX_DIFF_SIZE = 50000  # ~50KB - balanced for API limits and context window
    MAX_FILES = 50  # Prevent overwhelming the AI model with too many files
    MAX_FILE_DIFF_SIZE = 5000  # Per-file limit to keep individual diffs manageable

    def __init__(self, api_key: str, github_token: str) -> None:
        """Initialize the reviewer with API credentials.
        
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

    def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """Get the diff for a pull request with resource limits."""
        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
        except GithubException as e:
            print(f"GitHub API error: {e.status} - {e.data}")
            raise
        except Exception as e:
            print(f"Unexpected error fetching PR: {str(e)}")
            raise

        diff_text = []
        files = list(pr.get_files())[:self.MAX_FILES]
        total_diff_size = 0

        for file in files:
            if total_diff_size > self.MAX_DIFF_SIZE:
                diff_text.append("\n[Truncated: diff too large]")
                break

            diff_text.append(f"\n{'='*80}")
            diff_text.append(f"File: {file.filename}")
            diff_text.append(f"Status: {file.status}")
            diff_text.append(f"Changes: +{file.additions} -{file.deletions}")
            diff_text.append(f"{'='*80}\n")

            if file.patch:
                patch_content = file.patch[:self.MAX_FILE_DIFF_SIZE]
                total_diff_size += len(patch_content)
                diff_text.append(patch_content)
                if len(file.patch) > self.MAX_FILE_DIFF_SIZE:
                    diff_text.append("\n[File diff truncated]")
            else:
                diff_text.append("(Binary file or no diff available)")

        return "\n".join(diff_text)

    def get_pr_context(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        """Get context about the pull request.
        
        Args:
            repo_name: Repository in owner/name format
            pr_number: Pull request number to analyze
            
        Returns:
            Dictionary containing PR metadata
            
        Raises:
            GithubException: If GitHub API call fails
        """
        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
        except GithubException as e:
            print(f"GitHub API error: {e.status} - {e.data}")
            raise
        except Exception as e:
            print(f"Unexpected error fetching PR context: {str(e)}")
            raise

        return {
            "title": pr.title,
            "body": pr.body or "",
            "author": pr.user.login,
            "base_branch": pr.base.ref,
            "head_branch": pr.head.ref,
            "files_changed": pr.changed_files,
            "additions": pr.additions,
            "deletions": pr.deletions,
        }

    def create_review_prompt(self, context: Dict[str, Any], diff: str) -> str:
        """Create the prompt for Claude to review the code."""
        return f"""You are an expert code reviewer for a Python project called "arena-improver",
an AI-powered Magic: The Gathering Arena deck analysis platform.

Pull Request Information:
- Title: {context['title']}
- Description: {context['body']}
- Author: {context['author']}
- Base Branch: {context['base_branch']}
- Files Changed: {context['files_changed']}
- Lines: +{context['additions']} -{context['deletions']}

Code Quality Standards for this project:
- Python 3.9+ with type hints
- PEP 8 compliant code style
- AGPL-3.0 license
- Ruff for linting and formatting
- MyPy for type checking
- Pytest for testing (>80% coverage recommended)
- Security-first approach (no SQL injection, XSS, etc.)
- FastAPI for REST APIs
- SQLAlchemy for database operations

Please review the following code changes and provide:

1. **Security Issues** (CRITICAL): Any potential vulnerabilities
2. **Bugs** (HIGH): Logic errors, type issues, edge cases
3. **Code Quality** (MEDIUM): Style violations, complexity, maintainability
4. **Performance** (MEDIUM): Inefficiencies, optimization opportunities
5. **Testing** (MEDIUM): Missing tests, test quality
6. **Documentation** (LOW): Missing docstrings, unclear comments
7. **Suggestions** (LOW): Improvements, best practices

For each issue found:
- Specify the file and approximate line number
- Explain the issue clearly
- Suggest a specific fix with code example if applicable
- Rate severity: CRITICAL, HIGH, MEDIUM, LOW

If no issues are found, provide a brief positive review.

Here are the code changes:

{diff}

Please provide your review in the following markdown format:

## Summary
[Brief overview of the changes and overall assessment]

## Issues Found

### 🔴 Critical Issues
[List critical security/bug issues, or state "None found"]

### 🟡 High Priority
[List important bugs and quality issues, or state "None found"]

### 🟢 Medium Priority
[List code quality and performance suggestions, or state "None found"]

### ⚪ Low Priority
[List minor improvements and documentation suggestions, or state "None found"]

## Positive Aspects
[Highlight good practices and well-written code]

## Recommendations
[Overall recommendations for improving the PR]

## Metrics
- Files reviewed: {context['files_changed']}
- Lines analyzed: {context['additions'] + context['deletions']}
- Critical issues: [count]
- Total issues: [count]
"""

    def review_pr(
        self, repo_name: str, pr_number: int
    ) -> tuple[str, Dict[str, Any]]:
        """Perform a code review on a pull request.
        
        Args:
            repo_name: Repository in owner/name format
            pr_number: Pull request number to review
            
        Returns:
            Tuple of (review text, metrics dictionary)
            
        Raises:
            GithubException: If GitHub API call fails
            APIError: If Claude API call fails
        """
        print(f"Fetching PR #{pr_number} from {repo_name}...")
        context = self.get_pr_context(repo_name, pr_number)

        print(f"Analyzing {context['files_changed']} files...")
        diff = self.get_pr_diff(repo_name, pr_number)

        if not diff.strip():
            return "No code changes to review.", {}

        print("Requesting Claude review...")
        prompt = self.create_review_prompt(context, diff)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            review_text = message.content[0].text

            # Extract metrics from review
            metrics = {
                "files_reviewed": context["files_changed"],
                "lines_analyzed": context["additions"] + context["deletions"],
                "model_used": self.model,
                "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
            }

            print("✓ Review completed successfully")
            return review_text, metrics

        except Exception as e:
            error_msg = f"Error during review: {str(e)}"
            print(f"✗ {error_msg}")
            return f"## Error\n\n{error_msg}", {}

    def save_review(
        self, review_text: str, metrics: Dict[str, Any], output_file: str = "claude_review.md"
    ) -> None:
        """Save the review to a file."""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(review_text)

        # Save detailed metrics
        with open("claude_review_details.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(f"✓ Review saved to {output_file}")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Claude AI Code Reviewer")
    parser.add_argument("--pr-number", type=int, required=True, help="Pull request number")
    parser.add_argument("--repo", required=True, help="Repository (owner/name)")
    parser.add_argument("--base-sha", help="Base commit SHA (optional)")
    parser.add_argument("--head-sha", help="Head commit SHA (optional)")
    parser.add_argument(
        "--output", default="claude_review.md", help="Output file for review"
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

    # Perform review
    reviewer = ClaudeReviewer(api_key, github_token)
    review_text, metrics = reviewer.review_pr(args.repo, args.pr_number)

    # Save results
    reviewer.save_review(review_text, metrics, args.output)

    print("\n" + "="*80)
    print("Review Summary:")
    print("="*80)
    print(review_text[:500] + "..." if len(review_text) > 500 else review_text)
    print("="*80)


if __name__ == "__main__":
    main()
