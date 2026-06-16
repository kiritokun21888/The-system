"""Shared pytest fixtures and path setup for the system test suite.

Adds the ``system`` package root to ``sys.path`` so tests can ``import agents``
and ``import core`` directly, and provides factory fixtures that build agents,
registries, and orchestrators wired to in-memory state and the deterministic
LLM backend.
"""

from __future__ import annotations

import copy
import os
import sys
from typing import Any, Callable

import pytest

# Make the system package importable regardless of pytest's CWD.
_ROOT = os.path.dirname(__file__)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agents.orchestrator import AgentRegistry, Orchestrator  # noqa: E402
from core.cache import TTLCache  # noqa: E402
from core.config import Config  # noqa: E402
from core.failure_handler import FailureHandler  # noqa: E402
from core.llm_client import DeterministicLLMClient, LLMClient  # noqa: E402
from core.metrics import MetricsRegistry  # noqa: E402
from core.state_manager import StateManager  # noqa: E402


def _deep_set(d: dict[str, Any], dotted: str, value: Any) -> None:
    """Set a nested dict value via a dotted key, creating intermediate dicts."""
    node = d
    parts = dotted.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


@pytest.fixture
def make_config() -> Callable[..., Config]:
    """Return a factory producing a Config from the real file with overrides.

    Overrides are passed as dotted kwargs, e.g.
    ``make_config(**{"system.task_timeout_seconds": 0})``.
    """
    base = Config.load(os.path.join(_ROOT, "config.yaml"))

    def factory(**overrides: Any) -> Config:
        data = copy.deepcopy(base.raw)
        # Use an in-memory state DB and the log file in a temp-safe spot.
        _deep_set(data, "system.state_path", ":memory:")
        _deep_set(data, "monitoring.dashboard_enabled", False)
        for key, value in overrides.items():
            _deep_set(data, key, value)
        return Config(data)

    return factory


@pytest.fixture
def config(make_config: Callable[..., Config]) -> Config:
    """A default test config (in-memory state, dashboard off)."""
    return make_config()


@pytest.fixture
def infra(config: Config):
    """Bundle the shared infra components used to build agents."""
    cache = TTLCache(max_entries=256)
    metrics = MetricsRegistry()
    failure = FailureHandler(config)
    return {"cache": cache, "metrics": metrics, "failure": failure}


@pytest.fixture
def llm() -> LLMClient:
    """A clean deterministic LLM client."""
    return DeterministicLLMClient()


@pytest.fixture
def make_agent(config: Config, infra, llm: LLMClient) -> Callable[..., Any]:
    """Return a factory that builds a single agent instance by name.

    Usage: ``make_agent("coder")`` or ``make_agent("coder", llm=custom)``.
    """
    import importlib

    def factory(name: str, *, cfg: Config = None, llm_client: LLMClient = None):
        cfg = cfg or config
        acfg = cfg.agent_config(name)
        module = importlib.import_module(acfg["module"])
        cls = getattr(module, acfg["class_name"])
        return cls(
            name,
            cfg,
            llm_client or llm,
            infra["cache"],
            infra["metrics"],
            infra["failure"],
        )

    return factory


@pytest.fixture
def make_orchestrator(config: Config, infra, llm: LLMClient) -> Callable[..., Any]:
    """Return a factory that builds a fully-wired Orchestrator.

    Usage: ``orch, state_mgr = make_orchestrator()`` or with a custom config /
    llm client: ``make_orchestrator(cfg=custom, llm_client=client)``.
    """

    def factory(*, cfg: Config = None, llm_client: LLMClient = None):
        cfg = cfg or config
        client = llm_client or llm
        cache = TTLCache(max_entries=256)
        metrics = MetricsRegistry()
        failure = FailureHandler(cfg)
        state_mgr = StateManager(db_path=":memory:")
        registry = AgentRegistry(cfg, client, cache, metrics, failure)
        orch = Orchestrator(cfg, registry, state_mgr, failure, metrics)
        return orch, state_mgr

    return factory
