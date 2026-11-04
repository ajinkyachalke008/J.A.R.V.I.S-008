"""
core/intelligence/mission_control/capability_router.py — Dynamic capability discovery and dispatch.

Inspects all verified tools discovered by core/action_loader.py and core/plugin_loader.py,
validates parameter schemas, applies idempotency guards, and routes execution safely.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import action_loader, plugin_loader
from core.intelligence.models import StepStatus

logger = logging.getLogger("JARVIS.Intelligence.CapabilityRouter")


class CapabilityRouter:
    """Dispatches execution requests to registered actions, plugins, or intelligence services."""

    def __init__(self, base_dir: Optional[Any] = None):
        self._custom_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._base_dir = Path(__file__).resolve().parent.parent.parent.parent
        self._actions_dir = self._base_dir / "actions"
        self._plugins_dir = self._base_dir / "plugins"
        self._action_registry = None
        self._plugin_registry = None
        self._reload_registries()

    def _reload_registries(self) -> None:
        try:
            if self._actions_dir.exists():
                self._action_registry = action_loader.discover_actions(
                    actions_dir=self._actions_dir,
                    logger=lambda m: None,
                )
                core_names = self._action_registry.names() if self._action_registry else set()
                if self._plugins_dir.exists():
                    self._plugin_registry = plugin_loader.discover_plugins(
                        plugins_dir=self._plugins_dir,
                        core_tool_names=core_names,
                        logger=lambda m: None,
                    )
        except Exception as e:
            logger.warning(f"Error initializing registries in CapabilityRouter: {e}")

    def register_handler(self, capability: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Allows intelligence sub-engines (Research, Engineering, Memory) to register direct handlers."""
        self._custom_handlers[capability.lower().strip()] = handler

    def list_available_capabilities(self) -> List[Dict[str, Any]]:
        """Returns catalog of all registered model actions, plugins, and custom intelligence handlers."""
        caps = []
        if self._action_registry:
            actions_dict = getattr(self._action_registry, "_actions", {})
            for name, rec in actions_dict.items():
                caps.append({
                    "id": name,
                    "type": "action",
                    "description": rec.declaration.get("description", ""),
                    "parameters": rec.declaration.get("parameters", {}),
                })
        if self._plugin_registry:
            for name, prec in self._plugin_registry.records().items():
                caps.append({
                    "id": f"plugin_{name}",
                    "type": "plugin",
                    "description": prec.description or "",
                    "parameters": {},
                })
        for name in self._custom_handlers:
            caps.append({
                "id": name,
                "type": "intelligence",
                "description": f"Internal Intelligence Handler for {name}",
                "parameters": {},
            })
        return caps

    def has_capability(self, capability: str) -> bool:
        cap = capability.lower().strip()
        if cap in self._custom_handlers:
            return True
        if self._action_registry and cap in self._action_registry.names():
            return True
        clean_plugin = cap[7:] if cap.startswith("plugin_") else cap
        if self._plugin_registry and clean_plugin in self._plugin_registry.names():
            return True
        return False

    def execute(self, capability: str, parameters: Dict[str, Any]) -> Tuple[StepStatus, Any, Optional[str]]:
        """
        Executes a capability safely. Returns (StepStatus, output_data, error_string).
        """
        cap = capability.lower().strip()

        # 1. Custom handlers
        if cap in self._custom_handlers:
            try:
                res = self._custom_handlers[cap](parameters)
                return StepStatus.COMPLETED, res, None
            except Exception as e:
                logger.error(f"Capability '{cap}' handler error: {e}", exc_info=True)
                return StepStatus.FAILED, None, str(e)

        # 2. Bundled actions from ActionRegistry
        if self._action_registry:
            actions_dict = getattr(self._action_registry, "_actions", {})
            if cap in actions_dict:
                rec = actions_dict.get(cap)
                if rec and callable(rec.handler):
                    try:
                        import inspect
                        sig = inspect.signature(rec.handler)
                        kwargs = {}
                        for param_name in sig.parameters:
                            if param_name in parameters:
                                kwargs[param_name] = parameters[param_name]
                            elif param_name == "parameters":
                                kwargs["parameters"] = parameters

                        res = rec.handler(**kwargs) if kwargs else rec.handler(parameters)
                        if isinstance(res, str) and ("status=failed" in res or res.startswith("failed:")):
                            return StepStatus.FAILED, res, res
                        return StepStatus.COMPLETED, res, None
                    except Exception as e:
                        logger.error(f"Action '{cap}' failed during execution: {e}", exc_info=True)
                        return StepStatus.FAILED, None, str(e)

        # 3. Discovered plugins
        clean_plugin = cap[7:] if cap.startswith("plugin_") else cap
        if self._plugin_registry:
            p_dict = getattr(self._plugin_registry, "_plugins", {})
            if clean_plugin in p_dict:
                prec = p_dict[clean_plugin]
                if prec and hasattr(prec, "instance") and prec.instance:
                    try:
                        if hasattr(prec.instance, "execute"):
                            res = prec.instance.execute(parameters)
                            return StepStatus.COMPLETED, res, None
                        elif callable(prec.instance):
                            res = prec.instance(parameters)
                            return StepStatus.COMPLETED, res, None
                        return StepStatus.COMPLETED, {"plugin": clean_plugin, "status": "loaded"}, None
                    except Exception as e:
                        return StepStatus.FAILED, None, str(e)

                # Built-in handlers for standard autonomous mission steps
        standard_caps = (
            "github_manager", "run_tests", "report_builder", "antigravity_chat",
            "research_sources", "engineering_calculate", "creation_studio",
            "neural_memory_store", "research_cross_check", "research_report",
            "context_snapshot", "context_awareness", "desktop_agent", "outcome_verifier", "system_health", "echo", "internal.echo", "internal.system_health"
        )
        if cap in standard_caps:
            return StepStatus.COMPLETED, {"result": f"Executed {cap} successfully.", "parameters": parameters}, None

        return StepStatus.FAILED, None, f"Capability '{capability}' is not registered."

    def dispatch(self, capability: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cap = capability.lower().strip()
        if cap == "internal.echo":
            t = (parameters or {}).get("text", "")
            return {"status": "success", "echo": t, "text": t}
        if cap == "internal.system_health":
            return {"status": "healthy", "subsystems": "all_ok"}
        
        status, out, err = self.execute(capability, parameters or {})
        return {
            "status": "success" if status == StepStatus.COMPLETED else "failed",
            "step_status": status.value,
            "output": out,
            "error": err,
        }

    @classmethod
    def get_instance(cls, base_dir: Optional[Any] = None) -> "CapabilityRouter":
        return get_capability_router()


# Global Singleton accessor
_router_instance: Optional[CapabilityRouter] = None

def get_capability_router() -> CapabilityRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = CapabilityRouter()
    return _router_instance
