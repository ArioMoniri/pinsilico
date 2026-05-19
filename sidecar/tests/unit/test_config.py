"""Unit tests for SidecarConfig.

The config object is the only thing the Tauri shell reads via stdout
(``PINSILICO_HOST=…``, ``PINSILICO_PORT=…``), so its invariants — loopback
binding only, valid port range, env-override semantics — are locked here
before Phase 1 layers auth + log level on top.
"""

from __future__ import annotations

import pytest
from pinsilico import __version__
from pinsilico.config import SidecarConfig


class TestSidecarConfigDefaults:
    def test_default_host_is_loopback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PINSILICO_HOST", raising=False)
        cfg = SidecarConfig()
        assert cfg.host == "127.0.0.1"

    def test_default_port_is_ephemeral_sentinel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PINSILICO_PORT", raising=False)
        cfg = SidecarConfig()
        assert cfg.port == 0

    def test_version_matches_package_version(self) -> None:
        assert SidecarConfig().version == __version__

    def test_reload_defaults_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PINSILICO_RELOAD", raising=False)
        assert SidecarConfig().reload is False


class TestSidecarConfigEnvOverrides:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1", True),
            ("true", True),
            ("YES", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("", False),
            ("nonsense", False),
        ],
    )
    def test_reload_env_truthy_values(
        self, monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
    ) -> None:
        monkeypatch.setenv("PINSILICO_RELOAD", raw)
        assert SidecarConfig().reload is expected

    def test_port_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PINSILICO_PORT", "31337")
        assert SidecarConfig().port == 31337

    def test_host_env_override_localhost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PINSILICO_HOST", "localhost")
        assert SidecarConfig().host == "localhost"


class TestSidecarConfigValidation:
    @pytest.mark.parametrize(
        "bad_host",
        [
            "0.0.0.0",  # noqa: S104 - tested precisely because it's forbidden
            "192.168.1.10",
            "example.com",
            "",
        ],
    )
    def test_non_loopback_host_rejected(self, bad_host: str) -> None:
        with pytest.raises(ValueError, match="loopback"):
            SidecarConfig(host=bad_host)

    @pytest.mark.parametrize("bad_port", [-1, 65536, 100_000])
    def test_out_of_range_port_rejected(self, bad_port: int) -> None:
        with pytest.raises(ValueError, match="port out of range"):
            SidecarConfig(port=bad_port)

    def test_zero_port_accepted(self) -> None:
        SidecarConfig(port=0)  # ephemeral sentinel — must not raise

    def test_max_valid_port_accepted(self) -> None:
        SidecarConfig(port=65535)

    def test_config_is_frozen(self) -> None:
        cfg = SidecarConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.host = "example.com"  # type: ignore[misc]  # frozen dataclass
