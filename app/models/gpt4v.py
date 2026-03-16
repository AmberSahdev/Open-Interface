from typing import Any, cast

from models.model import Model
from prompting.builder import PromptPackage


class GPT4v(Model):
    def format_prompt_package_for_llm(
        self,
        prompt_package: PromptPackage,
        visual_payload: dict[str, Any],
        request_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return [
            {
                'role': 'system',
                'content': prompt_package.system_context,
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': prompt_package.user_context,
                    },
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f"data:image/png;base64,{visual_payload['annotated_image_base64']}",
                        },
                    },
                ],
            },
        ]

    def send_message_to_llm(
        self,
        message: list[dict[str, Any]],
        prompt_package: PromptPackage | None = None,
    ) -> Any:
        completions_client = cast(Any, self.client.chat.completions)
        response = completions_client.create(
            model=self.model_name,
            messages=message,
            max_tokens=800,
        )
        self.raise_for_provider_error(response)
        return response

    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> dict[str, Any]:
        choices = getattr(llm_response, 'choices', None) or []
        if len(choices) == 0:
            raise ValueError('模型没有返回任何候选结果。')

        message = getattr(choices[0], 'message', None)
        llm_response_data = str(getattr(message, 'content', '') or '').strip()
        return self.parse_json_response_text(llm_response_data)
