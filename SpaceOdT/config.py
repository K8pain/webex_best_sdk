"""Stable configuration contracts for SpaceOdT exports and cache behavior.

This module intentionally centralizes configuration defaults and schema-version
information so consumers can rely on a stable contract while implementation
internals evolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Contract version for this config shape. Bump only when contract keys/types change.
CONFIG_CONTRACT_VERSION: Final[int] = 1

# Keep this tuple append-only for future compatibility.
# Existing module names must not be renamed or removed.
ENABLED_MODULES: Final[tuple[str, ...]] = (
    "spaces",
    "messages",
    "memberships",
    "attachments",
)


@dataclass(frozen=True)
class FeatureToggles:
    """Runtime toggles for optional behavior.

    These are intentionally explicit booleans to avoid invalid intermediate
    states and to preserve a predictable consumer contract.
    """

    group_members: bool = True
    report_enabled: bool = True
    cache_enabled: bool = True

    def as_dict(self) -> dict[str, bool]:
        """Return a stable dictionary representation for serializers."""

        return {
            "group_members": self.group_members,
            "report_enabled": self.report_enabled,
            "cache_enabled": self.cache_enabled,
        }


@dataclass(frozen=True)
class SchemaVersions:
    """Schema versions exposed to consumers.

    Separate version numbers allow exports and cache to evolve independently.
    """

    export: int = 1
    cache: int = 1

    def as_dict(self) -> dict[str, int]:
        """Return a stable dictionary representation for serializers."""

        return {
            "export": self.export,
            "cache": self.cache,
        }


@dataclass(frozen=True)
class SpaceOdTConfig:
    """Top-level immutable config contract for SpaceOdT."""

    contract_version: int = CONFIG_CONTRACT_VERSION
    enabled_modules: tuple[str, ...] = ENABLED_MODULES
    toggles: FeatureToggles = FeatureToggles()
    schema_versions: SchemaVersions = SchemaVersions()

    def as_dict(self) -> dict[str, object]:
        """Return a stable mapping used by downstream consumers.

        Keys are part of the public contract and should be treated as append-only.
        """

        return {
            "contract_version": self.contract_version,
            "enabled_modules": list(self.enabled_modules),
            "toggles": self.toggles.as_dict(),
            "schema_versions": self.schema_versions.as_dict(),
        }


DEFAULT_CONFIG: Final[SpaceOdTConfig] = SpaceOdTConfig()
