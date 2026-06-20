Facilitate a feature planning session with a PM and Software Architect.

## Steps

1. Ask the user: "What feature or change are you planning? Describe it in as much detail as you have."
   Wait for their response.

2. Act as **Product Manager**: Read `docs/PRD.md` and analyse the request against it.
   Ask 2-3 clarifying questions covering: user impact, success metrics, edge cases, and scope constraints.
   Wait for answers.

3. Act as **Software Architect**: Read the relevant parts of `docs/TDD.md`, backend routers in
   `backend/routers/`, models in `backend/models/`, services in `backend/services/`, agents in
   `backend/agents/`, and the frontend structure in `frontend/src/`. Identify:
   - Which existing files will change
   - New files required
   - Firestore collection/schema changes needed
   - New AI agent or prompt changes needed
   - API contract changes (new endpoints, request/response shape)
   - Frontend component or route changes
   - Networking/WebSocket/SSE considerations
   - Audio/voice feature considerations
   - Infrastructure or Cloud Run changes
   - Risks and open questions

4. Synthesize into a **Feature Spec** and write it to `docs/feature-specs/{feature-name}.md`:
   - Overview (1 paragraph)
   - User story / acceptance criteria (each must be testable)
   - Backend changes (files, endpoints, schema)
   - Frontend changes (components, routes, state)
   - DB/Firestore changes
   - Prompt/AI changes
   - Network/audio considerations (if applicable)
   - Infrastructure changes (if applicable)
   - Out of scope
   - Open questions

5. Present the spec to the user and ask if they want to adjust anything before coding begins.

## Best practices
- No implementation details that over-constrain the engineer
- Every acceptance criterion must be testable
- Flag anything touching auth, billing, voice streaming, or external integrations as high-risk
