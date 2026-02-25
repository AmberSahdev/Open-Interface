from typing import Any

from models.model import Model
from utils.screen import Screen


class OpenAIComputerUse(Model):
    def __init__(self, model_name, base_url, api_key, context):
        super().__init__(model_name, base_url, api_key, context)
        self.previous_response_id = None
        self.last_call_id = None
        self.pending_safety_checks = []

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        if step_num == 0:
            self.previous_response_id = None
            self.last_call_id = None
            self.pending_safety_checks = []

        llm_response = self.send_message_to_llm(original_user_request)
        return self.convert_llm_response_to_json_instructions(llm_response)

    def send_message_to_llm(self, original_user_request: str) -> Any:
        base64_img = Screen().get_screenshot_in_base64()
        screenshot_url = f'data:image/png;base64,{base64_img}'
        screen_width, screen_height = Screen().get_size()

        tools = [{
            'type': 'computer_use_preview',
            'display_width': screen_width,
            'display_height': screen_height,
            'environment': 'browser'
        }]

        if self.previous_response_id and self.last_call_id:
            computer_call_output: dict[str, Any] = {
                'type': 'computer_call_output',
                'call_id': self.last_call_id,
                'output': {
                    'type': 'input_image',
                    'image_url': screenshot_url
                }
            }

            if self.pending_safety_checks:
                computer_call_output['acknowledged_safety_checks'] = self.pending_safety_checks
                self.pending_safety_checks = []

            return self.client.responses.create(
                model=self.model_name,
                previous_response_id=self.previous_response_id,
                tools=tools,
                input=[computer_call_output],
                truncation='auto'
            )

        return self.client.responses.create(
            model=self.model_name,
            tools=tools,
            input=[{
                'role': 'user',
                'content': [
                    {'type': 'input_text', 'text': original_user_request},
                    {'type': 'input_image', 'image_url': screenshot_url}
                ]
            }],
            reasoning={'summary': 'concise'},
            truncation='auto'
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
                'done': None
            }

        done_message = (self.read_obj(llm_response, 'output_text') or '').strip()
        if done_message == '':
            done_message = 'Done.'

        self.last_call_id = None
        self.pending_safety_checks = []
        return {
            'steps': [],
            'done': done_message
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
                    'message': message
                })
        return serialized

    def convert_action_to_steps(self, action: Any) -> list[dict[str, Any]]:
        action_type = self.read_obj(action, 'type')

        if action_type == 'click':
            return [{
                'function': 'click',
                'parameters': {
                    'x': self.read_obj(action, 'x'),
                    'y': self.read_obj(action, 'y'),
                    'button': self.read_obj(action, 'button') or 'left',
                    'clicks': 1
                }
            }]

        if action_type == 'double_click':
            return [{
                'function': 'click',
                'parameters': {
                    'x': self.read_obj(action, 'x'),
                    'y': self.read_obj(action, 'y'),
                    'button': 'left',
                    'clicks': 2
                }
            }]

        if action_type == 'move':
            return [{
                'function': 'moveTo',
                'parameters': {
                    'x': self.read_obj(action, 'x'),
                    'y': self.read_obj(action, 'y')
                }
            }]

        if action_type == 'scroll':
            scroll_y = self.read_obj(action, 'scroll_y') or 0
            return [{
                'function': 'scroll',
                'parameters': {
                    # Browser coordinate systems usually use positive Y for scrolling down;
                    # pyautogui.scroll uses negative values for down.
                    'clicks': int(-scroll_y)
                }
            }]

        if action_type == 'type':
            return [{
                'function': 'write',
                'parameters': {
                    'string': self.read_obj(action, 'text') or '',
                    'interval': 0.03
                }
            }]

        if action_type == 'wait':
            return [{
                'function': 'sleep',
                'parameters': {
                    'secs': 1
                }
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
                        'key': normalized_keys[0]
                    }
                }]
            return [{
                'function': 'hotkey',
                'parameters': {
                    'keys': normalized_keys
                }
            }]

        if action_type == 'drag':
            path = self.read_obj(action, 'path') or []
            if len(path) < 2:
                return []

            start_x = self.read_obj(path[0], 0)
            start_y = self.read_obj(path[0], 1)
            end_x = self.read_obj(path[-1], 0)
            end_y = self.read_obj(path[-1], 1)

            if None in [start_x, start_y, end_x, end_y]:
                return []

            return [
                {
                    'function': 'moveTo',
                    'parameters': {'x': start_x, 'y': start_y}
                },
                {
                    'function': 'dragTo',
                    'parameters': {'x': end_x, 'y': end_y, 'duration': 0.2, 'button': 'left'}
                }
            ]

        if action_type == 'screenshot':
            return []

        print(f'Unsupported computer_use action type: {action_type}')
        return []

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

    @staticmethod
    def normalize_key_name(key: str) -> str:
        key_l = str(key).lower()
        key_mappings = {
            'ctrl': 'ctrl',
            'control': 'ctrl',
            'cmd': 'command',
            'command': 'command',
            'option': 'option',
            'alt': 'alt',
            'return': 'enter',
            'esc': 'esc',
            'arrowleft': 'left',
            'arrowright': 'right',
            'arrowup': 'up',
            'arrowdown': 'down',
        }
        return key_mappings.get(key_l, key_l)

    def cleanup(self):
        self.previous_response_id = None
        self.last_call_id = None
        self.pending_safety_checks = []
