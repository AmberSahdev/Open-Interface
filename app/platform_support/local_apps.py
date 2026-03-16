import os
from pathlib import Path

from platform_support.detector import get_platform_name


def get_installed_apps_sample(limit: int = 24) -> list[str]:
    platform_name = get_platform_name()
    if platform_name == 'macos':
        return _list_macos_apps(limit)
    if platform_name == 'windows':
        return _list_windows_apps(limit)
    if platform_name == 'linux':
        return _list_linux_apps(limit)
    return []


def _list_macos_apps(limit: int) -> list[str]:
    applications_path = Path('/Applications')
    if not applications_path.exists():
        return []

    app_names: list[str] = []
    for item in sorted(applications_path.iterdir()):
        if not item.name.endswith('.app'):
            continue
        app_names.append(item.name)
        if len(app_names) >= limit:
            break
    return app_names


def _list_windows_apps(limit: int) -> list[str]:
    candidate_directories: list[Path] = []
    for env_name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        env_value = str(os.environ.get(env_name) or '').strip()
        if env_value == '':
            continue
        candidate_directories.append(Path(env_value))

    ignored_names = {
        'common files',
        'internet explorer',
        'microsoft',
        'modifiableswindowsapps',
        'windows defender',
        'windows mail',
        'windows media player',
        'windows nt',
        'windows photo viewer',
        'windowsapps',
    }

    app_names: list[str] = []
    seen: set[str] = set()
    for directory in candidate_directories:
        if not directory.exists():
            continue
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except Exception as exc:
            print(f'Warning: failed to inspect Windows app directory {directory}: {exc}')
            continue

        for item in children:
            if not item.is_dir():
                continue
            normalized_name = item.name.strip()
            if normalized_name == '':
                continue
            if normalized_name.lower() in ignored_names:
                continue
            if normalized_name.lower() in seen:
                continue
            seen.add(normalized_name.lower())
            app_names.append(normalized_name)
            if len(app_names) >= limit:
                return app_names

    return app_names


def _list_linux_apps(limit: int) -> list[str]:
    candidate_directories = [
        Path('/usr/share/applications'),
        Path.home() / '.local' / 'share' / 'applications',
    ]

    app_names: list[str] = []
    seen: set[str] = set()
    for directory in candidate_directories:
        if not directory.exists():
            continue
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except Exception as exc:
            print(f'Warning: failed to inspect Linux app directory {directory}: {exc}')
            continue

        for item in children:
            if item.suffix != '.desktop':
                continue
            normalized_name = item.stem.strip()
            if normalized_name == '':
                continue
            if normalized_name.lower() in seen:
                continue
            seen.add(normalized_name.lower())
            app_names.append(normalized_name)
            if len(app_names) >= limit:
                return app_names

    return app_names
