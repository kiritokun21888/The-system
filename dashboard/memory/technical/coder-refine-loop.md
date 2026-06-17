---
id: coder-refine-loop
title: "Coder Refinement Loop"
category: technical
tags: [agents, coder, feedback]
importance: 9
created: 2026-06-17T03:37:48.572488+00:00
updated: 2026-06-17T03:37:48.572488+00:00
linked: [spec-parser-arch, test-fix-loop]
---

The **Coder** generates code and is the refinement target for both feedback loops. Its cache key embeds the attempt counter so refinements are never short-circuited by the cache.
