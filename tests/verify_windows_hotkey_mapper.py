import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_DIR = os.path.join(ROOT_DIR, 'app')

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


from platform_support.hotkey_mapper import HotkeyMapper


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_windows_semantic_shortcuts() -> None:
    mapper = HotkeyMapper('windows')
    assert_true(mapper.get_paste_keys() == ('ctrl', 'v'), 'Windows paste should use ctrl+v.')
    assert_true(mapper.get_copy_keys() == ('ctrl', 'c'), 'Windows copy should use ctrl+c.')
    assert_true(mapper.get_select_all_keys() == ('ctrl', 'a'), 'Windows select all should use ctrl+a.')


def verify_windows_command_and_option_mapping() -> None:
    mapper = HotkeyMapper('windows')
    assert_true(
        mapper.normalize_hotkey_keys(['command', 'v']) == ['ctrl', 'v'],
        'Windows hotkey mapping should translate command+v into ctrl+v.',
    )
    assert_true(
        mapper.normalize_hotkey_keys(['option', 'tab']) == ['alt', 'tab'],
        'Windows hotkey mapping should translate option into alt.',
    )
    assert_true(
        mapper.normalize_key_name('command', for_hotkey=False) == 'win',
        'Standalone command key should map to win on Windows.',
    )


def main() -> None:
    verify_windows_semantic_shortcuts()
    verify_windows_command_and_option_mapping()
    print('windows hotkey mapper verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'windows hotkey mapper verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
