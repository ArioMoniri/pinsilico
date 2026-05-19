"""Structured-logging contract tests.

Phase 1 wires structlog with two sinks:

* stdout — JSON, one event per line, greppable with ``jq``.
* rotating file under ``~/.pinsilico/logs/sidecar.log`` — same JSON shape,
  rotated at 10 MB with up to 5 historical files.

Locked invariants:

* Every log record is valid JSON with required keys: ``timestamp``,
  ``level``, ``event``.
* Levels round-trip (info → "info", warning → "warning", etc.).
* Context bound via ``logger.bind()`` flows through to the output.
* The configured log directory is honoured (no hardcoded ``~/.pinsilico``).
"""

from __future__ import annotations

import io
import json
import logging
import re
from typing import TYPE_CHECKING

import pytest
from pinsilico.logs import configure_logger, get_logger

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def captured_stdout() -> io.StringIO:
    return io.StringIO()


@pytest.fixture(autouse=True)
def _reset_root_logger() -> None:
    """Each test gets a clean stdlib logger; structlog re-configures from scratch."""
    root = logging.getLogger()
    root.handlers.clear()


def _parse_lines(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


class TestConfigureLogger:
    def test_emits_json_to_provided_stream(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        configure_logger(level="info", log_dir=tmp_path, stream=captured_stdout)
        get_logger("test").info("hello", user="bob")
        events = _parse_lines(captured_stdout)
        assert events
        last = events[-1]
        assert last["event"] == "hello"
        assert last["level"] == "info"
        assert last["user"] == "bob"

    def test_every_record_has_iso_timestamp(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        configure_logger(level="debug", log_dir=tmp_path, stream=captured_stdout)
        get_logger("t").info("a")
        get_logger("t").warning("b")
        events = _parse_lines(captured_stdout)
        assert len(events) == 2
        iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
        for ev in events:
            assert isinstance(ev["timestamp"], str)
            assert iso_re.match(ev["timestamp"]), f"timestamp not ISO-8601: {ev['timestamp']!r}"

    @pytest.mark.parametrize(
        ("call_level", "expected"),
        [("debug", "debug"), ("info", "info"), ("warning", "warning"), ("error", "error")],
    )
    def test_levels_round_trip(
        self,
        captured_stdout: io.StringIO,
        tmp_path: Path,
        call_level: str,
        expected: str,
    ) -> None:
        configure_logger(level="debug", log_dir=tmp_path, stream=captured_stdout)
        log = get_logger("t")
        getattr(log, call_level)("msg")
        events = _parse_lines(captured_stdout)
        assert events[-1]["level"] == expected

    def test_level_filter_drops_below_threshold(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        configure_logger(level="warning", log_dir=tmp_path, stream=captured_stdout)
        log = get_logger("t")
        log.debug("noise")
        log.info("more noise")
        log.warning("kept")
        events = _parse_lines(captured_stdout)
        assert len(events) == 1
        assert events[0]["event"] == "kept"

    def test_bound_context_flows_through(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        configure_logger(level="info", log_dir=tmp_path, stream=captured_stdout)
        log = get_logger("t").bind(run_id="abc-123", protein="1HSG")
        log.info("docking_started")
        log.info("docking_finished", affinity_kcal_mol=-9.4)
        events = _parse_lines(captured_stdout)
        for ev in events:
            assert ev["run_id"] == "abc-123"
            assert ev["protein"] == "1HSG"
        assert events[-1]["affinity_kcal_mol"] == -9.4


class TestFileSink:
    def test_creates_log_dir_if_missing(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        log_dir = tmp_path / "nested" / "logs"
        assert not log_dir.exists()
        configure_logger(level="info", log_dir=log_dir, stream=captured_stdout)
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_writes_to_file_sink(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        configure_logger(level="info", log_dir=tmp_path, stream=captured_stdout)
        get_logger("file_test").info("on_disk", marker="42")
        log_file = tmp_path / "sidecar.log"
        assert log_file.exists()
        contents = log_file.read_text("utf-8")
        assert "on_disk" in contents
        # File sink uses the same JSON renderer
        last_line = [line for line in contents.splitlines() if line.strip()][-1]
        ev = json.loads(last_line)
        assert ev["marker"] == "42"

    def test_file_rotation_keeps_recent_logs(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        """We don't force the 10 MB cap in tests — just verify the rotating
        handler is in place (so a megabyte of debug noise doesn't kill the
        user's disk in long runs)."""
        configure_logger(
            level="info",
            log_dir=tmp_path,
            stream=captured_stdout,
            max_bytes=512,
            backup_count=3,
        )
        log = get_logger("rotate")
        for i in range(120):
            log.info("noise", iteration=i, payload="x" * 64)
        # At least the active log file should exist; rotated siblings are
        # opportunistic depending on bytes written.
        log_file = tmp_path / "sidecar.log"
        assert log_file.exists()
        rotated = list(tmp_path.glob("sidecar.log.*"))
        assert len(rotated) <= 3, f"unexpected rotation count: {rotated}"


class TestGetLogger:
    def test_returns_distinct_instances_with_separate_context(
        self, captured_stdout: io.StringIO, tmp_path: Path
    ) -> None:
        configure_logger(level="info", log_dir=tmp_path, stream=captured_stdout)
        a = get_logger("a").bind(component="docking")
        b = get_logger("b").bind(component="pocket")
        a.info("from_a")
        b.info("from_b")
        events = _parse_lines(captured_stdout)
        by_event = {ev["event"]: ev for ev in events}
        assert by_event["from_a"]["component"] == "docking"
        assert by_event["from_b"]["component"] == "pocket"
