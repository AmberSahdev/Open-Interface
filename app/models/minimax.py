import json
import os
from typing import Any

from models.model import Model
from utils.screen import Screen

MINIMAX_BASE_URL = 'https://api.minimax.io/v1/'


class MiniMax(Model):
    """
    MiniMax model integration via OpenAI-compatible API.
    Supports MiniMax-M2.7 (latest) and MiniMax-M2.5-highspeed (204K context).
    """

    def __init__(self, model_name, base_url, api_key, context):
        # Use MiniMax base URL unless user has explicitly set a custom one
        if not base_url or base_url.rstrip('/') + '/' == 'https://api.openai.com/v1/':
            base_url = MINIMAX_BASE_URL

        # Prefer MINIMAX_API_KEY env var if no API key was provided
        if not api_key:
            api_key = os.environ.get('MINIMAX_API_KEY', '')

        super().__init__(model_name, base_url, api_key, context)

        if api_key:
            os.environ['MINIMAX_API_KEY'] = api_key

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        message: list[dict[str, Any]] = self.format_user_request_for_llm(original_user_request, step_num)
        llm_response = self.send_message_to_llm(message)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)
        return json_instructions

    def format_user_request_for_llm(self, original_user_request, step_num) -> list[dict[str, Any]]:
        base64_img: str = Screen().get_screenshot_in_base64()

        request_data: str = json.dumps({
            'original_user_request': original_user_request,
            'step_num': step_num
        })

        message = [
            {'type': 'text', 'text': self.context + request_data},
            {'type': 'image_url',
             'image_url': {
                 'url': f'data:image/jpeg;base64,{base64_img}'
             }
             }
        ]

        return message

    def send_message_to_llm(self, message):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    'role': 'user',
                    'content': message,
                }
            ],
            max_tokens=800,
            temperature=min(max(0.01, 0.7), 1.0),
        )
        return response

    def convert_llm_response_to_json_instructions(self, llm_response) -> dict[str, Any]:
        llm_response_data: str = llm_response.choices[0].message.content.strip()

        # Strip MiniMax thinking tags if present (M2.5+ models may include <think>...</think> blocks)
        if '<think>' in llm_response_data and '</think>' in llm_response_data:
            think_end = llm_response_data.rfind('</think>')
            llm_response_data = llm_response_data[think_end + len('</think>'):].strip()

        start_index = llm_response_data.find('{')
        end_index = llm_response_data.rfind('}')

        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'Error while parsing JSON response - {e}')
            json_response = {}

        return json_response
