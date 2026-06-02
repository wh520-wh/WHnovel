"""Shutdown worker — spawned as a detached process by the admin API.

Reads pid files and scans ports to find backend/frontend processes,
kills their process trees, and cleans up pid files.

Designed to survive the backend's own termination (it runs in a separate
process, not a child thread).
"""
import os
import sys
import time
import subprocess
from pathlib import Path


def _find_port_processes(port: int) -> list[int]:
    """Find PIDs listening on the given TCP port using netstat."""
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True, text=True, timeout=5,
        )
        pids: list[int] = []
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line.strip():
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    pid = int(parts[-1])
                    if pid > 0:
                        pids.append(pid)
        return pids
    except Exception:
        return []


def _kill_process_tree(pid: int) -> bool:
    """Kill a process and all its children."""
    try:
        subprocess.run(
            ['taskkill', '/PID', str(pid), '/T', '/F'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return True
    except Exception:
        return False


def _stop_port(port: int, pid_file: Path, max_passes: int = 6) -> None:
    """Repeatedly find and kill processes on a port until none remain."""
    for _ in range(max_passes):
        targets: set[int] = set()

        # Read PIDs from pid file
        try:
            text = pid_file.read_text(encoding='utf-8').strip()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.isdigit():
                    targets.add(int(stripped))
        except (FileNotFoundError, ValueError, OSError):
            pass

        # Scan port for listening processes
        targets.update(_find_port_processes(port))

        # Never kill our own process
        targets.discard(0)
        targets.discard(os.getpid())

        if not targets:
            return

        for pid in targets:
            _kill_process_tree(pid)

        time.sleep(0.45)


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(1)

    project_root = Path(sys.argv[1])
    backend_delay_ms = int(sys.argv[2])
    frontend_delay_ms = int(sys.argv[3])

    # Phase 1: wait for HTTP response to be delivered, then kill backend
    time.sleep(backend_delay_ms / 1000)
    _stop_port(8000, project_root / 'backend' / 'app.pid')

    # Phase 2: wait, then kill frontend
    remaining_ms = max(frontend_delay_ms - backend_delay_ms, 400)
    time.sleep(remaining_ms / 1000)
    _stop_port(5173, project_root / 'frontend' / 'app.pid')

    # Clean up pid files
    for pid_file in [
        project_root / 'backend' / 'app.pid',
        project_root / 'frontend' / 'app.pid',
    ]:
        try:
            pid_file.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == '__main__':
    main()
