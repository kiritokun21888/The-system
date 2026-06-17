---
id: spec-parser-arch
title: "SpecParser Architecture"
category: technical
tags: [agents, spec, validation]
importance: 8
created: 2026-06-17T03:37:48.572488+00:00
updated: 2026-06-17T03:37:48.572488+00:00
linked: [coder-refine-loop, model-routing]
---

The **SpecParser** converts a free-form prompt into a structured `Spec` (function name, signature, requirements, examples). It uses the cheaper validation model and emits a `DataValidationError` on empty prompts.

Quality score = 0.4 + 0.3·requirements + 0.2·examples + 0.1·signature.
