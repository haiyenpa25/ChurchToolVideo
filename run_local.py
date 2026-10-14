"""Shared Windows/macOS bootstrap. Creates only a local virtual environment."""
import argparse
from pathlib import Path
import platform
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def environment_python(root, system):
    relative = Path('Scripts/python.exe') if system == 'Windows' else Path('bin/python')
    environment = root / '.venv'
    if environment.exists() and not (environment / relative).is_file():
        # A copied environment from another OS is not portable. Keep it intact.
        environment = root / ('.venv-windows' if system == 'Windows' else '.venv-macos')
    return environment, environment / relative


def main():
    parser = argparse.ArgumentParser(description='Start ChurchToolVideo on Windows or macOS.')
    parser.add_argument('--check', action='store_true', help='Check the installation without starting a server.')
    parser.add_argument('--install', action='store_true', help='Install/update dependencies in the local environment.')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        parser.error('Use Python 3.11 or 3.12 for the current media dependencies.')
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    environment, python = environment_python(ROOT, platform.system())
    created = not python.is_file()
    if created:
        if args.check:
            print('No local environment yet. Run the launcher once to install dependencies.')
            return 1
        if environment.exists():
            print(f'Incomplete environment: {environment}. Rename it, then launch again.')
            return 1
        print(f'Creating environment: {environment}', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    if created or args.install:
        subprocess.run([str(python), '-m', 'ensurepip', '--upgrade'], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT/'requirements.txt')], check=True)
    check = subprocess.run([str(python), str(ROOT/'scripts/check_environment.py')], cwd=ROOT)
    if check.returncode:
        print('Check failed. Install missing prerequisites; use --install for Python dependencies.')
        return check.returncode
    if args.check:
        return 0
    command = [str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
               '--port', str(args.port), '--workers', '1']
    if (ROOT/'.env').is_file():
        command.extend(['--env-file', str(ROOT/'.env')])
    print(f'Open http://localhost:{args.port} ; press Ctrl+C to stop.', flush=True)
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f'Setup failed (exit {error.returncode}). Check your network and installed Python version.')
        raise SystemExit(error.returncode)
    except KeyboardInterrupt:
        raise SystemExit(0)
