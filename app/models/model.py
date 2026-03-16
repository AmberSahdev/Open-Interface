import json
import os
from typing import Any, Optional

from agent_memory import build_agent_memory_payload
from openai import OpenAI
from prompting.builder import PromptPackage
from prompting.builder import build_prompt_package
from prompting.debug import maybe_dump_prompt_package
from utils.screen import Screen
from utils.settings import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    MAX_REQUEST_TIMEOUT_SECONDS,
    MIN_REQUEST_TIMEOUT_SECONDS,
)


SUPPORTED_REASONING_EFFORTS = {'none', 'low', 'medium', 'high', 'xhigh'}
DEFAULT_MAX_RETRIES = 0


class Model:
    def __init__(self, model_name, base_url, api_key, context):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.context = context
        self.request_timeout_seconds = DEFAULT_REQUEST_TIMEOUT_SECONDS
        self.client = self._create_openai_client(timeout_seconds=self.request_timeout_seconds)
        self.enable_reasoning = False
        self.reasoning_depth = 'low'
        self.prompt_runtime_data: dict[str, Any] = {
            'base_system_rules': str(context or ''),
            'custom_instructions': '',
            'machine_profile': {},
            'prompt_schema_version': 'v1',
            'save_prompt_text_dumps': False,
        }
        self.last_prompt_package: Optional[PromptPackage] = None

        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key

    def get_instructions_for_objective(
        self,
        original_user_request: str,
        step_num: int = 0,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.execute_prompt_round(
            original_user_request=original_user_request,
            step_num=step_num,
            request_context=request_context,
        )

    def format_prompt_package_for_llm(
        self,
        prompt_package: PromptPackage,
        visual_payload: dict[str, Any],
        request_context: dict[str, Any] | None,
    ) -> Any:
        raise NotImplementedError('Subclasses must implement format_prompt_package_for_llm().')

    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> dict[str, Any]:
        raise NotImplementedError('Subclasses must implement convert_llm_response_to_json_instructions().')
        return {}

    def send_message_to_llm(
        self,
        message: Any,
        prompt_package: PromptPackage | None = None,
    ) -> Any:
        raise NotImplementedError('Subclasses must implement send_message_to_llm().')

    def cleanup(self):
        return None

    def set_prompt_runtime_data(self, prompt_runtime_data: dict[str, Any]) -> None:
        if not isinstance(prompt_runtime_data, dict):
            return
        self.prompt_runtime_data = dict(prompt_runtime_data)

    def execute_prompt_round(
        self,
        *,
        original_user_request: str,
        step_num: int,
        request_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        visual_payload = self.get_visual_prompt_payload()
        prompt_package = self.build_prompt_package(
            original_user_request=original_user_request,
            step_num=step_num,
            request_context=request_context,
            frame_context=visual_payload.get('frame_context'),
        )
        self.last_prompt_package = prompt_package
        maybe_dump_prompt_package(
            prompt_package,
            enabled=bool(self.prompt_runtime_data.get('save_prompt_text_dumps', False)),
        )
        message = self.format_prompt_package_for_llm(prompt_package, visual_payload, request_context)
        llm_response = self.send_message_to_llm(message, prompt_package=prompt_package)
        instructions = self.convert_llm_response_to_json_instructions(llm_response)
        instructions = self.normalize_json_instructions(instructions)
        instructions = self.enrich_steps_with_anchor_coordinates(
            instructions,
            visual_payload['frame_context'],
        )
        instructions['frame_context'] = visual_payload['frame_context']
        return instructions

    def get_visual_prompt_payload(self) -> dict[str, Any]:
        return Screen().get_visual_prompt_payload()

    def build_prompt_package(
        self,
        *,
        original_user_request: str,
        step_num: int,
        request_context: dict[str, Any] | None,
        frame_context: dict[str, Any] | None,
    ) -> PromptPackage:
        base_system_rules = str(self.prompt_runtime_data.get('base_system_rules') or self.context or '')
        custom_instructions = str(self.prompt_runtime_data.get('custom_instructions') or '').strip()
        machine_profile = self.prompt_runtime_data.get('machine_profile')
        return build_prompt_package(
            base_system_rules=base_system_rules,
            custom_instructions=custom_instructions,
            original_user_request=original_user_request,
            step_num=step_num,
            request_context=request_context,
            frame_context=frame_context,
            machine_profile=machine_profile if isinstance(machine_profile, dict) else {},
        )

    def set_runtime_settings(self, settings_dict: dict[str, Any]) -> None:
        enable_reasoning = settings_dict.get('enable_reasoning', False)
        self.enable_reasoning = isinstance(enable_reasoning, bool) and enable_reasoning

        reasoning_depth = str(settings_dict.get('reasoning_depth') or 'low').strip().lower()
        if reasoning_depth not in SUPPORTED_REASONING_EFFORTS:
            reasoning_depth = 'low'
        self.reasoning_depth = reasoning_depth

        timeout_seconds = self._resolve_timeout_seconds(settings_dict)
        if timeout_seconds != self.request_timeout_seconds:
            self.request_timeout_seconds = timeout_seconds
            self.client = self._create_openai_client(timeout_seconds=timeout_seconds)

    def build_reasoning_request_options(self, include_summary: bool = False) -> dict[str, Any]:
        if not self.enable_reasoning:
            return {}

        reasoning_options: dict[str, Any] = {
            'effort': self.reasoning_depth,
        }

        if include_summary:
            reasoning_options['summary'] = 'auto'

        return {
            'reasoning': reasoning_options,
        }

    def raise_for_provider_error(self, llm_response: Any) -> None:
        error_message = self.extract_provider_error_message(llm_response)
        if error_message == '':
            return

        raise RuntimeError(f'模型服务返回失败：{error_message}')

    def extract_provider_error_message(self, llm_response: Any) -> str:
        if llm_response is None:
            return '模型服务没有返回任何内容。'

        response_error = getattr(llm_response, 'error', None)
        response_status = str(getattr(llm_response, 'status', '') or '').strip().lower()

        if response_error is None and response_status not in {'failed', 'incomplete'}:
            return ''

        if isinstance(response_error, dict):
            error_message = str(response_error.get('message') or '').strip()
            error_code = str(response_error.get('code') or '').strip()
        else:
            error_message = str(getattr(response_error, 'message', '') or '').strip()
            error_code = str(getattr(response_error, 'code', '') or '').strip()

        if error_message != '' and error_code != '':
            return f'{error_message} (code={error_code})'

        if error_message != '':
            return error_message

        if error_code != '':
            return f'错误码：{error_code}'

        if response_status == 'incomplete':
            return '模型响应未完成。'

        return '模型响应状态异常。'

    def parse_json_response_text(self, llm_response_data: str) -> dict[str, Any]:
        response_text = str(llm_response_data or '').strip()
        if response_text == '':
            raise ValueError('模型返回空文本，无法解析为执行步骤。')

        start_index = response_text.find('{')
        end_index = response_text.rfind('}')
        if start_index == -1 or end_index == -1 or end_index < start_index:
            preview = response_text[:400].replace('\n', ' ')
            raise ValueError(f'模型没有返回 JSON。原始响应片段：{preview}')

        candidate_json = response_text[start_index:end_index + 1].strip()

        try:
            return json.loads(candidate_json)
        except Exception as exc:
            preview = candidate_json[:400].replace('\n', ' ')
            raise ValueError(f'模型返回的 JSON 无法解析：{exc}。响应片段：{preview}') from exc

    def normalize_json_instructions(self, instructions: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(instructions, dict):
            return {
                'steps': [],
                'done': None,
            }

        normalized_steps: list[dict[str, Any]] = []
        steps = instructions.get('steps')
        if isinstance(steps, list):
            for raw_step in steps:
                if not isinstance(raw_step, dict):
                    continue
                normalized_steps.append({
                    'function': str(raw_step.get('function') or '').strip(),
                    'parameters': dict(raw_step.get('parameters') or {}),
                    'human_readable_justification': str(
                        raw_step.get('human_readable_justification') or ''
                    ).strip(),
                    'expected_outcome': str(raw_step.get('expected_outcome') or '').strip(),
                })

        done_value = instructions.get('done')
        if done_value is None:
            normalized_done = None
        else:
            normalized_done = str(done_value).strip()

        normalized_instructions = dict(instructions)
        normalized_instructions['steps'] = normalized_steps
        normalized_instructions['done'] = normalized_done
        return normalized_instructions

    def build_agent_loop_payload(self, request_context: Optional[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            'mode': 'single_step_mvp',
            'step_budget': 1,
            'agent_memory': create_empty_agent_payload(),
        }
        if not isinstance(request_context, dict):
            return payload

        payload['agent_memory'] = build_agent_memory_payload(request_context.get('agent_memory'))
        return payload

    def resolve_anchor_to_percent(
        self,
        frame_context: dict[str, Any],
        anchor_id: Any,
    ) -> Optional[tuple[float, float]]:
        anchors = frame_context.get('anchors') if isinstance(frame_context, dict) else None
        if not isinstance(anchors, list):
            return None

        try:
            normalized_anchor_id = int(anchor_id)
        except Exception:
            return None

        for anchor in anchors:
            if not isinstance(anchor, dict):
                continue
            if int(anchor.get('id', -1)) != normalized_anchor_id:
                continue
            x_percent = self._read_float(anchor.get('x_percent'))
            y_percent = self._read_float(anchor.get('y_percent'))
            if x_percent is None or y_percent is None:
                return None
            return self._clamp_percent(x_percent), self._clamp_percent(y_percent)

        return None

    def enrich_steps_with_anchor_coordinates(
        self,
        instructions: dict[str, Any],
        frame_context: dict[str, Any],
    ) -> dict[str, Any]:
        steps = instructions.get('steps')
        if not isinstance(steps, list):
            return instructions

        captured_screen = self._get_capture_size(frame_context)

        for step in steps:
            if not isinstance(step, dict):
                continue
            parameters = step.get('parameters')
            if not isinstance(parameters, dict):
                continue
            if 'x_percent' in parameters and 'y_percent' in parameters:
                continue

            if 'target_anchor_id' in parameters:
                anchor_id_raw = parameters.get('target_anchor_id')
                resolved = self.resolve_anchor_to_percent(frame_context, anchor_id_raw)
                if resolved is not None:
                    if anchor_id_raw is not None:
                        anchor_id_text = str(anchor_id_raw).strip()
                        try:
                            parameters['target_anchor_id'] = int(anchor_id_text)
                        except Exception:
                            pass
                    continue

            x_value = self._read_float(parameters.get('x'))
            y_value = self._read_float(parameters.get('y'))
            if x_value is None or y_value is None:
                continue

            if 0.0 <= x_value <= 1.0 and 0.0 <= y_value <= 1.0:
                parameters['x_percent'] = self._to_grid_percent(self._clamp_percent(x_value))
                parameters['y_percent'] = self._to_grid_percent(self._clamp_percent(y_value))
                continue

            if captured_screen is None:
                continue

            capture_width, capture_height = captured_screen
            parameters['x_percent'] = self._to_grid_percent(
                self._clamp_percent(x_value / float(max(1, capture_width)))
            )
            parameters['y_percent'] = self._to_grid_percent(
                self._clamp_percent(y_value / float(max(1, capture_height)))
            )

        return instructions

    def _get_capture_size(self, frame_context: dict[str, Any]) -> Optional[tuple[int, int]]:
        if not isinstance(frame_context, dict):
            return None

        captured = frame_context.get('captured_screen')
        if not isinstance(captured, dict):
            return None

        width = self._read_float(captured.get('width'))
        height = self._read_float(captured.get('height'))
        if width is None or height is None:
            return None

        width_int = int(width)
        height_int = int(height)
        if width_int <= 0 or height_int <= 0:
            return None

        return width_int, height_int

    def _read_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return None

    def _clamp_percent(self, value: float) -> float:
        return max(0.0, min(1.0, round(value, 4)))

    def _to_grid_percent(self, value: float) -> float:
        return round(value * 100.0, 4)

    def _create_openai_client(self, timeout_seconds: float) -> OpenAI:
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout_seconds,
            max_retries=DEFAULT_MAX_RETRIES,
        )

    def _resolve_timeout_seconds(self, settings_dict: dict[str, Any]) -> float:
        raw_timeout = settings_dict.get('request_timeout_seconds', DEFAULT_REQUEST_TIMEOUT_SECONDS)
        try:
            timeout_seconds = float(raw_timeout)
        except Exception:
            return DEFAULT_REQUEST_TIMEOUT_SECONDS

        if timeout_seconds < MIN_REQUEST_TIMEOUT_SECONDS:
            return DEFAULT_REQUEST_TIMEOUT_SECONDS

        if timeout_seconds > MAX_REQUEST_TIMEOUT_SECONDS:
            return DEFAULT_REQUEST_TIMEOUT_SECONDS

        return timeout_seconds


def create_empty_agent_payload() -> dict[str, Any]:
    return {
        'recent_actions': [],
        'recent_failures': [],
        'unreliable_anchor_ids': [],
        'consecutive_verification_failures': 0,
    }
