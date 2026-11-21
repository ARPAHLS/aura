"""Skillware host — wrap Skillware execute() through the membrane egress."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any, Callable, Mapping

from aura.hosts.bind import record_skill_bind
from aura.hosts.manifest import (
    ManifestValidationError,
    extract_manifest_taxonomy,
    has_physical_target,
    manifest_snapshot_hash,
    merge_manifest_into_rules,
    normalize_skill_manifest,
    validate_skill_manifest,
)
from aura.hosts.protocol import SkillExecutor
from aura.hosts.skillware_adapter import (
    SkillwareRegistrySkill,
    load_registry_skill,
    make_broker_credential_fn,
)
from aura.hosts.skillware_audit import create_dispatch_audit_hook, current_egress_span
from aura.membrane.egress import guarded_tool_call, guarded_tool_call_async


class _SkillContextExecutor:
    """Routes a single skill inside a Skillware SkillContext through AURA egress."""

    def __init__(
        self,
        skill_id: str,
        context: Any,
        manifest: dict[str, Any],
        *,
        session: Any,
        root_tier: str | None = None,
    ) -> None:
        self.skill_id = skill_id
        self._context = context
        self.manifest = dict(manifest)
        self._session = session
        self.root_tier = root_tier

    def _call_audit_meta(self, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        trace_id = getattr(self._session, "trace_id", None)
        if trace_id:
            meta["trace_id"] = str(trace_id)
        frame = current_egress_span()
        if frame and frame.get("span_id"):
            meta["span_id"] = str(frame["span_id"])
        if extra:
            meta.update(dict(extra))
        return meta

    def execute(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        audit_meta: Mapping[str, Any] | None = None,
    ) -> Any:
        params = dict(args or {})
        if headers is not None and "headers" not in params:
            params["headers"] = dict(headers)
        meta = self._call_audit_meta(audit_meta)
        try:
            sig = inspect.signature(self._context.execute)
            if "audit_meta" in sig.parameters:
                return self._context.execute(self.skill_id, params, audit_meta=meta)
        except (TypeError, ValueError):
            pass
        return self._context.execute(self.skill_id, params)

    async def aexecute(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        timeout: float | None = None,
        audit_meta: Mapping[str, Any] | None = None,
    ) -> Any:
        params = dict(args or {})
        if headers is not None and "headers" not in params:
            params["headers"] = dict(headers)
        meta = self._call_audit_meta(audit_meta)
        aexecute_fn = getattr(self._context, "aexecute", None)
        if callable(aexecute_fn):
            try:
                sig = inspect.signature(aexecute_fn)
                kwargs: dict[str, Any] = {}
                if "timeout" in sig.parameters and timeout is not None:
                    kwargs["timeout"] = timeout
                if "audit_meta" in sig.parameters:
                    kwargs["audit_meta"] = meta
                return await aexecute_fn(self.skill_id, params, **kwargs)
            except (TypeError, ValueError):
                return await aexecute_fn(self.skill_id, params)
        return await asyncio.to_thread(
            self.execute, tool, args, headers=headers, audit_meta=audit_meta
        )


class SkillwareHost:
    """
    Reference ToolHost adapter for Skillware skills.
    All tool execution passes through AURA egress (policy + audit).
    """

    def __init__(
        self,
        session: Any,
        *,
        skill_context: Any | None = None,
        manifest_validation: str = "warn",
        allow_hardware_execution: bool = False,
        hardware_gate: str = "auto",
        auto_schema_from_manifest: bool | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        self.session = session
        self._skills: dict[str, SkillExecutor] = {}
        self._skill_context = skill_context
        self.manifest_validation = str(manifest_validation or "warn").strip().lower()
        self.allow_hardware_execution = bool(allow_hardware_execution)
        self.hardware_gate = str(hardware_gate or "auto").strip().lower()
        self.auto_schema_from_manifest = auto_schema_from_manifest
        self._max_concurrency = max_concurrency
        self._semaphore: asyncio.Semaphore | None = None
        self._semaphore_loop: asyncio.AbstractEventLoop | None = None

    @property
    def skill_context(self) -> Any | None:
        """Attached Skillware SkillContext, if host was constructed with one."""
        return self._skill_context

    def dispatch_audit_hook(
        self,
        *,
        source: str = "skillware.context",
    ) -> Callable[[dict[str, Any]], None]:
        """Return an ``on_dispatch`` callback bridging SkillContext events into AURA's spine."""
        return create_dispatch_audit_hook(self.session, source=source)

    def register(self, skill: SkillExecutor) -> None:
        manifest = getattr(skill, "manifest", None)
        root_tier = getattr(skill, "root_tier", None)
        if isinstance(manifest, dict) and manifest:
            self._bind_manifest(skill.skill_id, manifest, root_tier=root_tier)
        self._skills[skill.skill_id] = skill

    def register_registry_skill(
        self,
        skill_id: str,
        *,
        config: dict[str, Any] | None = None,
        credential_fn: Callable[[str], str | None] | None = None,
        check_requirements: bool = True,
    ) -> SkillwareRegistrySkill:
        """Load a Skillware registry skill and register it on this host."""
        effective_cred_fn = credential_fn or make_broker_credential_fn(self.session)
        skill = load_registry_skill(
            skill_id,
            config=config,
            credential_fn=effective_cred_fn,
            check_requirements=check_requirements,
        )
        self.register(skill)
        return skill

    def register_by_id(
        self, skill_id: str, skill: Any, *, manifest: dict[str, Any] | None = None
    ) -> None:
        """Wrap a Skillware BaseSkill or mock skill instance."""
        wrapped = _wrap_skillware_instance(skill_id, skill)
        skill_manifest = manifest or getattr(skill, "manifest", None)
        if isinstance(skill_manifest, dict):
            wrapped.manifest = skill_manifest  # type: ignore[attr-defined]
        self.register(wrapped)

    def execute(
        self,
        skill_id: str,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        step_id: str | None = None,
        audit_meta: Mapping[str, Any] | None = None,
    ) -> Any:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill not registered: {skill_id}")

        def run(live_args: dict[str, Any], headers: dict[str, Any] | None = None) -> Any:
            effective_headers = headers or (
                live_args.get("headers") if isinstance(live_args.get("headers"), dict) else None
            )
            try:
                sig = inspect.signature(skill.execute)
                kwargs: dict[str, Any] = {}
                if "headers" in sig.parameters:
                    kwargs["headers"] = effective_headers
                if "audit_meta" in sig.parameters and audit_meta is not None:
                    kwargs["audit_meta"] = audit_meta
                if kwargs:
                    return skill.execute(tool, live_args, **kwargs)
            except (TypeError, ValueError):
                pass
            return skill.execute(tool, live_args)

        audit_tool = tool or skill_id
        manifest = getattr(skill, "manifest", None)
        skill_version = (
            str(manifest["version"])
            if isinstance(manifest, dict) and manifest.get("version") is not None
            else None
        )
        return guarded_tool_call(
            self.session,
            tool=audit_tool,
            skill_id=skill_id,
            args=args,
            headers=headers,
            execute=run,
            step_id=step_id,
            audit_meta=audit_meta,
            skill_version=skill_version,
        )

    def _get_semaphore(self) -> asyncio.Semaphore | None:
        if self._max_concurrency is None or self._max_concurrency <= 0:
            return None
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._semaphore_loop is not loop:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)
            self._semaphore_loop = loop
        return self._semaphore

    async def aexecute(
        self,
        skill_id: str,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        headers: dict[str, Any] | None = None,
        step_id: str | None = None,
        timeout: float | None = None,
        audit_meta: Mapping[str, Any] | None = None,
    ) -> Any:
        """Execute a registered skill asynchronously through AURA membrane egress."""
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill not registered: {skill_id}")

        async def run_async(
            live_args: dict[str, Any], headers: dict[str, Any] | None = None
        ) -> Any:
            effective_headers = headers or (
                live_args.get("headers") if isinstance(live_args.get("headers"), dict) else None
            )
            aexecute_fn = getattr(skill, "aexecute", None)
            if callable(aexecute_fn):
                try:
                    sig = inspect.signature(aexecute_fn)
                    kwargs: dict[str, Any] = {}
                    if "headers" in sig.parameters:
                        kwargs["headers"] = effective_headers
                    if "audit_meta" in sig.parameters and audit_meta is not None:
                        kwargs["audit_meta"] = audit_meta
                    if "timeout" in sig.parameters and timeout is not None:
                        kwargs["timeout"] = timeout
                    if kwargs:
                        return await aexecute_fn(tool, live_args, **kwargs)
                except (TypeError, ValueError):
                    pass
                return await aexecute_fn(tool, live_args)

            def _sync_call() -> Any:
                try:
                    sig = inspect.signature(skill.execute)
                    kwargs: dict[str, Any] = {}
                    if "headers" in sig.parameters:
                        kwargs["headers"] = effective_headers
                    if "audit_meta" in sig.parameters and audit_meta is not None:
                        kwargs["audit_meta"] = audit_meta
                    if kwargs:
                        return skill.execute(tool, live_args, **kwargs)
                except (TypeError, ValueError):
                    pass
                return skill.execute(tool, live_args)

            return await asyncio.to_thread(_sync_call)

        audit_tool = tool or skill_id
        manifest = getattr(skill, "manifest", None)
        skill_version = (
            str(manifest["version"])
            if isinstance(manifest, dict) and manifest.get("version") is not None
            else None
        )
        sem = self._get_semaphore()
        if sem is not None:
            async with sem:
                return await guarded_tool_call_async(
                    self.session,
                    tool=audit_tool,
                    skill_id=skill_id,
                    args=args,
                    headers=headers,
                    execute=run_async,
                    step_id=step_id,
                    timeout=timeout,
                    audit_meta=audit_meta,
                    skill_version=skill_version,
                )
        return await guarded_tool_call_async(
            self.session,
            tool=audit_tool,
            skill_id=skill_id,
            args=args,
            headers=headers,
            execute=run_async,
            step_id=step_id,
            timeout=timeout,
            audit_meta=audit_meta,
            skill_version=skill_version,
        )

    @classmethod
    def from_skillware(cls, session: Any, skills: list[Any]) -> "SkillwareHost":
        """Build host from Skillware BaseSkill instances or SkillwareRegistrySkill adapters."""
        host = cls(session)
        for skill in skills:
            if isinstance(skill, SkillwareRegistrySkill):
                host.register(skill)
                continue
            skill_id = getattr(skill, "skill_id", None) or getattr(
                skill, "id", type(skill).__name__
            )
            manifest = getattr(skill, "manifest", None)
            host.register_by_id(
                str(skill_id),
                skill,
                manifest=manifest if isinstance(manifest, dict) else None,
            )
        return host

    @classmethod
    def from_registry(cls, session: Any, skill_ids: list[str]) -> "SkillwareHost":
        """Load and register Skillware registry skills by id."""
        host = cls(session)
        for skill_id in skill_ids:
            host.register_registry_skill(skill_id)
        return host

    @classmethod
    def from_skill_context(
        cls,
        session: Any,
        context: Any,
        *,
        attach_audit_hook: bool = True,
        manifest_validation: str = "warn",
        allow_hardware_execution: bool | None = None,
        hardware_gate: str = "auto",
        auto_schema_from_manifest: bool | None = None,
        max_concurrency: int | None = None,
    ) -> "SkillwareHost":
        """
        Wrap an existing Skillware ``SkillContext`` so every skill executes through AURA egress.

        Prefer ``SkillwareHost.create_context()`` or constructing ``SkillContext`` with
        ``on_dispatch=create_dispatch_audit_hook(session)`` for pure public-API wiring.
        When ``attach_audit_hook=True`` on an existing context, AURA uses a public hook
        setter if present or safely guards fallback attachment on Skillware's dispatcher.
        """
        effective_hw = (
            bool(getattr(context, "allow_hardware_execution", False))
            if allow_hardware_execution is None
            else bool(allow_hardware_execution)
        )
        effective_conc = (
            getattr(context, "_max_concurrency", None)
            if max_concurrency is None
            else max_concurrency
        )
        host = cls(
            session,
            skill_context=context,
            manifest_validation=manifest_validation,
            allow_hardware_execution=effective_hw,
            hardware_gate=hardware_gate,
            auto_schema_from_manifest=auto_schema_from_manifest,
            max_concurrency=effective_conc,
        )
        if attach_audit_hook:
            _attach_context_audit_hook(context, host.dispatch_audit_hook())

        bundles = getattr(context, "_bundles", {}) or {}
        tier_by_id = getattr(context, "_tier_by_id", {}) or {}
        skill_ids = list(getattr(context, "skill_ids", []) or bundles.keys())
        for skill_id in skill_ids:
            bundle = bundles.get(skill_id) or {}
            manifest = dict(bundle.get("manifest") or {})
            executor = _SkillContextExecutor(
                skill_id,
                context,
                manifest,
                session=session,
                root_tier=tier_by_id.get(skill_id),
            )
            host.register(executor)
        return host

    @classmethod
    def create_context(
        cls,
        session: Any,
        *,
        audit_log_path: str | Path | None = None,
        attach_audit_hook: bool = True,
        manifest_validation: str = "warn",
        allow_hardware_execution: bool = False,
        hardware_gate: str = "auto",
        auto_schema_from_manifest: bool | None = None,
        max_concurrency: int | None = None,
        **context_kwargs: Any,
    ) -> "SkillwareHost":
        """
        Construct a Skillware ``SkillContext`` with AURA's dispatch audit hook pre-wired
        and return a ``SkillwareHost`` wrapping all discovered skills.

        Degrades gracefully on Skillware 0.6.2 (without ``on_dispatch``) by omitting
        unsupported kwargs while still routing all calls through AURA egress.
        """
        from skillware import SkillContext

        kwargs = dict(context_kwargs)
        sig = inspect.signature(SkillContext.__init__)

        if "allow_hardware_execution" in sig.parameters:
            kwargs.setdefault("allow_hardware_execution", allow_hardware_execution)
        if max_concurrency is not None and "max_concurrency" in sig.parameters:
            kwargs.setdefault("max_concurrency", max_concurrency)

        if "secret_provider" in sig.parameters and "secret_provider" not in kwargs:
            cred_fn = make_broker_credential_fn(session)
            if cred_fn is not None:
                kwargs["secret_provider"] = _AuraSecretProviderAdapter(cred_fn)

        if attach_audit_hook and "on_dispatch" in sig.parameters:
            user_hook = kwargs.get("on_dispatch")
            aura_hook = create_dispatch_audit_hook(session)
            if callable(user_hook):

                def _chained_hook(evt: dict[str, Any]) -> None:
                    aura_hook(evt)
                    user_hook(evt)

                kwargs["on_dispatch"] = _chained_hook
            else:
                kwargs["on_dispatch"] = aura_hook

        if audit_log_path is not None and "audit_log_path" in sig.parameters:
            kwargs["audit_log_path"] = audit_log_path

        ctx = SkillContext(**kwargs)
        return cls.from_skill_context(
            session,
            ctx,
            attach_audit_hook=False,
            manifest_validation=manifest_validation,
            allow_hardware_execution=allow_hardware_execution,
            hardware_gate=hardware_gate,
            auto_schema_from_manifest=auto_schema_from_manifest,
            max_concurrency=max_concurrency,
        )

    def _session_spectrum_level(self) -> str | None:
        profile = getattr(self.session, "profile", None)
        if profile is None:
            return None
        from aura.core.spectrum_enforcement import effective_spectrum

        return effective_spectrum(profile).level.lower()

    def _should_auto_wire_schema(self) -> bool:
        if self.auto_schema_from_manifest is not None:
            return bool(self.auto_schema_from_manifest)
        profile = getattr(self.session, "profile", None)
        if profile is None:
            return False
        from aura.core.schema_validation import schema_enforcement_enabled

        return schema_enforcement_enabled(profile)

    def _bind_manifest(
        self,
        skill_id: str,
        manifest: dict[str, Any],
        *,
        root_tier: str | None = None,
    ) -> None:
        session = self.session
        mode = self.manifest_validation
        validation_info: dict[str, Any] | None = None

        if mode != "off":
            errors = validate_skill_manifest(
                manifest,
                skill_id=skill_id,
                strict_required=(mode == "strict"),
            )
            validation_info = {"valid": len(errors) == 0, "errors": errors}
            if errors and mode == "strict":
                session.emit(
                    "skill.manifest_invalid",
                    {
                        "membrane": "ingress",
                        "skill_id": skill_id,
                        "errors": errors,
                    },
                )
                raise ManifestValidationError(skill_id, errors)

        normalized = normalize_skill_manifest(manifest)
        taxonomy = extract_manifest_taxonomy(normalized)
        physical = has_physical_target(manifest)
        deprecated = bool(manifest.get("deprecated"))
        deprecation_notice = (
            str(manifest["deprecation_notice"]) if manifest.get("deprecation_notice") else None
        )
        skill_version = str(manifest["version"]) if manifest.get("version") is not None else None

        spectrum_level = self._session_spectrum_level()
        session.rules = merge_manifest_into_rules(
            session.rules,
            skill_id,
            manifest,
            allow_hardware_execution=self.allow_hardware_execution,
            hardware_gate=self.hardware_gate,
            spectrum_level=spectrum_level,
            auto_schema=self._should_auto_wire_schema(),
        )
        snapshot = manifest_snapshot_hash(skill_id, manifest)
        session.snapshot_hash = _recompute_snapshot_hash(session)
        record_skill_bind(
            session,
            skill_id=skill_id,
            manifest_snapshot_hash=snapshot,
            host_kind="skillware",
            taxonomy=taxonomy,
            skill_version=skill_version,
            root_tier=root_tier,
            deprecated=deprecated,
            deprecation_notice=deprecation_notice,
            physical_target=physical,
            hardware_execution_acknowledged=self.allow_hardware_execution,
            manifest_validation=validation_info,
        )


class _AuraSecretProviderAdapter:
    """Adapt an AURA SecretBroker credential_fn to Skillware's SecretProvider protocol."""

    def __init__(self, credential_fn: Callable[[str], str | None]) -> None:
        self._fn = credential_fn

    def get(self, key: str) -> str | None:
        return self._fn(key)


def _attach_context_audit_hook(
    context: Any,
    aura_hook: Callable[[dict[str, Any]], None],
) -> bool:
    """Attach AURA's dispatch callback onto an existing SkillContext when supported."""
    for method_name in ("add_dispatch_hook", "set_dispatch_hook"):
        setter = getattr(context, method_name, None)
        if callable(setter):
            try:
                setter(aura_hook)
                return True
            except (AttributeError, TypeError, ValueError):
                pass

    try:
        audit_obj = getattr(context, "_audit", None)
        if audit_obj is not None:
            existing = getattr(audit_obj, "_on_dispatch", None)
            if existing is None:
                audit_obj._on_dispatch = aura_hook
                return True
            if existing is not aura_hook:

                def _chained(evt: dict[str, Any]) -> None:
                    aura_hook(evt)
                    existing(evt)

                audit_obj._on_dispatch = _chained
                return True
            return True

        from skillware.audit import AuditDispatcher

        if hasattr(context, "_audit"):
            context._audit = AuditDispatcher(on_dispatch=aura_hook)
            return True
    except (ImportError, AttributeError, TypeError):
        return False
    return False


def _wrap_skillware_instance(skill_id: str, skill: Any) -> SkillExecutor:
    class _Wrapped:
        def __init__(self) -> None:
            self.skill_id = skill_id
            self._skill = skill
            self.manifest: dict[str, Any] = {}

        def execute(
            self,
            tool: str,
            args: dict[str, Any] | None = None,
            *,
            headers: dict[str, Any] | None = None,
        ) -> Any:
            adapter = SkillwareRegistrySkill(
                self.skill_id,
                self._skill,
                self.manifest,
            )
            return adapter.execute(tool, args, headers=headers)

        async def aexecute(
            self,
            tool: str,
            args: dict[str, Any] | None = None,
            *,
            headers: dict[str, Any] | None = None,
        ) -> Any:
            adapter = SkillwareRegistrySkill(
                self.skill_id,
                self._skill,
                self.manifest,
            )
            return await adapter.aexecute(tool, args, headers=headers)

    return _Wrapped()


def _recompute_snapshot_hash(session: Any) -> str:
    from aura.core.session import _snapshot_hash

    return _snapshot_hash(session.profile, session.rules)


def skillware_available() -> bool:
    try:
        import skillware  # noqa: F401

        return True
    except ImportError:
        return False


def skillware_version() -> str | None:
    """Return installed Skillware distribution version, or None if unavailable."""
    if not skillware_available():
        return None
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("skillware")
    except PackageNotFoundError:
        try:
            import skillware

            ver = getattr(skillware, "__version__", None)
            return str(ver) if ver else None
        except ImportError:
            return None


def skillware_capabilities() -> dict[str, bool]:
    """Probe installed Skillware runtime capabilities for graceful version gating."""
    caps = {
        "installed": False,
        "manifest_schema": False,
        "audit_hook": False,
        "async_execution": False,
        "secret_provider": False,
        "deprecation_warning": False,
    }
    if not skillware_available():
        return caps
    caps["installed"] = True

    try:
        import skillware.core.manifest_schema as _ms  # noqa: F401

        caps["manifest_schema"] = hasattr(_ms, "validate_manifest_schema") and hasattr(
            _ms, "normalize_manifest_v2"
        )
    except ImportError:
        pass

    try:
        import skillware.context as _ctx

        ctx_cls = getattr(_ctx, "SkillContext", None)
        if ctx_cls is not None:
            sig = inspect.signature(ctx_cls.__init__)
            caps["secret_provider"] = "secret_provider" in sig.parameters
            caps["async_execution"] = hasattr(ctx_cls, "aexecute")
            try:
                import skillware.audit as _audit  # noqa: F401

                caps["audit_hook"] = (
                    "on_dispatch" in sig.parameters
                    and hasattr(_audit, "AuditDispatcher")
                    and hasattr(_audit, "verify_audit_log")
                )
            except ImportError:
                pass
    except (ImportError, TypeError, ValueError):
        pass

    try:
        import skillware.core.loader as _loader

        caps["deprecation_warning"] = hasattr(_loader, "SkillwareDeprecationWarning")
    except ImportError:
        pass

    return caps
