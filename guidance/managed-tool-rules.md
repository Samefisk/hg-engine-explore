# Managed tool rules

Read this file before using ImageGen, agent-browser, or Playwright CLI in this project.

- Follow the current host tool instructions and permission limits. Use only APIs that the host exposes and documents.
- Use the user's task scope and existing authorization. A tool workflow does not grant permission to publish, send messages, or change unrelated work.
- For ImageGen, read the imagegen skill and use the host image generation tool. Inspect a supplied local reference before editing it.
- For browser work, use a purpose-built tool or API when available. Otherwise use the enabled browser control tool and read its returned documentation before further calls. Use agent-browser or Playwright CLI only when the host supports that workflow.
- Game tests use memory-backed observations. Capture or inspect game screenshots and video only after an explicit user request or a manual Capture click, as required by [AGENTS.md](../AGENTS.md#build-and-test-requests).
- Keep source changes in the current checkout and preserve unrelated edits. A tool workflow does not authorize a new worktree.

The host's tool limits apply even when a skill gives a different tool route. Explicit user task instructions take precedence over skill guidance.
