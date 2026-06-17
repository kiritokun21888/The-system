---
id: websocket-bridge
title: "WebSocket Event Bridge"
category: project
tags: [dashboard, backend, realtime]
importance: 8
created: 2026-06-17T03:37:48.572488+00:00
updated: 2026-06-17T03:37:48.572488+00:00
linked: [mission-control]
---

FastAPI backend polls the live Swarm metrics + task state and broadcasts `agent_status`, `task_update`, `metric_update`, `log_entry`, and `memory_update` events over `ws://localhost:8000/ws`.
