"""Tests for GitHub workflow YAML files.

Validates that all workflow files parse correctly with PyYAML and that
the Claude PR review workflow has proper duplicate detection and concurrency
control configured.
"""

import pathlib
from typing import List

import pytest
import yaml


# Constants
DUPLICATE_GUARD_STEP_ID = "duplicate_guard"


def get_workflow_files() -> List[pathlib.Path]:
    """Get all workflow YAML files."""
    workflows_dir = (
        pathlib.Path(__file__).parent.parent.parent / ".github" / "workflows"
    )
    if not workflows_dir.exists():
        pytest.fail(f"Workflows directory not found: {workflows_dir}")

    workflow_files = list(workflows_dir.glob("*.yml")) + list(
        workflows_dir.glob("*.yaml")
    )
    if not workflow_files:
        pytest.fail(f"No workflow files found in {workflows_dir}")

    return workflow_files


@pytest.mark.unit
@pytest.mark.parametrize("workflow_file", get_workflow_files(), ids=lambda p: p.name)
def test_workflow_yaml_parses(workflow_file: pathlib.Path) -> None:
    """Test that all workflow YAML files parse correctly with PyYAML."""
    with open(workflow_file, "r", encoding="utf-8") as f:
        try:
            content = yaml.safe_load(f)
            assert content is not None, f"{workflow_file.name} is empty"
        except yaml.YAMLError as e:
            pytest.fail(f"Failed to parse {workflow_file.name}: {e}")


@pytest.mark.unit
def test_claude_pr_review_duplicate_guard() -> None:
    """Test that claude-pr-review.yml has duplicate guard structure."""
    workflow_path = (
        pathlib.Path(__file__).parent.parent.parent
        / ".github"
        / "workflows"
        / "claude-pr-review.yml"
    )

    # Don't skip - this is a critical workflow that must exist
    assert workflow_path.exists(), f"Critical workflow file not found: {workflow_path}"

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    # Verify workflow structure
    assert "jobs" in workflow, "Workflow missing 'jobs' key"
    assert "claude-review" in workflow["jobs"], "Workflow missing 'claude-review' job"

    job = workflow["jobs"]["claude-review"]
    assert "steps" in job, "Job missing 'steps' key"

    # Find the duplicate guard step
    duplicate_guard_step = None
    for step in job["steps"]:
        if step.get("id") == DUPLICATE_GUARD_STEP_ID:
            duplicate_guard_step = step
            break

    assert duplicate_guard_step is not None, (
        f"Missing duplicate_guard step with id='{DUPLICATE_GUARD_STEP_ID}'"
    )
    assert "uses" in duplicate_guard_step, "duplicate_guard step missing 'uses' key"
    assert "actions/github-script@" in duplicate_guard_step["uses"], (
        "duplicate_guard not using github-script action"
    )
    assert "script" in duplicate_guard_step.get("with", {}), (
        "duplicate_guard missing script"
    )

    # Verify the script contains key duplicate detection logic
    script = duplicate_guard_step["with"]["script"]
    assert "claude-review:" in script, "Script missing claude-review marker"
    assert "skip_duplicate" in script, "Script missing skip_duplicate logic"
    assert "head_sha" in script or "headSha" in script, (
        "Script missing head SHA handling"
    )

    # Verify there's a step that checks the duplicate guard output
    has_conditional_step = False
    for step in job["steps"]:
        if "if" in step and "duplicate_guard.outputs" in step["if"]:
            has_conditional_step = True
            break

    assert has_conditional_step, (
        "No steps conditionally execute based on duplicate_guard output"
    )


@pytest.mark.unit
def test_claude_pr_review_concurrency() -> None:
    """Test that claude-pr-review.yml has concurrency configuration."""
    workflow_path = (
        pathlib.Path(__file__).parent.parent.parent
        / ".github"
        / "workflows"
        / "claude-pr-review.yml"
    )

    # Don't skip - this is a critical workflow that must exist
    assert workflow_path.exists(), f"Critical workflow file not found: {workflow_path}"

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    # Verify concurrency configuration
    assert "concurrency" in workflow, "Workflow missing 'concurrency' key"
    assert "group" in workflow["concurrency"], "Concurrency missing 'group' key"
    assert "cancel-in-progress" in workflow["concurrency"], (
        "Concurrency missing 'cancel-in-progress' key"
    )

    # Verify group contains PR number or run_id
    group = workflow["concurrency"]["group"]
    assert "pull_request.number" in group or "run_id" in group, (
        "Concurrency group should reference PR number or run_id"
    )
