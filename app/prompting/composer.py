from prompting.common import format_block


def compose_prompt_text(
    schema_version: str,
    task_context: str,
    execution_timeline: str,
    recent_details: str,
    visual_context: str,
    output_contract: str,
) -> str:
    sections = [
        format_block('PromptSchema', [f'Prompt Schema Version: {schema_version}']),
        task_context,
        execution_timeline,
        recent_details,
        visual_context,
        output_contract,
    ]
    return '\n\n'.join(section for section in sections if str(section).strip() != '')
