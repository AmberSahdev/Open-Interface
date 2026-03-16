import json
import sys
from multiprocessing import Queue
from time import sleep
from typing import Optional, Any

import pyautogui

try:
    import Quartz
except Exception:
    Quartz = None

from platform_support.clipboard_adapter import ClipboardAdapter
from platform_support.input_adapter import InputAdapter
from session_store import SessionStore


class Interpreter:
    MACOS_MULTI_CLICK_FUNCTIONS = {
        'doubleClick': 2,
        'tripleClick': 3,
    }

    COORDINATE_FUNCTIONS = {
        'click',
        'doubleClick',
        'tripleClick',
        'rightClick',
        'middleClick',
        'mouseDown',
        'mouseUp',
        'move',
        'moveTo',
        'drag',
        'dragTo',
    }

    FUNCTION_ALIASES = {
        'move': 'moveTo',
        'drag': 'dragTo',
    }

    def __init__(self, status_queue: Queue, session_store: SessionStore):
        # MP Queue to put current status of execution in while processes commands.
        # It helps us reflect the current status on the UI.
        self.status_queue = status_queue
        self.session_store = session_store
        self._last_function_name: Optional[str] = None
        self._last_coordinate_resolution: Optional[dict[str, Any]] = None
        self._last_execution_parameters: Optional[dict[str, Any]] = None
        self._last_execution_error_message: Optional[str] = None
        self.input_adapter = InputAdapter()
        self.clipboard_adapter = ClipboardAdapter()

    def process_commands(
        self,
        json_commands: list[dict[str, Any]],
        request_context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Reads a list of JSON commands and runs the corresponding function call as specified in context.txt
        :param json_commands: List of JSON Objects with format as described in context.txt
        :return: True for successful execution, False for exception while interpreting or executing.
        """
        for command in json_commands:
            success = self.process_command(command, request_context)
            if not success:
                return False  # End early and return
        return True

    def process_command(
        self,
        json_command: dict[str, Any],
        request_context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Reads the passed in JSON object and extracts relevant details. Format is specified in context.txt.
        After interpretation, it proceeds to execute the appropriate function call.

        :return: True for successful execution, False for exception while interpreting or executing.
        """
        function_name = json_command['function']
        parameters = json_command.get('parameters', {})
        human_readable_justification = json_command.get('human_readable_justification')
        print(f'Now performing - {function_name} - {parameters} - {human_readable_justification}')

        runtime_status = human_readable_justification or function_name
        self._emit_runtime_status(runtime_status, request_context)

        executed_parameters = parameters
        self._last_function_name = None
        self._last_coordinate_resolution = None
        self._last_execution_parameters = None
        self._last_execution_error_message = None
        try:
            executed_parameters = self.execute_function(function_name, parameters, request_context)
            self._persist_execution_log(
                request_context,
                function_name=function_name,
                parameters=self._build_logged_parameters(executed_parameters),
                justification=human_readable_justification,
                status='succeeded',
                error_message=None,
            )
            return True
        except Exception as e:
            error_message = str(e)
            self._last_execution_error_message = error_message
            print(f'\nError:\nWe are having a problem executing this step - {type(e)} - {e}')
            print(f'This was the json we received from the LLM: {json.dumps(json_command, indent=2)}')
            print(f'This is what we extracted:')
            print(f'\t function_name:{function_name}')
            print(f'\t parameters:{parameters}')

            self._persist_execution_log(
                request_context,
                function_name=function_name,
                parameters=self._build_logged_parameters(
                    self._last_execution_parameters or executed_parameters,
                ),
                justification=human_readable_justification,
                status='failed',
                error_message=error_message,
            )

            return False

    def _persist_execution_log(
        self,
        request_context: Optional[dict[str, Any]],
        function_name: str,
        parameters: dict[str, Any],
        justification: Optional[str],
        status: str,
        error_message: Optional[str],
    ) -> None:
        if request_context is None:
            return

        log_record = self.session_store.append_execution_log(
            session_id=request_context['session_id'],
            message_id=request_context['user_message_id'],
            step_index=request_context['next_step_index'],
            function_name=function_name,
            parameters_json=self._serialize_parameters(parameters),
            justification=justification,
            status=status,
            error_message=error_message,
        )
        self.status_queue.put({
            'type': 'execution_log_persisted',
            'session_id': log_record.get('session_id'),
            'execution_log': log_record,
        })

    def _emit_runtime_status(
        self,
        message: str,
        request_context: Optional[dict[str, Any]],
    ) -> None:
        self.status_queue.put({
            'type': 'runtime_status',
            'message': message,
            'session_id': None if request_context is None else request_context.get('session_id'),
        })

    def _serialize_parameters(self, parameters: dict[str, Any]) -> str:
        try:
            return json.dumps(parameters, ensure_ascii=False)
        except TypeError:
            safe_parameters: dict[str, Any] = {}
            for key, value in parameters.items():
                safe_parameters[key] = str(value)
            return json.dumps(safe_parameters, ensure_ascii=False)

    def execute_function(
        self,
        function_name: str,
        parameters: dict[str, Any],
        request_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
            We are expecting only two types of function calls below
            1. time.sleep() - to wait for web pages, applications, and other things to load.
            2. pyautogui calls to interact with system's mouse and keyboard.
        """
        # Strip to bare name to normalize
        if function_name.startswith('pyautogui.'):
            function_name = function_name.split('.')[-1]

        function_name = self.FUNCTION_ALIASES.get(function_name, function_name)
        self._last_function_name = function_name

        execution_parameters = self._normalize_parameters_for_function(
            function_name=function_name,
            parameters=parameters,
            request_context=request_context,
        )
        self._last_execution_parameters = dict(execution_parameters)
        self.input_adapter.warm_up()

        if function_name == 'sleep':
            seconds_value = execution_parameters.get('secs')
            if seconds_value is not None:
                seconds = float(seconds_value)
                sleep(seconds)
        elif hasattr(pyautogui, function_name):
            if function_name == 'write' and (
                'string' in execution_parameters
                or 'text' in execution_parameters
                or 'message' in execution_parameters
            ):
                string_to_write = (
                    execution_parameters.get('string')
                    or execution_parameters.get('text')
                    or execution_parameters.get('message')
                )
                interval = execution_parameters.get('interval', 0.1)
                self._write_text(str(string_to_write or ''), float(interval))
            else:
                self.input_adapter.execute(function_name, execution_parameters)
        else:
            print(f'No such function {function_name} in our interface\'s interpreter')

        return execution_parameters

    def _write_text(self, text: str, interval: float) -> None:
        if self._should_use_clipboard_paste(text):
            self._paste_text_via_clipboard(text)
            return

        self.input_adapter.write_text(text, interval)

    def _should_use_clipboard_paste(self, text: str) -> bool:
        for character in text:
            if ord(character) > 127:
                return True
        return False

    def _paste_text_via_clipboard(self, text: str) -> None:
        try:
            original_clipboard = self._read_clipboard_text()
        except Exception as exc:
            raise RuntimeError('Unable to read clipboard before text paste.') from exc

        try:
            self._copy_text_to_clipboard(text)
        except Exception as exc:
            raise RuntimeError('Unable to copy target text into clipboard.') from exc

        sleep(0.05)
        self.input_adapter.paste()
        sleep(0.05)

        try:
            self._copy_text_to_clipboard(original_clipboard)
        except Exception as exc:
            print(f'Warning: failed to restore clipboard contents after paste: {exc}')

    def _get_paste_hotkey_keys(self) -> tuple[str, str]:
        return self.input_adapter.hotkey_mapper.get_paste_keys()

    def _read_clipboard_text(self) -> str:
        return self.clipboard_adapter.read_text()

    def _copy_text_to_clipboard(self, text: str) -> None:
        self.clipboard_adapter.write_text(text)

    def _normalize_parameters_for_function(
        self,
        function_name: str,
        parameters: dict[str, Any],
        request_context: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        execution_parameters = dict(parameters)

        if function_name not in self.COORDINATE_FUNCTIONS:
            return execution_parameters

        resolved_coordinates = self._resolve_coordinates_from_parameters(
            execution_parameters,
            request_context,
        )
        if resolved_coordinates is None:
            return execution_parameters

        execution_parameters['x'] = resolved_coordinates[0]
        execution_parameters['y'] = resolved_coordinates[1]
        execution_parameters.pop('x_percent', None)
        execution_parameters.pop('y_percent', None)
        execution_parameters.pop('target_anchor_id', None)
        return execution_parameters

    def _resolve_coordinates_from_parameters(
        self,
        parameters: dict[str, Any],
        request_context: Optional[dict[str, Any]],
    ) -> Optional[tuple[int, int]]:
        anchor_id = parameters.get('target_anchor_id')
        if anchor_id is not None:
            return self._resolve_coordinates_from_anchor(anchor_id, request_context)

        if 'x_percent' in parameters or 'y_percent' in parameters:
            x_percent_value = parameters.get('x_percent')
            y_percent_value = parameters.get('y_percent')
            if x_percent_value is None or y_percent_value is None:
                raise ValueError('Both x_percent and y_percent are required for coordinate actions.')

            x_percent = self._normalize_grid_percent(float(x_percent_value), 'x_percent')
            y_percent = self._normalize_grid_percent(float(y_percent_value), 'y_percent')
            return self._map_percent_to_logical_pixels(
                x_percent=x_percent,
                y_percent=y_percent,
                input_coordinate_type='x_percent/y_percent grid-scale',
                source='percent',
            )

        if 'x' not in parameters or 'y' not in parameters:
            return None

        x_value = float(parameters['x'])
        y_value = float(parameters['y'])

        if 0.0 <= x_value <= 1.0 and 0.0 <= y_value <= 1.0:
            return self._map_percent_to_logical_pixels(
                x_percent=self._clamp_percent(x_value),
                y_percent=self._clamp_percent(y_value),
                input_coordinate_type='normalized x/y',
                source='percent',
            )

        converted = self._resolve_coordinates_from_frame_pixels(x_value, y_value, request_context)
        if converted is not None:
            return converted

        raise ValueError(
            'Absolute x/y coordinates are disabled. '
            'Use x_percent/y_percent or target_anchor_id.',
        )

    def _resolve_coordinates_from_frame_pixels(
        self,
        x_value: float,
        y_value: float,
        request_context: Optional[dict[str, Any]],
    ) -> Optional[tuple[int, int]]:
        if request_context is None:
            return None

        frame_context = request_context.get('frame_context')
        if not isinstance(frame_context, dict):
            return None

        captured_screen = frame_context.get('captured_screen')
        if not isinstance(captured_screen, dict):
            return None

        capture_width = captured_screen.get('width')
        capture_height = captured_screen.get('height')
        if capture_width is None or capture_height is None:
            return None

        capture_width = int(capture_width)
        capture_height = int(capture_height)
        if capture_width <= 0 or capture_height <= 0:
            return None

        x_percent = self._clamp_percent(x_value / float(max(1, capture_width)))
        y_percent = self._clamp_percent(y_value / float(max(1, capture_height)))
        return self._map_percent_to_logical_pixels(
            x_percent=x_percent,
            y_percent=y_percent,
            input_coordinate_type='x/y pixels',
            source='pixel-convert',
            capture_size={
                'width': capture_width,
                'height': capture_height,
            },
        )

    def _resolve_coordinates_from_anchor(
        self,
        anchor_id: Any,
        request_context: Optional[dict[str, Any]],
    ) -> tuple[int, int]:
        anchors = self._get_anchor_definitions(request_context)
        try:
            normalized_anchor_id = int(anchor_id)
        except Exception as exc:
            raise ValueError(f'Invalid target_anchor_id: {anchor_id}') from exc

        selected_anchor: Optional[dict[str, Any]] = None
        for anchor in anchors:
            if int(anchor.get('id', -1)) == normalized_anchor_id:
                selected_anchor = anchor
                break

        if selected_anchor is None:
            raise ValueError(f'Anchor id {normalized_anchor_id} not found in frame context.')

        x_percent = self._clamp_percent(float(selected_anchor['x_percent']))
        y_percent = self._clamp_percent(float(selected_anchor['y_percent']))
        return self._map_percent_to_logical_pixels(
            x_percent=x_percent,
            y_percent=y_percent,
            input_coordinate_type='target_anchor_id',
            source='anchor',
            anchor_id=normalized_anchor_id,
        )

    def _get_anchor_definitions(
        self,
        request_context: Optional[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if request_context is None:
            raise ValueError('Missing request context for anchor-based action.')

        frame_context = request_context.get('frame_context')
        if not isinstance(frame_context, dict):
            raise ValueError('Missing frame context for anchor-based action.')

        anchors = frame_context.get('anchors')
        if not isinstance(anchors, list) or len(anchors) == 0:
            raise ValueError('No anchors available for anchor-based action.')

        return anchors

    def _clamp_percent(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _normalize_grid_percent(self, value: float, parameter_name: str) -> float:
        if value < 0.0 or value > 100.0:
            raise ValueError(f'{parameter_name} must be in the inclusive ruler range [0, 100].')
        return self._clamp_percent(value / 100.0)

    def _map_percent_to_logical_pixels(
        self,
        x_percent: float,
        y_percent: float,
        input_coordinate_type: str,
        source: str,
        anchor_id: Optional[int] = None,
        capture_size: Optional[dict[str, int]] = None,
    ) -> tuple[int, int]:
        screen_width, screen_height = pyautogui.size()
        x = int(x_percent * max(1, screen_width - 1))
        y = int(y_percent * max(1, screen_height - 1))

        self._last_coordinate_resolution = {
            'input_coordinate_type': input_coordinate_type,
            'source': source,
            'x_percent': round(x_percent, 4),
            'y_percent': round(y_percent, 4),
            'logical_screen': {
                'width': screen_width,
                'height': screen_height,
            },
            'resolved_pixels': {
                'x': x,
                'y': y,
            },
        }
        if anchor_id is not None:
            self._last_coordinate_resolution['anchor_id'] = anchor_id
        if capture_size is not None:
            self._last_coordinate_resolution['captured_screen'] = capture_size

        print(
            'Coordinate resolution '
            f"type={input_coordinate_type} source={source} "
            f"percent=({round(x_percent, 4)}, {round(y_percent, 4)}) "
            f"logical=({x}, {y})"
        )
        return x, y

    def _build_logged_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        logged_parameters = dict(parameters)
        if self._last_coordinate_resolution is not None:
            logged_parameters['coordinate_debug'] = dict(self._last_coordinate_resolution)
        return logged_parameters

    def get_last_execution_snapshot(self) -> dict[str, Any]:
        snapshot = {
            'function_name': self._last_function_name,
            'parameters': {},
            'coordinate_resolution': None,
            'error_message': self._last_execution_error_message,
        }
        if self._last_execution_parameters is not None:
            snapshot['parameters'] = dict(self._last_execution_parameters)
        if self._last_coordinate_resolution is not None:
            snapshot['coordinate_resolution'] = dict(self._last_coordinate_resolution)
        return snapshot
