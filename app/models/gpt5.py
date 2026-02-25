import json
from typing import Any

from models.model import Model
from utils.screen import Screen


class GPT5(Model):
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

        # GPT-5 uses Responses API content blocks.
        return [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': self.context + request_data
                    },
                    {
                        'type': 'input_image',
                        'image_url': f'data:image/jpeg;base64,{base64_img}'
                    }
                ]
            }
        ]

    def send_message_to_llm(self, message: list[dict[str, Any]]) -> Any:
        return self.client.responses.create(
            model=self.model_name,
            input=message,
            max_output_tokens=800,
        )

    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> dict[str, Any]:
        llm_response_data = (getattr(llm_response, 'output_text', '') or '').strip()

        if llm_response_data == '':
            # Fallback parsing for SDKs/providers that don't populate output_text.
            chunks = []
            for output_item in getattr(llm_response, 'output', []) or []:
                for content_item in getattr(output_item, 'content', []) or []:
                    text = getattr(content_item, 'text', None)
                    if text:
                        chunks.append(text)
            llm_response_data = ''.join(chunks).strip()

        start_index = llm_response_data.find('{')
        end_index = llm_response_data.rfind('}')

        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'Error while parsing JSON response - {e}')
            json_response = {}

        return json_response
