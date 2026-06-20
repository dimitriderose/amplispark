---
name: qa-test
description: Implement tests as QA Testers based on a QA test plan. Use when the user wants to write tests, implement a test plan, or add test coverage.
---
Implement tests as QA Testers based on the QA test plan.

## Steps

1. Read the test plan from `docs/feature-specs/{feature-name}-test-plan.md`.
   Read `backend/tests/conftest.py` for existing fixtures.
   Read the most relevant existing test file for patterns (e.g. `test_posts.py` for post changes).

2. Act as **QA Tester**. Write pytest tests in `backend/tests/test_{feature-name}.py`:

   ### Test patterns to follow
   - `asyncio_mode = auto` is set in `pytest.ini` — no `@pytest.mark.asyncio` needed
   - Mock Firestore via the `mock_db` fixture from `conftest.py`
   - Mock Firebase auth via the `mock_verify_token` fixture
   - Use `AsyncMock` for Firestore async operations
   - Parametrize with `@pytest.mark.parametrize` for edge cases
   - Group with classes: `class TestFeatureName:` with `test_*` methods
   - Test names must be self-describing: `test_create_post_returns_400_when_caption_empty`

   ### Coverage requirements
   - Every happy path scenario from the test plan
   - Every edge case
   - Every error case
   - At least one regression test for each existing behavior the change touches

   ### Code quality rules
   - No comments explaining WHAT the test does — the name must do that
   - No magic numbers — use named constants or parametrize values
   - Each test asserts one behavior (or closely related asserts for a single outcome)

3. Run the full test suite:
   ```powershell
   .\backend\.venv\Scripts\python -m pytest backend/tests/ -v --tb=short
   ```

4. Report: number of new tests added, full test results, any failures diagnosed and fixed.
