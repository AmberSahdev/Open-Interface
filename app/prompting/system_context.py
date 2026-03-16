from prompting.common import format_block
from prompting.tool_schema import build_tool_schema_text


def build_system_context(base_rules_text: str, schema_version: str, custom_instructions: str = '') -> str:
    lines = [
        f'Prompt Schema Version: {schema_version}',
        base_rules_text.strip(),
    ]

    lines.extend([
        '',
        build_tool_schema_text(),
    ])

    custom_text = str(custom_instructions or '').strip()
    if custom_text != '':
        lines.extend([
            '',
            'Additional Stable Instructions:',
            custom_text,
        ])

    return format_block('PromptSystemContext', lines)
