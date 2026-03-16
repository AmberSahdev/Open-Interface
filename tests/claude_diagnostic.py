"""Claude provider diagnostic helper.

This script verifies the Anthropic-compatible request shape used by the app,
including model routing, endpoint resolution, headers, and multimodal payload
format. It can optionally send a live request when a compatible proxy base URL
and API key are supplied.
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from models.catalog import DEFAULT_ANTHROPIC_BASE_URL, DEFAULT_CLAUDE_MODEL_NAME
from models.factory import ModelFactory
from models.claude import Claude


SAMPLE_IMAGE_BASE64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnSUs8AAAAASUVORK5CYII='
SAMPLE_REQUEST = '你是桌面自动化代理。请严格只返回 JSON：{"steps": [], "done": "ok"}'


def mask_secret(value: str) -> str:
    normalized = str(value or '').strip()
    if normalized == '':
        return ''
    if len(normalized) <= 8:
        return '*' * len(normalized)
    return f'{normalized[:4]}...{normalized[-4:]}'


def build_visual_payload() -> dict:
    return {
        'annotated_image_base64': SAMPLE_IMAGE_BASE64,
        'frame_context': {
            'grid_reference': {
                'coordinate_system': 'percent',
                'x_range': [0, 100],
                'y_range': [0, 100],
            },
            'logical_screen': {
                'width': 1440,
                'height': 900,
            },
            'captured_screen': {
                'width': 1440,
                'height': 900,
            },
        },
    }


def extract_text(response_payload: dict) -> str:
    content_blocks = response_payload.get('content') if isinstance(response_payload, dict) else None
    if not isinstance(content_blocks, list):
        return ''

    parts: list[str] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get('type') or '') != 'text':
            continue
        text = str(block.get('text') or '').strip()
        if text != '':
            parts.append(text)
    return '\n'.join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnose Claude Anthropic-compatible integration.')
    parser.add_argument('--model', default=DEFAULT_CLAUDE_MODEL_NAME, help='Claude model or proxy alias.')
    parser.add_argument('--base-url', default=DEFAULT_ANTHROPIC_BASE_URL, help='Anthropic-compatible base URL.')
    parser.add_argument('--api-key', default='test-api-key', help='API key used for headers or live requests.')
    parser.add_argument('--timeout', type=float, default=25.0, help='Timeout seconds.')
    parser.add_argument('--enable-thinking', action='store_true', help='Enable Claude thinking in the request payload.')
    parser.add_argument('--thinking-budget', type=int, default=2048, help='Claude thinking budget_tokens value.')
    parser.add_argument('--live', action='store_true', help='Send a real request to the configured endpoint.')
    args = parser.parse_args()

    routed_model = ModelFactory.create_model(
        args.model,
        args.api_key,
        args.base_url,
        '请只返回 JSON。',
        provider_type='anthropic_compatible',
    )
    if not isinstance(routed_model, Claude):
        print('ERROR: ModelFactory did not route to Claude adapter.')
        return 1

    routed_model.set_runtime_settings({
        'request_timeout_seconds': args.timeout,
        'claude_enable_thinking': args.enable_thinking,
        'claude_thinking_budget_tokens': args.thinking_budget,
    })
    routed_model.request_timeout_seconds = args.timeout
    routed_model.http_client = routed_model._create_http_client(args.timeout)
    message = routed_model.format_user_request_for_llm(
        SAMPLE_REQUEST,
        0,
        build_visual_payload(),
        None,
    )
    endpoint = routed_model._build_messages_endpoint()
    headers = routed_model._build_headers()
    request_payload = routed_model.build_request_payload(message)

    print('=== Claude Config ===')
    print(json.dumps({
        'model': args.model,
        'base_url': args.base_url,
        'api_key': mask_secret(args.api_key),
        'endpoint': endpoint,
        'timeout_seconds': args.timeout,
        'claude_enable_thinking': args.enable_thinking,
        'claude_thinking_budget_tokens': args.thinking_budget,
    }, ensure_ascii=False, indent=2))

    print('\n=== Payload Summary ===')
    content_blocks = message[0]['content']
    print(json.dumps({
        'message_count': len(message),
        'first_role': message[0]['role'],
        'content_types': [block.get('type') for block in content_blocks],
        'has_image_base64': bool(content_blocks[1]['source'].get('data')),
        'headers': {
            'anthropic-version': headers.get('anthropic-version'),
            'x-api-key': mask_secret(headers.get('x-api-key', '')),
        },
        'thinking': request_payload.get('thinking'),
        'max_tokens': request_payload.get('max_tokens'),
    }, ensure_ascii=False, indent=2))

    if endpoint.endswith('/v1/messages') is False:
        print('ERROR: Endpoint does not resolve to /v1/messages.')
        return 1
    if message[0]['role'] != 'user':
        print('ERROR: Claude payload role must be user.')
        return 1
    if [block.get('type') for block in content_blocks] != ['text', 'image']:
        print('ERROR: Claude multimodal content blocks are malformed.')
        return 1
    if headers.get('anthropic-version', '') == '':
        print('ERROR: anthropic-version header is missing.')
        return 1
    if args.enable_thinking and request_payload.get('thinking') != {
        'type': 'enabled',
        'budget_tokens': args.thinking_budget,
    }:
        print('ERROR: Claude thinking payload is malformed.')
        return 1
    if (not args.enable_thinking) and 'thinking' in request_payload:
        print('ERROR: Claude thinking should be omitted when disabled.')
        return 1

    if not args.live:
        print('\nDIAGNOSIS: Dry-run passed. Claude payload shape is valid for Anthropic-compatible providers.')
        return 0

    try:
        response_payload = routed_model.send_message_to_llm(message)
    except Exception as exc:
        print('\n=== Live Request Exception ===')
        print(type(exc).__name__)
        print(str(exc))
        return 1

    print('\n=== Live Response Summary ===')
    print(json.dumps({
        'id': response_payload.get('id'),
        'model': response_payload.get('model'),
        'stop_reason': response_payload.get('stop_reason'),
        'text_preview': extract_text(response_payload)[:400],
    }, ensure_ascii=False, indent=2))

    print('\nDIAGNOSIS: Live Claude-compatible request succeeded.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
