# Pull Request

## Description

<!-- Provide a clear and concise description of the changes -->

## Type of Change

<!-- Mark the relevant option with an 'x' -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🎨 Code style update (formatting, renaming)
- [ ] ♻️ Refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] ✅ Test update
- [ ] 🔧 Build configuration change
- [ ] 🔒 Security fix

## Related Issues

<!-- Link related issues using keywords: Fixes #123, Closes #456, Related to #789 -->

Fixes #
Related to #

## Changes Made

<!-- List the specific changes made in this PR -->

-
-
-

## Testing

<!-- Describe the tests you ran to verify your changes -->

### Test Coverage

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing locally
- [ ] Coverage maintained/improved (>80%)

### Manual Testing

<!-- Describe manual testing performed -->

```bash
# Commands used for testing
```

**Test Results:**
-
-

## Screenshots / Examples

<!-- If applicable, add screenshots or code examples to demonstrate the changes -->

```python
# Code examples
```

## Checklist

<!-- Mark completed items with an 'x' -->

### Code Quality

- [ ] My code follows the project's style guidelines (PEP 8, Ruff)
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added type hints to new functions/methods

### Async Patterns (for HTTP/IO changes)

- [ ] No new `httpx.AsyncClient()` instantiations (use `await get_http_client()` instead)
- [ ] All async functions properly use `await` keywords
- [ ] No `time.sleep()` in async functions (use `await asyncio.sleep()` instead)
- [ ] Services use async context managers (`__aenter__`/`__aexit__`) when appropriate
- [ ] Connection pooling is utilized via shared HTTP client
- [ ] I have read [docs/async_patterns.md](../docs/async_patterns.md)

### Testing

- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

### Security

- [ ] I have checked for security vulnerabilities (SQL injection, XSS, etc.)
- [ ] No sensitive data (API keys, passwords) is hardcoded
- [ ] Input validation is properly implemented
- [ ] I have run security scanners (bandit, pip-audit)

### Documentation

- [ ] I have updated the README.md (if needed)
- [ ] I have updated CHANGELOG.md
- [ ] I have added/updated docstrings
- [ ] API documentation is updated (if applicable)

### Dependencies

- [ ] I have not introduced new dependencies unnecessarily
- [ ] New dependencies are pinned to specific versions
- [ ] I have updated requirements.txt / pyproject.toml
- [ ] Dependencies pass security audit (pip-audit)

## Breaking Changes

<!-- If this PR introduces breaking changes, describe them here -->

**Before:**
```python
# Old behavior
```

**After:**
```python
# New behavior
```

**Migration Guide:**
1.
2.
3.

## Performance Impact

<!-- Describe any performance implications -->

- [ ] No performance impact
- [ ] Performance improved
- [ ] Performance may be affected (explain below)

**Details:**

## Database Changes

<!-- If applicable, describe database schema changes -->

- [ ] No database changes
- [ ] New tables/columns added
- [ ] Migration script provided
- [ ] Backwards compatible

## Deployment Notes

<!-- Special instructions for deploying this change -->

**Pre-deployment:**
-

**Post-deployment:**
-

## Rollback Plan

<!-- How to rollback if issues are discovered -->

1.
2.

---

## 🤖 Claude AI Review

<!-- Claude will automatically review this PR when it's created or updated -->

Want a focused review on specific aspects? Tag @claude with a comment:

- `@claude please review` - Full code review
- `@claude check for security issues` - Security-focused review
- `@claude suggest optimizations` - Performance review
- `@claude review test coverage` - Testing review

See [CLAUDE.md](../CLAUDE.md) for more information.

---

## Additional Notes

<!-- Any additional information that reviewers should know -->

---

**Reviewer Guidelines:**

- Check code quality and adherence to standards
- Verify test coverage is adequate
- Look for potential security issues
- Consider performance implications
- Ensure documentation is clear and complete
- Test the changes locally if possible
