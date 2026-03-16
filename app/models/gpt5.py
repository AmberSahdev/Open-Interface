from typing import Any, cast

from models.model import Model
from prompting.builder import PromptPackage


class GPT5(Model):
    def format_prompt_package_for_llm(
        self,
        prompt_package: PromptPackage,
        visual_payload: dict[str, Any],
        request_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'input_text',
                        'text': prompt_package.system_context,
                    },
                ],
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': prompt_package.user_context,
                    },
                    {
                        'type': 'input_image',
                        'image_url': f"data:image/png;base64,{visual_payload['annotated_image_base64']}",
                    },
                ],
            }
        ]

    def send_message_to_llm(
        self,
        message: list[dict[str, Any]],
        prompt_package: PromptPackage | None = None,
    ) -> Any:
        request_options = self.build_reasoning_request_options()

        responses_client = cast(Any, self.client.responses)
        response = responses_client.create(
            model=self.model_name,
            input=message,
            max_output_tokens=800,
            **request_options,
        )
        self.raise_for_provider_error(response)
        return response

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

        return self.parse_json_response_text(llm_response_data)
