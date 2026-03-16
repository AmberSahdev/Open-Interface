import os
import sys
import types
from unittest.mock import Mock, patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

if 'pyautogui' not in sys.modules:
    fake_pyautogui = types.ModuleType('pyautogui')
    setattr(fake_pyautogui, 'size', lambda: (1000, 500))
    setattr(fake_pyautogui, 'press', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'click', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'doubleClick', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'tripleClick', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'moveTo', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'dragTo', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'screenshot', lambda *args, **kwargs: None)
    sys.modules['pyautogui'] = fake_pyautogui

from interpreter import Interpreter
from verifier import StepVerifier


class FakeQuartzModule:
    kCGMouseButtonLeft = 0
    kCGEventLeftMouseDown = 1
    kCGEventLeftMouseUp = 2
    kCGMouseButtonRight = 3
    kCGEventRightMouseDown = 4
    kCGEventRightMouseUp = 5
    kCGMouseButtonCenter = 6
    kCGEventOtherMouseDown = 7
    kCGEventOtherMouseUp = 8
    kCGMouseEventClickState = 9
    kCGHIDEventTap = 10

    def __init__(self):
        self.events = []

    def CGEventCreateMouseEvent(self, _source, event_type, point, button):
        event = {
            'event_type': event_type,
            'point': point,
            'button': button,
            'fields': {},
        }
        self.events.append(event)
        return event

    def CGEventSetIntegerValueField(self, event, field, value):
        event['fields'][field] = value

    def CGEventPost(self, _tap, event):
        event['posted'] = True


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_macos_doubleclick_events() -> None:
    interpreter = Interpreter(Mock(), Mock())
    interpreter.input_adapter.platform_name = 'macos'
    fake_quartz = FakeQuartzModule()

    with patch('platform_support.input_adapter.Quartz', fake_quartz), \
         patch('interpreter.pyautogui.size', return_value=(1000, 500)), \
         patch('interpreter.pyautogui.press'), \
         patch('interpreter.pyautogui.moveTo') as move_to_mock, \
         patch('interpreter.sleep'):
        executed = interpreter.execute_function(
            'doubleClick',
            {'x_percent': 50, 'y_percent': 25, 'button': 'left', 'interval': 0.2},
        )

    assert_true(executed['x'] == 499 and executed['y'] == 124, 'doubleClick should resolve to logical pixels.')
    move_to_mock.assert_called_once_with(x=499, y=124, duration=0.0)
    assert_true(len(fake_quartz.events) == 4, 'doubleClick should emit 4 mouse events on macOS.')
    click_states = [event['fields'][fake_quartz.kCGMouseEventClickState] for event in fake_quartz.events]
    assert_true(click_states == [1, 1, 2, 2], 'doubleClick should set click-state progression [1, 1, 2, 2].')
    print(f'macOS doubleClick emitted click states: {click_states}')


def verify_doubleclick_verifier_gate() -> None:
    verifier = StepVerifier()
    result = verifier._classify_visual_step(
        function_name='doubleClick',
        expected_outcome='open the desktop file',
        global_change_ratio=0.0002,
        local_change_ratio=0.02,
    )

    assert_true(result['status'] == 'uncertain', 'doubleClick local-only change should not be marked passed.')
    assert_true(
        result['reason'] == 'selection_only_possible',
        'doubleClick selection-only case should produce selection_only_possible reason.',
    )
    print(f"doubleClick verifier result: status={result['status']} reason={result['reason']}")


def main() -> None:
    verify_macos_doubleclick_events()
    verify_doubleclick_verifier_gate()
    print('macOS doubleClick verification passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'macOS doubleClick verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
