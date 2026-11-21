"""Host adapters — ToolHost protocol, Skillware reference, mock skills."""

from aura.hosts.manifest import (
    ManifestValidationError,
    extract_manifest_taxonomy,
    has_physical_target,
    manifest_snapshot_hash,
    manifest_to_rules,
    merge_manifest_into_rules,
    normalize_skill_manifest,
    requires_physical_approval_gate,
    validate_skill_manifest,
)
from aura.hosts.mock import MockSkill, MockSkillRegistry
from aura.hosts.protocol import AsyncSkillExecutor, AsyncToolHost, SkillExecutor, ToolHost
from aura.hosts.skillware import (
    SkillwareHost,
    skillware_available,
    skillware_capabilities,
    skillware_version,
)
from aura.hosts.skillware_adapter import (
    SkillwareRegistrySkill,
    load_registry_skill,
    load_registry_skills,
)
from aura.hosts.skillware_audit import (
    DualChainVerificationResult,
    create_dispatch_audit_hook,
    extract_provenance_hash,
    verify_dual_audit_chain,
)

__all__ = [
    "AsyncSkillExecutor",
    "AsyncToolHost",
    "DualChainVerificationResult",
    "ManifestValidationError",
    "MockSkill",
    "MockSkillRegistry",
    "SkillExecutor",
    "SkillwareHost",
    "SkillwareRegistrySkill",
    "ToolHost",
    "create_dispatch_audit_hook",
    "extract_manifest_taxonomy",
    "extract_provenance_hash",
    "has_physical_target",
    "load_registry_skill",
    "load_registry_skills",
    "manifest_snapshot_hash",
    "manifest_to_rules",
    "merge_manifest_into_rules",
    "normalize_skill_manifest",
    "requires_physical_approval_gate",
    "skillware_available",
    "skillware_capabilities",
    "skillware_version",
    "validate_skill_manifest",
    "verify_dual_audit_chain",
]
