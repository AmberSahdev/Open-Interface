import time
from typing import Any, cast

from models.model import Model
from prompting.builder import PromptPackage
from prompting.debug import maybe_dump_prompt_package
from utils.screen import Screen


# TODO
# [ ] Function calling with assistants api - https://platform.openai.com/docs/assistants/tools/function-calling/quickstart

class GPT4o(Model):
    def __init__(self, model_name, base_url, api_key, context):
        super().__init__(model_name, base_url, api_key, context)

        # GPT4o has Assistant Mode enabled that we can utilize to make Open Interface be more contextually aware
        self.assistant = self.client.beta.assistants.create(
            name='Open Interface Backend',
            instructions=self.context,
            model=model_name,
            # tools=[],
        )

        self.thread = self.client.beta.threads.create()

        # IDs of images uploaded to OpenAI for use with the assistants API, can be cleaned up once thread is no longer needed
        self.list_of_image_ids = []

    def get_instructions_for_objective(
        self,
        original_user_request: str,
        step_num: int = 0,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Upload screenshot to OpenAI - Note: Don't delete files from openai while the thread is active
        openai_screenshot_file_id, frame_context = self.upload_visual_prompt_and_get_file_id()

        prompt_package = self.build_prompt_package(
            original_user_request=original_user_request,
            step_num=step_num,
            request_context=request_context,
            frame_context=frame_context,
        )
        self.last_prompt_package = prompt_package
        maybe_dump_prompt_package(
            prompt_package,
            enabled=bool(self.prompt_runtime_data.get('save_prompt_text_dumps', False)),
        )

        self.list_of_image_ids.append(openai_screenshot_file_id)

        # Format user request to send to LLM
        formatted_user_request = self.format_prompt_package_for_llm(
            prompt_package,
            {
                'annotated_image_base64': '',
                'frame_context': frame_context,
                'openai_screenshot_file_id': openai_screenshot_file_id,
            },
            request_context,
        )

        # Read response
        llm_response = self.send_message_to_llm(formatted_user_request, prompt_package=prompt_package)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)
        json_instructions = self.normalize_json_instructions(json_instructions)
        json_instructions = self.enrich_steps_with_anchor_coordinates(json_instructions, frame_context)
        json_instructions['frame_context'] = frame_context

        return json_instructions

    def reset_for_new_request(self) -> None:
        self.thread = self.client.beta.threads.create()

    def send_message_to_llm(
        self,
        message: list[dict[str, Any]],
        prompt_package: PromptPackage | None = None,
    ) -> Any:
        threads_client = cast(Any, self.client.beta.threads)
        messages_client = cast(Any, threads_client.messages)
        messages_client.create(
            thread_id=self.thread.id,
            role='user',
            content=message,
        )

        run = threads_client.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id,
            instructions=self.context if prompt_package is None else prompt_package.system_context,
        )

        while run.status != 'completed':
            print(f'Waiting for response, sleeping for 1. run.status={run.status}')
            time.sleep(1)

            if run.status == 'failed':
                print(f'failed run run.required_action:{run.required_action} run.last_error: {run.last_error}\n\n')
                return None

        if run.status == 'completed':
            # NOTE: Apparently right now the API doesn't have a way to retrieve just the last message???
            #  So instead you get all messages and take the latest one
            response = messages_client.list(
                thread_id=self.thread.id,
            )

            return response.data[0]

        print('Run did not complete successfully.')
        return None

    def upload_visual_prompt_and_get_file_id(self) -> tuple[str, dict[str, Any]]:
        # Files are used to upload documents like images that can be used with features like Assistants
        # Assistants API cannot take base64 images like chat.completions API
        filepath, frame_context = Screen().get_visual_prompt_file()

        with open(filepath, 'rb') as image_file:
            response = self.client.files.create(
                file=image_file,
                purpose='vision',
            )
        return response.id, frame_context

    def format_prompt_package_for_llm(
        self,
        prompt_package: PromptPackage,
        visual_payload: dict[str, Any],
        request_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        openai_screenshot_file_id = str(visual_payload.get('openai_screenshot_file_id') or '').strip()

        content = [
            {
                'type': 'text',
                'text': prompt_package.user_context,
            },
            {
                'type': 'image_file',
                'image_file': {
                    'file_id': openai_screenshot_file_id,
                },
            },
        ]

        return content

    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> dict[str, Any]:
        content_items = getattr(llm_response, 'content', None) or []
        if len(content_items) == 0:
            raise ValueError('模型没有返回任何内容块。')

        first_item = content_items[0]
        text_obj = getattr(first_item, 'text', None)
        llm_response_data = str(getattr(text_obj, 'value', '') or '').strip()
        return self.parse_json_response_text(llm_response_data)

    def cleanup(self):
        # Note: Cannot delete screenshots while the thread is active. Cleanup during shut down.
        for id in self.list_of_image_ids:
            self.client.files.delete(id)
        self.thread = self.client.beta.threads.create()  # Using old thread even by accident would cause Image errors
