Create a QA test plan for the feature as a QA Lead.

## Steps

1. Read the relevant feature spec from `docs/feature-specs/`. Ask the user which one if multiple exist.
   Also read the existing tests in `backend/tests/` and `backend/tests/conftest.py` to understand current patterns.

2. Act as **QA Lead**. Produce a test plan covering:

   ### Happy Path Tests
   - One test case per acceptance criterion from the spec
   - Include exact input data and expected output/behavior

   ### Edge Cases
   - Empty inputs, maximum field lengths, concurrent requests, missing optional fields
   - Platform-specific behaviors if the feature touches content generation
   - Voice/audio session edge cases (disconnect mid-session, no mic permission) if applicable

   ### Error Cases
   - Auth failures (missing token, expired token, wrong user)
   - Not-found resources (brand not found, post not found)
   - Invalid input (bad types, out-of-range values)
   - External service failures (Gemini API down, Firestore unavailable)
   - Soft delete behavior if posts or brands are affected

   ### Integration Points
   - Firestore operations that need async mocking via `mock_db` fixture
   - Gemini API calls that need mocking
   - Firebase auth that needs the `mock_verify_token` fixture from `conftest.py`
   - WebSocket/SSE connections that need mock handling (if applicable)

   ### Regression Risk
   - List existing tests likely affected by this change
   - Flag gaps in current test coverage this change exposes

3. Write the test plan to `docs/feature-specs/{feature-name}-test-plan.md`.

4. Present the plan to the user and confirm before handing off to `/qa-test`.
