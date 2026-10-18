"""Install/uninstall a per-user macOS LaunchAgent for Claude Bucks.

Run using `pdm run install-agent` or `pdm run uninstall-agent`.
"""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = 'local.claudebucks.monitor'
AGENT_PATH = Path.home() / 'Library' / 'LaunchAgents' / (LABEL + '.plist')
LOG_DIR = Path.home() / 'Library' / 'Logs' / 'ClaudeBucks'
ROOT = Path(__file__).resolve().parent.parent


def launchctl(*args, check=False):
    return subprocess.run(['launchctl', *args], check=check)


def main():
    parser = argparse.ArgumentParser(description='Manage Claude Bucks LaunchAgent')
    parser.add_argument('action', choices=['install', 'uninstall'])
    parser.add_argument('--budget', type=float, default=None)
    parser.add_argument('--interval', type=float, default=30)
    args = parser.parse_args()
    if args.budget is not None and args.budget <= 0:
        parser.error('--budget must be positive')
    if not 0 < args.interval < 90:
        parser.error('--interval must be between 0 and 90 seconds')

    domain = f'gui/{os.getuid()}'
    service = f'{domain}/{LABEL}'
    if args.action == 'uninstall':
        launchctl('bootout', service)
        AGENT_PATH.unlink(missing_ok=True)
        print('Claude Bucks LaunchAgent removed')
        return

    # This command runs via PDM. Its interpreter is the project-managed Python
    # environment with pyserial available, no dependency on PATH at login.
    python = str(Path(sys.executable).resolve())
    if not Path(python).exists():
        parser.error(f'Python interpreter does not exist: {python}')
    arguments = [python, '-u', str(ROOT / 'mac' / 'main.py'),
                 '--interval', str(args.interval)]
    if args.budget is not None:
        arguments += ['--budget', str(args.budget)]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        'Label': LABEL,
        'ProgramArguments': arguments,
        'WorkingDirectory': str(ROOT),
        'RunAtLoad': True,
        'KeepAlive': True,
        'ThrottleInterval': 10,
        'StandardOutPath': str(LOG_DIR / 'stdout.log'),
        'StandardErrorPath': str(LOG_DIR / 'stderr.log'),
    }
    # Remove prior job first, to support repeatable installation.
    launchctl('bootout', service)
    with AGENT_PATH.open('wb') as f:
        plistlib.dump(plist, f)
    launchctl('bootstrap', domain, str(AGENT_PATH), check=True)
    print('Claude Bucks installed and started')
    print('Agent:', AGENT_PATH)
    print('Logs:', LOG_DIR)
    print('To stop permanently: pdm run uninstall-agent')


if __name__ == '__main__':
    main()
