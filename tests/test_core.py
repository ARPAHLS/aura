"""Core registry and spectrum tests."""

from aura.core.registry import TypeRegistry
from aura.core.spectrum import Spectrum


def test_spectrum_from_manifest_defaults():
    s = Spectrum.from_manifest({})
    assert s.level == "mid"
    assert "audit" in s.services


def test_type_registry_register():
    class FakePlugin:
        type_id = "test.fake"
        version = 1
        role = "brain"

        def validate(self, config): ...
        def bind(self, session, config): ...

    reg = TypeRegistry()
    reg.register(FakePlugin())  # type: ignore[arg-type]
    assert reg.get("test.fake") is not None
    assert "test.fake" in reg.list_types("brain")
