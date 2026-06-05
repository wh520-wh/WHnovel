import os
import subprocess
from unittest.mock import MagicMock

from app.shutdown_worker import (
    _find_port_processes,
    _kill_process_tree,
    _stop_port,
)


def test_find_port_extracts_pids_from_netstat_output(monkeypatch):
    """netstat output with one LISTENING entry on port 8000."""
    fake_output = (
        "  TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       12345\r\n"
        "  TCP    127.0.0.1:5173         0.0.0.0:0              LISTENING       67890\r\n"
        "  TCP    192.168.1.1:8000       10.0.0.5:443            ESTABLISHED     99999\r\n"
    )

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.stdout = fake_output
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)

    pids = _find_port_processes(8000)
    assert pids == [12345]


def test_find_port_returns_empty_on_netstat_failure(monkeypatch):
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=Exception("boom")))
    assert _find_port_processes(8000) == []


def test_find_port_ignores_non_digit_pid(monkeypatch):
    fake_output = "  TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       abcde\r\n"

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.stdout = fake_output
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _find_port_processes(8000) == []


def test_kill_process_tree_calls_taskkill_with_correct_args(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = _kill_process_tree(12345)

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "taskkill"
    assert "/PID" in args
    assert "12345" in args
    assert "/T" in args
    assert "/F" in args
    assert result is True


def test_kill_process_tree_returns_false_on_failure(monkeypatch):
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=Exception("boom")))
    assert _kill_process_tree(12345) is False


def test_stop_port_kills_processes_from_pid_file(tmp_path, monkeypatch):
    pid_file = tmp_path / "app.pid"
    pid_file.write_text("11111\n22222\n")

    monkeypatch.setattr(
        "app.shutdown_worker._find_port_processes",
        lambda port: [],
    )
    mock_kill = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.shutdown_worker._kill_process_tree",
        mock_kill,
    )

    _stop_port(8000, pid_file, max_passes=1)

    assert mock_kill.call_count == 2
    killed_pids = {call.args[0] for call in mock_kill.call_args_list}
    assert killed_pids == {11111, 22222}


def test_stop_port_stops_when_no_targets(tmp_path, monkeypatch):
    pid_file = tmp_path / "app.pid"
    pid_file.write_text("")

    monkeypatch.setattr(
        "app.shutdown_worker._find_port_processes",
        lambda port: [],
    )
    mock_kill = MagicMock()
    monkeypatch.setattr(
        "app.shutdown_worker._kill_process_tree",
        mock_kill,
    )

    _stop_port(8000, pid_file, max_passes=3)

    mock_kill.assert_not_called()


def test_stop_port_excludes_own_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "app.pid"
    pid_file.write_text(f"{os.getpid()}\n")

    monkeypatch.setattr(
        "app.shutdown_worker._find_port_processes",
        lambda port: [],
    )
    mock_kill = MagicMock()
    monkeypatch.setattr(
        "app.shutdown_worker._kill_process_tree",
        mock_kill,
    )

    _stop_port(8000, pid_file, max_passes=1)

    mock_kill.assert_not_called()


def test_stop_port_merges_pid_file_and_port_scan(tmp_path, monkeypatch):
    pid_file = tmp_path / "app.pid"
    pid_file.write_text("11111\n")

    monkeypatch.setattr(
        "app.shutdown_worker._find_port_processes",
        lambda port: [22222],
    )
    mock_kill = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.shutdown_worker._kill_process_tree",
        mock_kill,
    )

    _stop_port(8000, pid_file, max_passes=1)

    killed = {call.args[0] for call in mock_kill.call_args_list}
    assert killed == {11111, 22222}
