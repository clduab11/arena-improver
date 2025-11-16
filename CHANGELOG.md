# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed - 2025-11-11

#### License Correction

- **All Project Files**: Corrected license from MIT to AGPL-3.0 to match LICENSE file
  - Updated README.md license badge from MIT to AGPL v3
  - Updated README.md License section from MIT to AGPL-3.0
  - Updated pyproject.toml license field from MIT to AGPL-3.0
  - Ensures consistency across all documentation and metadata

### Merged - 2025-11-11

#### MTG Arena Deck Analyzer Integration

- **Merged main branch**: Integrated complete MTG Arena deck analysis implementation
  - FastAPI REST API for deck upload and analysis
  - MCP protocol server implementation
  - SmartSQL: SQLite database with SQLAlchemy ORM
  - SmartInference: OpenAI-powered optimization suggestions
  - SmartMemory: Historical performance tracking
  - Card similarity embeddings using sentence transformers
  - CSV deck import from Steam MTG Arena
  - Comprehensive test suite (unit + integration tests)
  - Docker deployment support
  - Example workflows and sample data

### Added - November 2025 Claude AI Integration

#### GitHub Integration for Automated Reviews

- **CLAUDE.md**: Comprehensive usage guide for Claude AI integration
  - Command reference for PR and issue reviews
  - Best practices for tagging Claude
  - Example use cases and workflows
  - Troubleshooting guide
  - Learning resources

- **.github/SETUP.md**: Step-by-step setup instructions
  - API key configuration
  - Repository secrets setup
  - Permissions configuration
  - Testing procedures
  - Security best practices
  - Cost management guidance

- **.github/CLAUDE_CONFIG.yml**: Claude behavior configuration
  - Review focus areas (security, performance, testing, etc.)
  - Auto-review settings
  - Severity thresholds
  - Rate limiting
  - Project-specific context
  - Customizable review patterns

#### GitHub Actions Workflows

- **.github/workflows/claude-pr-review.yml**: Automated PR code review
  - Triggers on PR creation, updates, or @claude mention
  - Comprehensive code analysis
  - Security vulnerability detection
  - Performance optimization suggestions
  - Test coverage verification
  - Automated comment posting with review results

- **.github/workflows/claude-issue-assistant.yml**: Issue analysis automation
  - Triggers on issue creation with 'claude-review' label or @claude mention
  - Root cause analysis
  - Solution recommendations with code examples
  - Similar issue detection
  - Testing strategy suggestions

#### Review Automation Scripts

- **.github/scripts/claude_reviewer.py**: PR review implementation
  - Fetches PR diffs and context
  - Analyzes code changes using Claude API
  - Checks for security issues, bugs, code quality
  - Generates formatted review comments
  - Tracks metrics and usage

- **.github/scripts/claude_issue_assistant.py**: Issue assistance implementation
  - Fetches issue context and comments
  - Searches for similar issues
  - Extracts relevant code snippets
  - Provides detailed analysis and solutions
  - Suggests prevention strategies

#### GitHub Templates

- **.github/ISSUE_TEMPLATE/bug_report.yml**: Bug report template
  - Structured issue format
  - Claude integration hints
  - Pre-submission checklist
  - Environment information collection

- **.github/ISSUE_TEMPLATE/feature_request.yml**: Feature request template
  - Problem statement format
  - Use case collection
  - Implementation assistance offers
  - Claude guidance integration

- **.github/ISSUE_TEMPLATE/config.yml**: Template configuration
  - Links to documentation
  - Community discussion channels
  - Claude integration guide

- **.github/PULL_REQUEST_TEMPLATE.md**: PR template
  - Comprehensive PR checklist
  - Code quality requirements
  - Security verification
  - Testing guidelines
  - Claude review instructions

#### Features

- **Automated Code Reviews**: Claude analyzes PRs for security, quality, and performance
- **Security Scanning**: Detects SQL injection, XSS, command injection, and more
- **Issue Analysis**: Provides root cause analysis and solution recommendations
- **Code Examples**: Generates specific code fixes and improvements
- **Test Coverage**: Verifies and suggests test improvements
- **Performance**: Identifies optimization opportunities
- **Documentation**: Reviews and suggests documentation improvements

#### Benefits

- Faster code review turnaround
- Consistent review quality
- Early detection of security issues
- Educational feedback for developers
- 24/7 availability for assistance
- Reduced reviewer workload

### Added - November 2025 Best Practices Implementation

#### Dependency Management

- **requirements.txt**: Modern production dependencies file with:
  - Organized structure by category (framework, data processing, database, etc.)
  - Pinned versions for reproducibility
  - Comprehensive comments and documentation
  - Latest stable package versions as of November 2025
  - Security-conscious package selection

- **requirements-dev.txt**: Separate development dependencies including:
  - Testing framework: pytest 8.3.4 with plugins (asyncio, mock, xdist, coverage)
  - Code quality: ruff 0.9.3, mypy 1.13.0, pylint 3.3.2, bandit 1.7.10
  - Code formatting: black 24.10.0, isort 5.13.2, autoflake 2.3.1
  - Documentation: sphinx 8.1.3, mkdocs 1.6.1 with material theme
  - Security scanning: pip-audit 2.7.3, safety 3.2.11
  - Development tools: ipython 8.30.0, pre-commit 4.0.1, pip-tools 7.4.1
  - Type stubs for common libraries

#### Project Configuration

- **pyproject.toml**: Modern Python project configuration (PEP 517/518/621) with:
  - Build system requirements
  - Project metadata and dependencies
  - Optional dependency groups (dev, test, docs)
  - Comprehensive tool configurations:
    - Ruff: Fast linting and formatting with 40+ rule categories
    - Black: Code formatter settings (100 char line length)
    - isort: Import statement organization
    - MyPy: Strict type checking configuration
    - Pytest: Testing framework with coverage and markers
    - Coverage: Code coverage measurement settings
    - Bandit: Security linting configuration
    - Pylint: Additional linting rules

#### Version Management

- **.python-version**: Python 3.11.10 specification for pyenv/asdf compatibility

#### Code Quality & Automation

- **.pre-commit-config.yaml**: Comprehensive pre-commit hooks including:
  - General hooks: trailing whitespace, EOF fixer, YAML/TOML/JSON validation
  - Ruff: Fast Python linting and formatting
  - MyPy: Static type checking with type stubs
  - Bandit: Security vulnerability scanning
  - Safety: Dependency vulnerability checks
  - Prettier: Multi-language formatting (YAML, JSON, Markdown)
  - yamllint: YAML linting
  - markdownlint: Markdown linting
  - shellcheck: Shell script linting
  - Commitizen: Conventional commit enforcement
  - detect-secrets: Secrets detection

- **.editorconfig**: Editor configuration for consistent coding styles:
  - UTF-8 charset, LF line endings
  - Space indentation (4 spaces for Python)
  - Proper settings for YAML (2 spaces), JSON (2 spaces), Markdown
  - Support for all major editors/IDEs

- **.yamllint.yaml**: YAML linting configuration with:
  - 120 character line length
  - 2-space indentation
  - Comprehensive rules for YAML formatting
  - Exclude patterns for build directories

- **.secrets.baseline**: Baseline for secrets detection with:
  - 20+ detector plugins (AWS, Azure, GitHub, JWT, Private keys, etc.)
  - Advanced filtering heuristics
  - Empty baseline for new projects

#### Development Utilities

- **Makefile**: Comprehensive development commands:
  - Installation: `make install`, `make dev`, `make hooks`
  - Code quality: `make lint`, `make format`, `make type-check`, `make security`
  - Testing: `make test`, `make test-coverage`, `make test-fast`
  - Pre-commit: `make pre-commit`, `make pre-commit-update`
  - Documentation: `make docs`, `make docs-serve`
  - Dependencies: `make deps-compile`, `make deps-upgrade`, `make deps-audit`
  - Build: `make build`, `make build-check`
  - Cleanup: `make clean`, `make clean-all`
  - CI/CD: `make check`, `make ci`
  - 25+ useful commands with help descriptions

#### Documentation

- **README.md**: Comprehensive project documentation including:
  - Project overview with badge indicators
  - Table of contents for easy navigation
  - Installation instructions (3 different methods)
  - Development setup with pre-commit hooks
  - Code quality guidelines and tools
  - Testing instructions and examples
  - Dependency management philosophy and practices
  - Support for modern tools (uv, poetry, pdm)
  - Makefile command reference
  - Contributing guidelines with conventional commits
  - CI/CD integration examples (GitHub Actions, GitLab CI)
  - Troubleshooting section
  - Resource links to official documentation

- **CHANGELOG.md**: This file for tracking project changes

### Features

#### Best Practices Alignment (November 2025)

1. **Modern Dependency Management**:
   - Pinned versions for reproducibility
   - Separate production/development dependencies
   - Security-first approach with regular audits
   - Support for modern tools (pip-tools, uv, poetry, pdm)

2. **Code Quality Automation**:
   - Pre-commit hooks for automatic checks
   - Multiple linters (Ruff, MyPy, Pylint, Bandit)
   - Automated formatting (Ruff, Black, isort)
   - Security scanning (Bandit, pip-audit, safety)
   - Secrets detection (detect-secrets)

3. **Type Safety**:
   - MyPy with strict configuration
   - Type stubs for common libraries
   - PEP 484 compliance

4. **Testing Infrastructure**:
   - Pytest with plugins (asyncio, mock, xdist)
   - Coverage reporting (HTML, XML, terminal)
   - Property-based testing (hypothesis)
   - Test fixtures and factories

5. **Documentation**:
   - Comprehensive README
   - Multiple documentation tools (Sphinx, MkDocs)
   - CI/CD integration examples
   - Troubleshooting guides

6. **Developer Experience**:
   - Makefile for common commands
   - EditorConfig for consistent styles
   - Python version specification
   - Clear project structure
   - Conventional commits

7. **Security**:
   - Multiple security scanners
   - Dependency vulnerability audits
   - Secrets detection
   - Security-focused linting

8. **CodeFactor Compatibility**:
   - All configurations aligned with code quality standards
   - No unnecessary complexity
   - Clear, well-documented code
   - Comprehensive testing setup
   - Security best practices

### Technical Details

- **Python Version**: 3.11+ (with support for 3.12, 3.13)
- **License**: AGPL-3.0
- **Build System**: setuptools with PEP 517/518 compliance
- **Package Manager**: pip (with support for pip-tools, uv, poetry, pdm)
- **CI/CD Ready**: GitHub Actions and GitLab CI examples provided

### Migration Path

For existing codebases wanting to adopt these practices:

1. Review and compare your current requirements files
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Setup pre-commit hooks: `pre-commit install`
4. Run initial checks: `make check`
5. Fix any issues identified by linters
6. Update documentation as needed
7. Configure CI/CD pipeline using provided examples

### Rationale

This implementation follows November 2025 best practices because:

1. **Ruff** has become the standard for Python linting/formatting (fast, comprehensive)
2. **pyproject.toml** is now the preferred configuration format (PEP 621)
3. **Type hints** are expected in modern Python code (PEP 484)
4. **Pre-commit hooks** are industry standard for code quality automation
5. **Security scanning** is mandatory for modern software development
6. **Pinned dependencies** ensure reproducible builds
7. **Separate dev dependencies** reduce production footprint
8. **Modern tools** (uv, pip-tools) improve development workflow
9. **Comprehensive documentation** improves maintainability
10. **CI/CD integration** enables automated quality checks

### CodeFactor Compliance

All configurations are designed to pass CodeFactor analysis:

- **Code Style**: Ruff + Black ensure PEP 8 compliance
- **Complexity**: Pylint configured with reasonable thresholds
- **Type Safety**: MyPy ensures type correctness
- **Security**: Bandit catches security issues
- **Dependencies**: Regular audits prevent vulnerabilities
- **Documentation**: Comprehensive README and docstrings
- **Testing**: High coverage requirements
- **Consistency**: EditorConfig ensures uniform formatting

### References

- [PEP 517 - Build System Interface](https://peps.python.org/pep-0517/)
- [PEP 518 - Build System Dependencies](https://peps.python.org/pep-0518/)
- [PEP 621 - Project Metadata](https://peps.python.org/pep-0621/)
- [PEP 8 - Style Guide](https://peps.python.org/pep-0008/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pre-commit Framework](https://pre-commit.com/)

---

**Date**: 2025-11-11
**Type**: Initial Setup / Best Practices Implementation
**Impact**: High - Establishes foundation for high-quality Python development
