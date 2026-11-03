"""Start or stop the local Compose stack with automatic Podman discovery."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(action, check=False):
    env = os.environ.copy()
    runtime = shutil.which('podman')
    if not runtime and os.name == 'nt':
        candidates = [
            Path(env.get('LOCALAPPDATA', '')) / 'Programs/Podman/podman.exe',
            Path(env.get('PROGRAMFILES', 'C:/Program Files')) / 'RedHat/Podman/podman.exe',
            Path(env.get('PROGRAMFILES', 'C:/Program Files')) / 'Podman/podman.exe',
        ]
        runtime = next((str(path) for path in candidates if path.is_file()), None)
    if not runtime:
        raise RuntimeError('Podman not found. Install/configure the Podman engine in Podman Desktop, then retry.')
    env['PATH'] = str(Path(runtime).parent) + os.pathsep + env.get('PATH', '')
    provider = env.get('PODMAN_COMPOSE_PROVIDER')
    if provider:
        resolved = shutil.which(provider, path=env['PATH'])
        if not resolved:
            raise RuntimeError('PODMAN_COMPOSE_PROVIDER does not identify an executable.')
        env['PODMAN_COMPOSE_PROVIDER'] = resolved
    else:
        candidates = [
            ROOT / '.venv/Scripts/podman-compose.exe',
            ROOT / '.venv/bin/podman-compose',
        ]
        provider = next((str(path) for path in candidates if path.is_file()), None)
        provider = provider or shutil.which('podman-compose', path=env['PATH']) or shutil.which('docker-compose', path=env['PATH'])
        if not provider:
            raise RuntimeError('Compose provider missing. Install requirements-containers.txt in .venv.')
        env['PODMAN_COMPOSE_PROVIDER'] = provider
    if not (ROOT / '.env').is_file() and not check:
        raise RuntimeError('Missing .env. Follow README setup and run cli.configure_postgres first.')
    args = [runtime, 'compose']
    args += ['version'] if check else (['up', '-d', '--build'] if action == 'start' else ['stop'])
    return args, env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--check', action='store_true', help='Check Compose tooling without changing containers')
    args = parser.parse_args()
    try:
        argv, env = command(args.action, args.check)
        result = subprocess.run(argv, cwd=ROOT, env=env)
        if result.returncode:
            return result.returncode
        if not args.check:
            print('Stack started. Default URL: http://127.0.0.1:8080 (or APP_PORT from .env).' if args.action == 'start'
                  else 'Stack stopped. Containers and persistent volumes were preserved.')
        return 0
    except (RuntimeError, OSError) as exc:
        print(f'Compose error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
