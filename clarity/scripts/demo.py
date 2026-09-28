#!/usr/bin/env python3
"""Start the synthetic MoneyMoney demo on loopback; no account or API key."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv' / 'bin' / 'python'
URL = 'http://127.0.0.1:5173/?ordinary=1#overview'


def prepare(install: bool) -> None:
    if os.name != 'posix' or sys.version_info[:2] != (3, 11):
        raise RuntimeError('Use Python 3.11 on macOS or Linux. Windows is not yet supported.')
    node, npm = shutil.which('node'), shutil.which('npm')
    if not node or not npm:
        raise RuntimeError('Install Node 22.18 or newer (including npm), then rerun this command.')
    version = tuple(int(x) for x in subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.'))
    if version < (22, 18, 0):
        raise RuntimeError('Node 22.18 or newer is required.')
    for port in (8788, 5173):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as exc:
                raise RuntimeError(f'Port {port} is busy. Stop your other demo first; no existing process was changed.') from exc
    if install:
        print('Installing pinned dependencies into clarity/node_modules and clarity/.venv.', flush=True)
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / '.venv')], check=True)
        subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r', 'requirements.lock.txt'], cwd=ROOT, check=True)
        subprocess.run([npm, 'ci'], cwd=ROOT, check=True)
    if not PYTHON.is_file() or not (ROOT / 'node_modules' / 'vite' / 'bin' / 'vite.js').is_file():
        raise RuntimeError('Dependencies are missing. Run again with --install for the first setup.')


def wait_ready(processes: list[subprocess.Popen], url: str) -> None:
    deadline = time.monotonic() + 45
    # Loopback checks must not be sent through a shell-configured HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if any(proc.poll() is not None for proc in processes):
            raise RuntimeError('A demo process exited. Check the output above, or report the first-run failure.')
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f'Demo did not become ready within 45 seconds: {url}')


def stop(processes: list[subprocess.Popen]) -> None:
    # Each child owns a new process group. Never stop another user's server.
    for proc in reversed(processes):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for proc in reversed(processes):
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Install pinned packages first (requires network).')
    parser.add_argument('--no-browser', action='store_true', help='Print the URL without opening a browser.')
    parser.add_argument('--smoke', action='store_true', help='Check both servers with temporary invented data, then stop.')
    args = parser.parse_args()
    processes: list[subprocess.Popen] = []
    temporary = None
    try:
        prepare(args.install)
        if args.smoke:
            temporary = tempfile.TemporaryDirectory(prefix='moneymoney-demo-')
        data = Path(temporary.name) if temporary else ROOT / '.demo-data'
        data.mkdir(mode=0o700, exist_ok=True)
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / 'backend')
        processes.append(subprocess.Popen([str(PYTHON), 'scripts/private_nsdl_connected_backend.py', '--data-dir', str(data)], cwd=ROOT, env=env, start_new_session=True))
        wait_ready(processes, 'http://127.0.0.1:8788/health')
        processes.append(subprocess.Popen([shutil.which('node'), 'node_modules/vite/bin/vite.js'], cwd=ROOT, start_new_session=True))
        wait_ready(processes, 'http://127.0.0.1:5173/')
        print(f'\nSynthetic demo ready: {URL}\nInvented data only. No real accounts, statements or credentials.\nCtrl-C stops both servers. Local manual records remain in .demo-data.\n', flush=True)
        if args.smoke:
            print('PASS: backend and frontend responded; temporary demo data will be removed.', flush=True)
            return 0
        if not args.no_browser:
            webbrowser.open(URL)
        while all(proc.poll() is None for proc in processes):
            time.sleep(0.3)
        raise RuntimeError('A demo process stopped unexpectedly.')
    except KeyboardInterrupt:
        print('\nStopping this demo.', flush=True)
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Demo setup: {exc}', file=sys.stderr)
        return 1
    finally:
        stop(processes)
        if temporary:
            temporary.cleanup()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    raise SystemExit(main())
