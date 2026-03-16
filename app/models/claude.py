from typing import Any

import httpx

from models.model import Model
from prompting.builder import PromptPackage


ANTHROPIC_VERSION = '2023-06-01'
DEFAULT_MAX_TOKENS = 800


class Claude(Model):
    def __init__(self, model_name, base_url, api_key, context):
        super().__init__(model_name, base_url, api_key, context)
        self.http_client = self._create_http_client(self.request_timeout_seconds)
        self.claude_enable_thinking = False
        self.claude_thinking_budget_tokens = 2048

    def cleanup(self):
        try:
            self.http_client.close()
        except Exception:
            pass
        return None

    def set_runtime_settings(self, settings_dict: dict[str, Any]) -> None:
        previous_timeout = self.request_timeout_seconds
        super().set_runtime_settings(settings_dict)
        enable_thinking = settings_dict.get('claude_enable_thinking', False)
        self.claude_enable_thinking = isinstance(enable_thinking, bool) and enable_thinking

        budget_raw = settings_dict.get('claude_thinking_budget_tokens', 2048)
        try:
            budget_tokens = int(budget_raw)
        except Exception:
            budget_tokens = 2048
        if budget_tokens <= 0:
            budget_tokens = 2048
        self.claude_thinking_budget_tokens = budget_tokens

        if previous_timeout != self.request_timeout_seconds:
            try:
                self.http_client.close()
            except Exception:
                pass
            self.http_client = self._create_http_client(self.request_timeout_seconds)

    def get_instructions_for_objective(
        self,
        original_user_request: str,
        step_num: int = 0,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return super().get_instructions_for_objective(
            original_user_request,
            step_num,
            request_context=request_context,
        )

    def format_prompt_package_for_llm(
        self,
        prompt_package: PromptPackage,
        visual_payload: dict[str, Any],
        request_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': prompt_package.user_context,
                    },
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/png',
                            'data': visual_payload['annotated_image_base64'],
                        },
                    },
                ],
            }
        ]

    def send_message_to_llm(
        self,
        message: list[dict[str, Any]],
        prompt_package: PromptPackage | None = None,
    ) -> dict[str, Any]:
        payload = self.build_request_payload(message, prompt_package)

        response = self.http_client.post(
            self._build_messages_endpoint(),
            headers=self._build_headers(),
            json=payload,
        )
        return self._parse_http_response(response)

    def build_request_payload(
        self,
        message: list[dict[str, Any]],
        prompt_package: PromptPackage | None,
    ) -> dict[str, Any]:
        max_tokens = DEFAULT_MAX_TOKENS
        payload: dict[str, Any] = {
            'model': self.model_name,
            'max_tokens': max_tokens,
            'system': self.context if prompt_package is None else prompt_package.system_context,
            'messages': message,
        }

        if self.claude_enable_thinking:
            thinking_budget_tokens = max(1, int(self.claude_thinking_budget_tokens))
            payload['thinking'] = {
                'type': 'enabled',
                'budget_tokens': thinking_budget_tokens,
            }
            payload['max_tokens'] = max_tokens + thinking_budget_tokens

        return payload

    def convert_llm_response_to_json_instructions(self, llm_response: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(llm_response, dict):
            raise ValueError('Claude 兼容服务没有返回 JSON 对象。')

        content_blocks = llm_response.get('content')
        if not isinstance(content_blocks, list) or len(content_blocks) == 0:
            raise ValueError('Claude 兼容服务没有返回任何内容块。')

        text_segments: list[str] = []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            if str(block.get('type') or '') != 'text':
                continue
            text_value = str(block.get('text') or '').strip()
            if text_value != '':
                text_segments.append(text_value)

        llm_response_data = '\n'.join(text_segments).strip()
        return self.parse_json_response_text(llm_response_data)

    def _build_headers(self) -> dict[str, str]:
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'anthropic-version': ANTHROPIC_VERSION,
        }
        if self.api_key != '':
            headers['x-api-key'] = self.api_key
            headers['authorization'] = f'Bearer {self.api_key}'
        return headers

    def _build_messages_endpoint(self) -> str:
        normalized_base_url = str(self.base_url or '').strip().rstrip('/')
        if normalized_base_url.endswith('/v1/messages'):
            return normalized_base_url
        if normalized_base_url.endswith('/v1'):
            return normalized_base_url + '/messages'
        return normalized_base_url + '/v1/messages'

    def _create_http_client(self, timeout_seconds: float) -> httpx.Client:
        return httpx.Client(timeout=timeout_seconds)

    def _parse_http_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            response_payload = response.json()
        except Exception as exc:
            response_payload = None
            response.raise_for_status()
            raise RuntimeError(f'Claude 兼容服务返回了无法解析的响应：{exc}') from exc

        if response.is_success:
            if isinstance(response_payload, dict):
                return response_payload
            raise RuntimeError('Claude 兼容服务返回了非对象 JSON。')

        error_message = self._extract_error_message(response_payload)
        request_id = response.headers.get('request-id') or response.headers.get('x-request-id') or ''
        details = f'HTTP {response.status_code}'
        if request_id != '':
            details += f', request_id={request_id}'
        raise RuntimeError(f'Claude 兼容服务返回失败：{error_message} ({details})')

    def _extract_error_message(self, response_payload: Any) -> str:
        if not isinstance(response_payload, dict):
            return '未知错误。'

        error_payload = response_payload.get('error')
        if isinstance(error_payload, dict):
            error_type = str(error_payload.get('type') or '').strip()
            error_message = str(error_payload.get('message') or '').strip()
            if error_type != '' and error_message != '':
                return f'{error_message} (type={error_type})'
            if error_message != '':
                return error_message

        message = str(response_payload.get('message') or '').strip()
        if message != '':
            return message

        return '未知错误。'
