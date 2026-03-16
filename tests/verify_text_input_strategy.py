import os
import sys
import types
from unittest.mock import Mock, call, patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

if 'pyautogui' not in sys.modules:
    fake_pyautogui = types.ModuleType('pyautogui')
    setattr(fake_pyautogui, 'size', lambda: (1000, 500))
    setattr(fake_pyautogui, 'press', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'write', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'hotkey', lambda *args, **kwargs: None)
    sys.modules['pyautogui'] = fake_pyautogui

from interpreter import Interpreter


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_non_ascii_text_uses_clipboard_paste() -> None:
    interpreter = Interpreter(Mock(), Mock())

    with patch('interpreter.pyautogui.press'), \
         patch('interpreter.pyautogui.write') as write_mock, \
         patch('interpreter.pyautogui.hotkey') as hotkey_mock, \
         patch.object(interpreter, '_read_clipboard_text', return_value='original clipboard') as paste_mock, \
         patch.object(interpreter, '_copy_text_to_clipboard') as copy_mock, \
         patch('interpreter.sleep'):
        interpreter.execute_function(
            'write',
            {'string': '佛山大学计算机研究生官网 招生动态', 'interval': 0.03},
        )

    expected_paste_keys = interpreter._get_paste_hotkey_keys()
    paste_mock.assert_called_once_with()
    write_mock.assert_not_called()
    hotkey_mock.assert_called_once_with(*expected_paste_keys)
    assert_true(
        copy_mock.call_args_list == [
            call('佛山大学计算机研究生官网 招生动态'),
            call('original clipboard'),
        ],
        'non-ASCII text should copy target text and then restore clipboard contents',
    )
    print('non-ASCII text uses clipboard paste strategy')


def verify_ascii_text_keeps_direct_write() -> None:
    interpreter = Interpreter(Mock(), Mock())

    with patch('interpreter.pyautogui.press'), \
         patch('interpreter.pyautogui.write') as write_mock, \
         patch('interpreter.pyautogui.hotkey') as hotkey_mock, \
         patch.object(interpreter, '_copy_text_to_clipboard') as copy_mock, \
         patch.object(interpreter, '_read_clipboard_text') as paste_mock:
        interpreter.execute_function(
            'write',
            {'string': 'open interface search', 'interval': 0.03},
        )

    write_mock.assert_called_once_with('open interface search', interval=0.03)
    hotkey_mock.assert_not_called()
    copy_mock.assert_not_called()
    paste_mock.assert_not_called()
    print('ASCII text keeps direct write strategy')


def verify_clipboard_read_failure_is_explicit() -> None:
    interpreter = Interpreter(Mock(), Mock())

    with patch('interpreter.pyautogui.press'), \
         patch.object(interpreter, '_read_clipboard_text', side_effect=RuntimeError('clipboard unavailable')):
        try:
            interpreter.execute_function('write', {'string': '中文输入'})
        except RuntimeError as exc:
            assert_true(
                'Unable to read clipboard before text paste.' in str(exc),
                'clipboard read failures should raise contextual RuntimeError',
            )
            print('clipboard failure path raises contextual error')
            return

    raise AssertionError('clipboard read failure should not be swallowed')


def main() -> None:
    verify_non_ascii_text_uses_clipboard_paste()
    verify_ascii_text_keeps_direct_write()
    verify_clipboard_read_failure_is_explicit()
    print('text input strategy verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'text input strategy verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
