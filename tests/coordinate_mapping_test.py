import json
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

if 'pyautogui' not in sys.modules:
    fake_pyautogui = types.ModuleType('pyautogui')
    setattr(fake_pyautogui, 'size', lambda: (1920, 1080))
    setattr(fake_pyautogui, 'press', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'click', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'doubleClick', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'tripleClick', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'moveTo', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'dragTo', lambda *args, **kwargs: None)
    setattr(fake_pyautogui, 'screenshot', lambda *args, **kwargs: None)
    sys.modules['pyautogui'] = fake_pyautogui

from core import Core
from interpreter import Interpreter
from models.model import Model
from models.openai_computer_use import OpenAIComputerUse
from verifier import StepVerifier


class InterpreterCoordinateMappingTest(unittest.TestCase):
    def setUp(self):
        self.session_store = Mock()
        self.session_store.append_execution_log.return_value = {'session_id': 's1'}
        self.status_queue = Mock()
        self.interpreter = Interpreter(self.status_queue, self.session_store)

    @patch('interpreter.pyautogui.click')
    @patch('interpreter.pyautogui.press')
    @patch('interpreter.pyautogui.size', return_value=(200, 100))
    def test_click_uses_percent_coordinates(self, _size_mock, _press_mock, click_mock):
        params = {'x_percent': 50, 'y_percent': 25, 'button': 'left'}
        executed = self.interpreter.execute_function('click', params)

        self.assertIn('x', executed)
        self.assertIn('y', executed)
        self.assertNotIn('x_percent', executed)
        self.assertNotIn('y_percent', executed)
        click_mock.assert_called_once_with(x=99, y=24, button='left')

    @patch('interpreter.pyautogui.click')
    @patch('interpreter.pyautogui.press')
    @patch('interpreter.pyautogui.size', return_value=(1000, 500))
    def test_click_resolves_anchor_id(self, _size_mock, _press_mock, click_mock):
        params = {'target_anchor_id': 2, 'button': 'left'}
        request_context = {
            'frame_context': {
                'anchors': [
                    {'id': 1, 'x_percent': 0.1, 'y_percent': 0.1},
                    {'id': 2, 'x_percent': 0.4, 'y_percent': 0.8},
                ]
            }
        }

        executed = self.interpreter.execute_function('click', params, request_context=request_context)

        self.assertEqual(executed['x'], 399)
        self.assertEqual(executed['y'], 399)
        self.assertNotIn('target_anchor_id', executed)
        click_mock.assert_called_once_with(x=399, y=399, button='left')

    @patch('interpreter.pyautogui.click')
    @patch('interpreter.pyautogui.press')
    @patch('interpreter.pyautogui.size', return_value=(1000, 500))
    def test_click_prefers_anchor_id_over_percent_coordinates(self, _size_mock, _press_mock, click_mock):
        params = {
            'target_anchor_id': 2,
            'x_percent': 10,
            'y_percent': 10,
            'button': 'left',
        }
        request_context = {
            'frame_context': {
                'anchors': [
                    {'id': 2, 'x_percent': 0.4, 'y_percent': 0.8},
                ]
            }
        }

        executed = self.interpreter.execute_function('click', params, request_context=request_context)

        self.assertEqual(executed['x'], 399)
        self.assertEqual(executed['y'], 399)
        click_mock.assert_called_once_with(x=399, y=399, button='left')

    @patch('interpreter.pyautogui.press')
    def test_click_rejects_absolute_pixels_without_frame_context(self, _press_mock):
        params = {'x': 1500, 'y': 800, 'button': 'left'}

        with self.assertRaises(ValueError):
            self.interpreter.execute_function('click', params)

    @patch('interpreter.pyautogui.click')
    @patch('interpreter.pyautogui.press')
    @patch('interpreter.pyautogui.size', return_value=(200, 100))
    def test_process_command_persists_coordinate_debug_log(self, _size_mock, _press_mock, click_mock):
        request_context = {
            'session_id': 's1',
            'user_message_id': 'm1',
            'next_step_index': 1,
            'frame_context': {
                'anchors': [
                {'id': 3, 'x_percent': 0.5, 'y_percent': 0.4},
                ]
            },
        }

        success = self.interpreter.process_command(
            {
                'function': 'click',
                'parameters': {
                    'target_anchor_id': 3,
                    'button': 'left',
                },
            },
            request_context=request_context,
        )

        self.assertTrue(success)
        click_mock.assert_called_once_with(x=99, y=39, button='left')
        persisted_kwargs = self.session_store.append_execution_log.call_args.kwargs
        persisted_parameters = json.loads(persisted_kwargs['parameters_json'])
        self.assertEqual(persisted_parameters['coordinate_debug']['source'], 'anchor')
        self.assertEqual(persisted_parameters['coordinate_debug']['input_coordinate_type'], 'target_anchor_id')

    @patch('interpreter.pyautogui.moveTo')
    @patch('interpreter.pyautogui.press')
    @patch('interpreter.pyautogui.size', return_value=(1000, 500))
    @patch('interpreter.sleep')
    def test_doubleclick_uses_macos_click_state_events(
        self,
        _sleep_mock,
        _size_mock,
        _press_mock,
        move_to_mock,
    ):
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

        fake_quartz = FakeQuartzModule()
        self.interpreter.input_adapter.platform_name = 'macos'

        with patch('platform_support.input_adapter.Quartz', fake_quartz):
            executed = self.interpreter.execute_function(
                'doubleClick',
                {'x_percent': 50, 'y_percent': 25, 'button': 'left', 'interval': 0.2},
            )

        self.assertEqual(executed['x'], 499)
        self.assertEqual(executed['y'], 124)
        move_to_mock.assert_called_once_with(x=499, y=124, duration=0.0)
        self.assertEqual(len(fake_quartz.events), 4)
        click_states = [event['fields'][fake_quartz.kCGMouseEventClickState] for event in fake_quartz.events]
        self.assertEqual(click_states, [1, 1, 2, 2])


class ModelCoordinateEnrichmentTest(unittest.TestCase):
    def test_model_enriches_absolute_pixels_to_percent(self):
        model = Model.__new__(Model)

        instructions = {
            'steps': [
                {
                    'function': 'click',
                    'parameters': {
                        'x': 1000,
                        'y': 500,
                    },
                }
            ]
        }
        frame_context = {
            'captured_screen': {
                'width': 2000,
                'height': 1000,
            },
            'anchors': [],
        }

        enriched = model.enrich_steps_with_anchor_coordinates(instructions, frame_context)
        params = enriched['steps'][0]['parameters']

        self.assertEqual(params['x_percent'], 50.0)
        self.assertEqual(params['y_percent'], 50.0)

    def test_model_keeps_anchor_id_for_interpreter_resolution(self):
        model = Model.__new__(Model)

        instructions = {
            'steps': [
                {
                    'function': 'click',
                    'parameters': {
                        'target_anchor_id': '7',
                    },
                }
            ]
        }
        frame_context = {
            'anchors': [
                {'id': 7, 'x_percent': 0.25, 'y_percent': 0.75},
            ]
        }

        enriched = model.enrich_steps_with_anchor_coordinates(instructions, frame_context)
        params = enriched['steps'][0]['parameters']

        self.assertEqual(params['target_anchor_id'], 7)
        self.assertNotIn('x_percent', params)
        self.assertNotIn('y_percent', params)


class ComputerUseCoordinateConversionTest(unittest.TestCase):
    def test_convert_action_to_steps_returns_percent_coordinates(self):
        model = OpenAIComputerUse.__new__(OpenAIComputerUse)
        model.current_screen_size = (1920, 1080)
        model.current_frame_context = None

        steps = model.convert_action_to_steps({
            'type': 'click',
            'x': 960,
            'y': 540,
            'button': 'left',
        })

        self.assertEqual(steps[0]['function'], 'click')
        self.assertIn('x_percent', steps[0]['parameters'])
        self.assertIn('y_percent', steps[0]['parameters'])
        self.assertNotIn('x', steps[0]['parameters'])
        self.assertNotIn('y', steps[0]['parameters'])

    def test_coordinates_to_percent_uses_captured_screen_size(self):
        model = OpenAIComputerUse.__new__(OpenAIComputerUse)
        model.current_screen_size = (1000, 500)
        model.current_frame_context = {
            'captured_screen': {
                'width': 2000,
                'height': 1000,
            }
        }

        coords = model.coordinates_to_percent(1000, 500)

        self.assertEqual(coords['x_percent'], 50.0)
        self.assertEqual(coords['y_percent'], 50.0)


class StepVerifierDoubleClickTest(unittest.TestCase):
    def test_doubleclick_local_change_only_is_not_marked_passed(self):
        verifier = StepVerifier()

        result = verifier._classify_visual_step(
            function_name='doubleClick',
            expected_outcome='open the file',
            global_change_ratio=0.0002,
            local_change_ratio=0.02,
        )

        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(result['reason'], 'selection_only_possible')


class CoreFrameContextPropagationTest(unittest.TestCase):
    def test_execute_attaches_frame_context_from_model_response(self):
        core = Core.__new__(Core)
        core.interrupt_execution = False
        core.startup_issue = None
        core.status_queue = Mock()
        core.session_store = Mock()
        core.settings_dict = {}
        core._store_status_message = Mock()
        core._store_assistant_message = Mock()
        core._emit_runtime_status = Mock()
        core.play_ding_on_completion = Mock()
        core.step_verifier = Mock()
        core.llm = Mock()
        core.interpreter = Mock()
        core.step_verifier.verify_step.return_value = {
            'status': 'passed',
            'reason': 'mock_pass',
        }
        core.interpreter.get_last_execution_snapshot.return_value = {
            'function_name': 'click',
            'parameters': {
                'x': 0,
                'y': 0,
            },
            'coordinate_resolution': None,
        }

        request_context = {
            'prompt': 'do something',
            'request_id': 'r1',
            'session_id': 's1',
            'user_message_id': 'm1',
            'next_step_index': 1,
        }
        frame_context = {
            'captured_screen': {
                'width': 2000,
                'height': 1000,
            },
            'anchors': [
                {'id': 1, 'x_percent': 0.4, 'y_percent': 0.2},
            ],
        }
        core.llm.get_instructions_for_objective.return_value = {
            'steps': [
                {
                    'function': 'click',
                    'parameters': {
                        'target_anchor_id': 1,
                    },
                }
            ],
            'done': 'ok',
            'frame_context': frame_context,
        }
        core.interpreter.process_command.return_value = True

        result = core.execute('do something', request_context=request_context)

        self.assertEqual(result, 'ok')
        self.assertEqual(request_context['frame_context'], frame_context)
        core.interpreter.process_command.assert_called_once_with(
            {
                'function': 'click',
                'parameters': {
                    'target_anchor_id': 1,
                },
            },
            request_context,
        )


if __name__ == '__main__':
    unittest.main()
