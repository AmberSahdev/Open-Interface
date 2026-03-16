from typing import Any, cast

from models.model import Model
from platform_support.hotkey_mapper import HotkeyMapper
from utils.screen import Screen


class OpenAIComputerUse(Model):
    def __init__(self, model_name, base_url, api_key, context):
        super().__init__(model_name, base_url, api_key, context)
        self.previous_response_id = None
        self.last_call_id = None
        self.pending_safety_checks = []
        self.current_screen_size = (1, 1)
        self.current_frame_context = None
        self.hotkey_mapper = HotkeyMapper()

    def get_instructions_for_objective(
        self,
        original_user_request: str,
        step_num: int = 0,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if step_num == 0:
            self.previous_response_id = None
            self.last_call_id = None
            self.pending_safety_checks = []
            self.current_frame_context = None

        llm_response = self.send_message_to_llm(original_user_request)
        instructions = self.convert_llm_response_to_json_instructions(llm_response)
        instructions = self.normalize_json_instructions(instructions)
        if isinstance(self.current_frame_context, dict):
            instructions['frame_context'] = self.current_frame_context
        return instructions

    def send_message_to_llm(
        self,
        message: str,
        prompt_package: Any = None,
    ) -> Any:
        visual_payload = Screen().get_visual_prompt_payload()
        screenshot_url = f"data:image/png;base64,{visual_payload['annotated_image_base64']}"
        frame_context = visual_payload['frame_context']
        self.current_frame_context = frame_context

        captured_screen = frame_context.get('captured_screen', {})
        screen_width = int(captured_screen.get('width') or 1)
        screen_height = int(captured_screen.get('height') or 1)
        self.current_screen_size = (screen_width, screen_height)
        reasoning_options = self.build_reasoning_request_options(include_summary=True)

        tools = [{
            'type': 'computer_use_preview',
            'display_width': screen_width,
            'display_height': screen_height,
            'environment': 'browser',
        }]

        if self.previous_response_id and self.last_call_id:
            computer_call_output: dict[str, Any] = {
                'type': 'computer_call_output',
                'call_id': self.last_call_id,
                'output': {
                    'type': 'input_image',
                    'image_url': screenshot_url,
                },
            }

            if self.pending_safety_checks:
                computer_call_output['acknowledged_safety_checks'] = self.pending_safety_checks
                self.pending_safety_checks = []

            responses_client = cast(Any, self.client.responses)
            return responses_client.create(
                model=self.model_name,
                previous_response_id=self.previous_response_id,
                tools=tools,
                input=[computer_call_output],
                truncation='auto',
                **reasoning_options,
            )

        responses_client = cast(Any, self.client.responses)
        return responses_client.create(
            model=self.model_name,
            tools=tools,
            input=[{
                'role': 'user',
                'content': [
                    {'type': 'input_text', 'text': message},
                    {'type': 'input_image', 'image_url': screenshot_url},
                ],
            }],
            truncation='auto',
            **reasoning_options,
        )

    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> dict[str, Any]:
        self.previous_response_id = self.read_obj(llm_response, 'id')

        output_items = self.read_obj(llm_response, 'output') or []
        for item in output_items:
            if self.read_obj(item, 'type') != 'computer_call':
                continue

            self.last_call_id = self.read_obj(item, 'call_id')
            self.pending_safety_checks = self.serialize_safety_checks(self.read_obj(item, 'pending_safety_checks') or [])

            action = self.read_obj(item, 'action') or {}
            steps = self.convert_action_to_steps(action)
            return {
                'steps': steps,
                'done': None,
            }

        done_message = (self.read_obj(llm_response, 'output_text') or '').strip()
        if done_message == '':
            done_message = 'Done.'

        self.last_call_id = None
        self.pending_safety_checks = []
        return {
            'steps': [],
            'done': done_message,
        }

    def serialize_safety_checks(self, checks: list[Any]) -> list[dict[str, Any]]:
        serialized = []
        for check in checks:
            check_id = self.read_obj(check, 'id')
            code = self.read_obj(check, 'code')
            message = self.read_obj(check, 'message')
            if check_id and code and message:
                serialized.append({
                    'id': check_id,
                    'code': code,
                    'message': message,
                })
        return serialized

    def convert_action_to_steps(self, action: Any) -> list[dict[str, Any]]:
        action_type = self.read_obj(action, 'type')

        if action_type == 'click':
            coords = self.coordinates_to_percent(
                self.read_obj(action, 'x'),
                self.read_obj(action, 'y'),
            )
            if coords is None:
                return []
            return [{
                'function': 'click',
                'parameters': {
                    'x_percent': coords['x_percent'],
                    'y_percent': coords['y_percent'],
                    'button': self.read_obj(action, 'button') or 'left',
                    'clicks': 1,
                },
            }]

        if action_type == 'double_click':
            coords = self.coordinates_to_percent(
                self.read_obj(action, 'x'),
                self.read_obj(action, 'y'),
            )
            if coords is None:
                return []
            return [{
                'function': 'click',
                'parameters': {
                    'x_percent': coords['x_percent'],
                    'y_percent': coords['y_percent'],
                    'button': 'left',
                    'clicks': 2,
                },
            }]

        if action_type == 'move':
            coords = self.coordinates_to_percent(
                self.read_obj(action, 'x'),
                self.read_obj(action, 'y'),
            )
            if coords is None:
                return []
            return [{
                'function': 'moveTo',
                'parameters': {
                    'x_percent': coords['x_percent'],
                    'y_percent': coords['y_percent'],
                },
            }]

        if action_type == 'scroll':
            scroll_y = self.read_obj(action, 'scroll_y') or 0
            return [{
                'function': 'scroll',
                'parameters': {
                    # Browser coordinate systems usually use positive Y for scrolling down;
                    # pyautogui.scroll uses negative values for down.
                    'clicks': int(-scroll_y),
                },
            }]

        if action_type == 'type':
            return [{
                'function': 'write',
                'parameters': {
                    'string': self.read_obj(action, 'text') or '',
                    'interval': 0.03,
                },
            }]

        if action_type == 'wait':
            return [{
                'function': 'sleep',
                'parameters': {
                    'secs': 1,
                },
            }]

        if action_type == 'keypress':
            keys = self.read_obj(action, 'keys') or []
            normalized_keys = [self.normalize_key_name(key) for key in keys if key]
            if len(normalized_keys) == 0:
                return []
            if len(normalized_keys) == 1:
                return [{
                    'function': 'press',
                    'parameters': {
                        'key': normalized_keys[0],
                    },
                }]
            return [{
                'function': 'hotkey',
                'parameters': {
                    'keys': normalized_keys,
                },
            }]

        if action_type == 'drag':
            path = self.read_obj(action, 'path') or []
            if len(path) < 2:
                return []

            start_x = self.read_obj(path[0], 0)
            start_y = self.read_obj(path[0], 1)
            end_x = self.read_obj(path[-1], 0)
            end_y = self.read_obj(path[-1], 1)

            start_coords = self.coordinates_to_percent(start_x, start_y)
            end_coords = self.coordinates_to_percent(end_x, end_y)
            if start_coords is None or end_coords is None:
                return []

            return [
                {
                    'function': 'moveTo',
                    'parameters': {
                        'x_percent': start_coords['x_percent'],
                        'y_percent': start_coords['y_percent'],
                    },
                },
                {
                    'function': 'dragTo',
                    'parameters': {
                        'x_percent': end_coords['x_percent'],
                        'y_percent': end_coords['y_percent'],
                        'duration': 0.2,
                        'button': 'left',
                    },
                },
            ]

        if action_type == 'screenshot':
            return []

        print(f'Unsupported computer_use action type: {action_type}')
        return []

    def coordinates_to_percent(self, x: Any, y: Any) -> Any:
        if x is None or y is None:
            return None

        screen_width, screen_height = self.current_screen_size
        if isinstance(self.current_frame_context, dict):
            captured_screen = self.current_frame_context.get('captured_screen')
            if isinstance(captured_screen, dict):
                captured_width = int(captured_screen.get('width') or 0)
                captured_height = int(captured_screen.get('height') or 0)
                if captured_width > 0 and captured_height > 0:
                    screen_width = captured_width
                    screen_height = captured_height

        if screen_width <= 0 or screen_height <= 0:
            screen_width, screen_height = Screen().get_size()

        x_percent = max(0.0, min(1.0, float(x) / float(max(1, screen_width))))
        y_percent = max(0.0, min(1.0, float(y) / float(max(1, screen_height))))
        return {
            'x_percent': round(x_percent * 100.0, 4),
            'y_percent': round(y_percent * 100.0, 4),
        }

    @staticmethod
    def read_obj(obj: Any, key: Any, default=None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        if isinstance(obj, (list, tuple)) and isinstance(key, int):
            if 0 <= key < len(obj):
                return obj[key]
            return default
        return getattr(obj, key, default)

    def normalize_key_name(self, key: str) -> str:
        return self.hotkey_mapper.normalize_key_name(key, for_hotkey=True)

    def cleanup(self):
        self.previous_response_id = None
        self.last_call_id = None
        self.pending_safety_checks = []
        self.current_frame_context = None
