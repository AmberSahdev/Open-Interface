from prompting.common import format_block


def build_output_contract(schema_version: str) -> str:
    lines = [
        f'Prompt Schema Version: {schema_version}',
        'Return strict JSON only. No markdown fences. No extra prose.',
        'Return exactly these top-level keys: steps, done.',
        'Return at most one executable step inside steps.',
        'Each step object must include exactly these keys: function, parameters, human_readable_justification, expected_outcome.',
        'done must be null until the task is complete or must stop safely.',
        'If the task is complete, blocked, or unsafe, return steps as [] and explain briefly in done.',
        'Output Example:',
        '{',
        '  "steps": [',
        '    {',
        '      "function": "click",',
        '      "parameters": {"x_percent": 31.5, "y_percent": 44.2, "button": "left", "clicks": 1},',
        '      "human_readable_justification": "点击当前最可能的输入区域以建立焦点。",',
        '      "expected_outcome": "光标进入输入框，或界面出现可见焦点状态。"',
        '    }',
        '  ],',
        '  "done": null',
        '}',
    ]
    return format_block('PromptOutputContract', lines)
