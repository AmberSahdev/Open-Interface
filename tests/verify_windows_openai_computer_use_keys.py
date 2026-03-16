import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_DIR = os.path.join(ROOT_DIR, 'app')

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


from models.openai_computer_use import OpenAIComputerUse
from platform_support.hotkey_mapper import HotkeyMapper


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_windows_command_keypress_maps_to_ctrl_hotkey() -> None:
    model = OpenAIComputerUse.__new__(OpenAIComputerUse)
    model.hotkey_mapper = HotkeyMapper('windows')

    steps = model.convert_action_to_steps({
        'type': 'keypress',
        'keys': ['command', 'c'],
    })

    assert_true(len(steps) == 1, 'keypress should produce exactly one step.')
    assert_true(steps[0]['function'] == 'hotkey', 'command+c should remain a hotkey step.')
    assert_true(
        steps[0]['parameters']['keys'] == ['ctrl', 'c'],
        'Windows computer-use key mapping should translate command+c into ctrl+c.',
    )


def main() -> None:
    verify_windows_command_keypress_maps_to_ctrl_hotkey()
    print('windows computer use key mapping verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'windows computer use key mapping verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
