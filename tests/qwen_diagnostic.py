"""Qwen / DashScope integration diagnostic helper.

This script reads the persisted app settings, shows the effective model route,
and performs a minimal DashScope probe without launching the GUI.
It is intended for local debugging when the runtime stops after the first model
request.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from models.catalog import (
    DEFAULT_BASE_URL,
    DEFAULT_QWEN_BASE_URL,
    is_qwen_model,
    is_qwen_vision_model,
    requires_qwen_reasoning,
    supports_qwen_reasoning_toggle,
)
from utils.settings import Settings


SAMPLE_REQUEST = '你是桌面自动化代理。请严格只返回 JSON：{"steps": [], "done": "ok"}'
SAMPLE_IMAGE_URL = 'https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg'


def mask_secret(value: str) -> str:
    normalized = str(value or '').strip()
    if normalized == '':
        return ''
    if len(normalized) <= 8:
        return '*' * len(normalized)
    return f'{normalized[:4]}...{normalized[-4:]}'


def resolve_route(model_name: str) -> str:
    normalized = str(model_name or '').strip()
    if normalized == 'gpt-4o' or normalized == 'gpt-4o-mini':
        return 'GPT4o'
    if normalized == 'computer-use-preview':
        return 'OpenAIComputerUse'
    if normalized.startswith('gpt-5'):
        return 'GPT5'
    if normalized == 'gpt-4-vision-preview' or normalized == 'gpt-4-turbo':
        return 'GPT4v'
    if is_qwen_model(normalized):
        return 'Qwen'
    if normalized.startswith('gemini'):
        return 'GPT4v'
    return 'GPT4v'


def build_client(base_url: str, api_key: str, timeout_seconds: float) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout_seconds,
        max_retries=0,
    )


def build_probe_payload(model_name: str, include_image: bool, enable_reasoning: bool) -> tuple[str, dict[str, Any]]:
    if is_qwen_model(model_name):
        request_options: dict[str, Any] = {}
        if requires_qwen_reasoning(model_name):
            request_options['extra_body'] = {
                'enable_thinking': True,
            }
        elif supports_qwen_reasoning_toggle(model_name):
            request_options['extra_body'] = {
                'enable_thinking': enable_reasoning,
            }

        if include_image:
            request_options['messages'] = [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': SAMPLE_REQUEST,
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': SAMPLE_IMAGE_URL,
                            },
                        },
                    ],
                }
            ]
        else:
            request_options['messages'] = [
                {
                    'role': 'user',
                    'content': SAMPLE_REQUEST,
                }
            ]
        return 'chat.completions', request_options

    request_options = {
        'input': SAMPLE_REQUEST,
        'max_output_tokens': 120,
    }
    return 'responses', request_options


def summarize_response(response: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        'object_type': type(response).__name__,
        'status': getattr(response, 'status', None),
        'error': getattr(response, 'error', None),
        'output_text': getattr(response, 'output_text', None),
    }

    choices = getattr(response, 'choices', None)
    if choices is not None:
        summary['choices_count'] = len(choices)
        if len(choices) > 0:
            first_message = getattr(choices[0], 'message', None)
            summary['first_choice_content'] = getattr(first_message, 'content', None)

    output = getattr(response, 'output', None)
    if output is not None:
        summary['output_count'] = len(output)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnose DashScope / Qwen configuration issues.')
    parser.add_argument('--model', default='', help='Temporarily override the persisted model name.')
    parser.add_argument('--base-url', default='', help='Temporarily override the persisted base_url.')
    parser.add_argument('--api-key', default='', help='Temporarily override the persisted api_key.')
    parser.add_argument('--timeout', type=float, default=30.0, help='Request timeout in seconds.')
    parser.add_argument('--with-image', action='store_true', help='Include a tiny inline image for VL model probing.')
    parser.add_argument('--enable-thinking', action='store_true', help='Force enable Qwen thinking when supported.')
    parser.add_argument('--disable-thinking', action='store_true', help='Force disable Qwen thinking when supported.')
    args = parser.parse_args()

    settings = Settings().get_dict()
    model_name = str(args.model or settings.get('model') or '').strip()
    base_url = str(args.base_url or settings.get('base_url') or DEFAULT_BASE_URL).strip().rstrip('/') + '/'
    api_key = str(args.api_key or settings.get('api_key') or '').strip()
    enable_reasoning = bool(settings.get('enable_reasoning', False))
    if args.enable_thinking:
        enable_reasoning = True
    if args.disable_thinking:
        enable_reasoning = False

    print('=== Persisted Settings Snapshot ===')
    print(json.dumps({
        'provider_type': settings.get('provider_type'),
        'base_url': settings.get('base_url'),
        'model': settings.get('model'),
        'enable_reasoning': settings.get('enable_reasoning'),
        'reasoning_depth': settings.get('reasoning_depth'),
        'request_timeout_seconds': settings.get('request_timeout_seconds'),
        'api_key': mask_secret(str(settings.get('api_key') or '')),
    }, ensure_ascii=False, indent=2))

    print('\n=== Effective Probe Config ===')
    print(json.dumps({
        'model': model_name,
        'base_url': base_url,
        'api_key': mask_secret(api_key),
        'expected_route': resolve_route(model_name),
        'is_qwen_model': is_qwen_model(model_name),
        'is_qwen_vision_model': is_qwen_vision_model(model_name),
        'supports_qwen_reasoning_toggle': supports_qwen_reasoning_toggle(model_name),
        'requires_qwen_reasoning': requires_qwen_reasoning(model_name),
        'enable_reasoning': enable_reasoning,
        'suggested_qwen_base_url': DEFAULT_QWEN_BASE_URL,
        'with_image': args.with_image,
    }, ensure_ascii=False, indent=2))

    if api_key == '':
        print('\nERROR: 当前没有可用的 API Key。')
        return 2

    client = build_client(base_url, api_key, args.timeout)
    endpoint_name, request_options = build_probe_payload(
        model_name,
        include_image=args.with_image,
        enable_reasoning=enable_reasoning,
    )

    try:
        if endpoint_name == 'chat.completions':
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=120,
                **request_options,
            )
        else:
            response = client.responses.create(
                model=model_name,
                **request_options,
            )
    except Exception as exc:
        print('\n=== Request Exception ===')
        print(type(exc).__name__)
        print(str(exc))
        return 1

    summary = summarize_response(response)
    print('\n=== Raw Response Summary ===')
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))

    response_error = getattr(response, 'error', None)
    response_status = str(getattr(response, 'status', '') or '').strip().lower()
    if response_error is not None or response_status in {'failed', 'incomplete'}:
        print('\nDIAGNOSIS: 模型服务已返回失败状态，当前配置不可用。')
        return 1

    print('\nDIAGNOSIS: 请求已成功返回，当前配置至少可以完成基础接口调用。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
