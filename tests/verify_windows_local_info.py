import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_DIR = os.path.join(ROOT_DIR, 'app')

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


from platform_support.local_apps import get_installed_apps_sample


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_windows_program_files_scan() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        program_files = Path(temp_dir) / 'Program Files'
        program_files_x86 = Path(temp_dir) / 'Program Files (x86)'
        local_app_data = Path(temp_dir) / 'LocalAppData'
        for directory in (program_files, program_files_x86, local_app_data):
            directory.mkdir(parents=True, exist_ok=True)

        (program_files / 'Google').mkdir()
        (program_files / 'Notion').mkdir()
        (program_files / 'Common Files').mkdir()
        (program_files_x86 / 'Mozilla Firefox').mkdir()
        (local_app_data / 'Obsidian').mkdir()

        with patch('platform_support.local_apps.get_platform_name', return_value='windows'), patch.dict(
            os.environ,
            {
                'ProgramFiles': str(program_files),
                'ProgramFiles(x86)': str(program_files_x86),
                'LOCALAPPDATA': str(local_app_data),
            },
            clear=False,
        ):
            apps = get_installed_apps_sample(limit=10)

        assert_true('Google' in apps, 'Windows app scan should include Program Files entries.')
        assert_true('Mozilla Firefox' in apps, 'Windows app scan should include Program Files (x86) entries.')
        assert_true('Obsidian' in apps, 'Windows app scan should include LOCALAPPDATA entries.')
        assert_true('Common Files' not in apps, 'Windows app scan should skip Common Files.')


def main() -> None:
    verify_windows_program_files_scan()
    print('windows local info verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'windows local info verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
