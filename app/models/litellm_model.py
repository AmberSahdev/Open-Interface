import json
from typing import Any

import litellm

from models.model import Model
from utils.screen import Screen


class LiteLLMModel(Model):
    # Default base_url injected by llm.py when no custom URL is set.
    _DEFAULT_OPENAI_BASE_URL = 'https://api.openai.com/v1/'

    def __init__(self, model_name, base_url, api_key, context):
        self.model_name = model_name
        self.api_key = api_key
        self.context = context
        # Only store base_url if the user explicitly set a custom endpoint.
        # The default OpenAI URL would break LiteLLM's own provider routing.
        self.base_url = base_url if base_url != self._DEFAULT_OPENAI_BASE_URL else None

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        message = self.format_user_request_for_llm(original_user_request, step_num)
        llm_response = self.send_message_to_llm(message)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)
        return json_instructions

    def format_user_request_for_llm(self, original_user_request: str, step_num: int) -> list[dict[str, Any]]:
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

    def send_message_to_llm(self, message) -> Any:
        kwargs = {
            'model': self.model_name,
            'messages': [
                {
                    'role': 'user',
                    'content': message,
                }
            ],
            'max_tokens': 800,
            'drop_params': True,
        }

        if self.api_key:
            kwargs['api_key'] = self.api_key
        if self.base_url:
            kwargs['api_base'] = self.base_url

        response = litellm.completion(**kwargs)
        return response

    def convert_llm_response_to_json_instructions(self, llm_response) -> dict[str, Any]:
        llm_response_data: str = llm_response.choices[0].message.content.strip()

        start_index = llm_response_data.find('{')
        end_index = llm_response_data.rfind('}')

        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'Error while parsing JSON response - {e}')
            json_response = {}

        return json_response
