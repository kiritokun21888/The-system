---
id: test-fix-loop
title: "Test-Fix Feedback Loop"
category: technical
tags: [feedback, testing, loops]
importance: 9
created: 2026-06-17T03:37:48.572488+00:00
updated: 2026-06-17T03:37:48.572488+00:00
linked: [coder-refine-loop, review-refine-loop]
---

When the TestRunner reports a failing test (LOGIC failure), the orchestrator routes back to the Coder with the failing traces as context. Converges when pass_rate == 1.0; hard cap of 4 iterations is the divergence guard.
