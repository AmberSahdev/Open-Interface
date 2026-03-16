from dataclasses import dataclass, field

from prompting.common import format_block


@dataclass(frozen=True)
class ToolParameterDefinition:
    name: str
    description: str
    required: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: tuple[ToolParameterDefinition, ...] = ()
    usage_rules: tuple[str, ...] = ()


@dataclass
class ToolRegistry:
    tools: list[ToolDefinition] = field(default_factory=list)

    def register(self, tool_definition: ToolDefinition) -> None:
        normalized_name = tool_definition.name.strip()
        if normalized_name == '':
            raise ValueError('Tool name cannot be empty.')

        for existing_tool in self.tools:
            if existing_tool.name == normalized_name:
                raise ValueError(f'Duplicate tool name: {normalized_name}')

        self.tools.append(tool_definition)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self.tools)


def build_tool_schema_text(tool_registry: ToolRegistry | None = None) -> str:
    registry = tool_registry or get_default_tool_registry()
    lines = [
        'Use only the registered tools below.',
        'Do not invent new function names.',
        'Do not invent new parameter names.',
        'Return exactly one tool call per response unless you must stop safely with done.',
    ]

    for tool_definition in registry.list_tools():
        lines.append('')
        lines.append(f'Tool: {tool_definition.name}')
        lines.append(f'- Description: {tool_definition.description}')

        required_parameters = [
            parameter.name for parameter in tool_definition.parameters if parameter.required
        ]
        optional_parameters = [
            parameter.name for parameter in tool_definition.parameters if not parameter.required
        ]

        if len(required_parameters) == 0:
            lines.append('- Required Parameters: none')
        else:
            lines.append(f'- Required Parameters: {", ".join(required_parameters)}')

        if len(optional_parameters) == 0:
            lines.append('- Optional Parameters: none')
        else:
            lines.append(f'- Optional Parameters: {", ".join(optional_parameters)}')

        if len(tool_definition.parameters) > 0:
            lines.append('- Parameter Notes:')
            for parameter in tool_definition.parameters:
                required_flag = 'required' if parameter.required else 'optional'
                lines.append(f'  - {parameter.name} ({required_flag}): {parameter.description}')

        if len(tool_definition.usage_rules) > 0:
            lines.append('- Usage Rules:')
            for usage_rule in tool_definition.usage_rules:
                lines.append(f'  - {usage_rule}')

    return format_block('PromptToolSchema', lines)


def get_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(ToolDefinition(
        name='click',
        description='Click a target on the current screen.',
        parameters=(
            ToolParameterDefinition('x_percent', 'Target X position in the visible ruler scale [0, 100].'),
            ToolParameterDefinition('y_percent', 'Target Y position in the visible ruler scale [0, 100].'),
            ToolParameterDefinition('target_anchor_id', 'Stable target anchor id from the current runtime context.'),
            ToolParameterDefinition('button', 'Mouse button such as left, right, or middle.'),
            ToolParameterDefinition('clicks', 'Number of clicks to perform.'),
            ToolParameterDefinition('interval', 'Delay between repeated clicks in seconds.'),
        ),
        usage_rules=(
            'Provide target_anchor_id or provide both x_percent and y_percent.',
            'When you use x_percent and y_percent, return the same 0-100 values shown by the rulers. Do not divide by 100 yourself.',
            'Use button=left unless a different button is clearly required.',
            'Use clicks=1 unless you intentionally need a multi-click action.',
        ),
    ))

    registry.register(ToolDefinition(
        name='moveTo',
        description='Move the pointer to a target position without clicking.',
        parameters=(
            ToolParameterDefinition('x_percent', 'Target X position in the visible ruler scale [0, 100].'),
            ToolParameterDefinition('y_percent', 'Target Y position in the visible ruler scale [0, 100].'),
            ToolParameterDefinition('target_anchor_id', 'Stable target anchor id from the current runtime context.'),
            ToolParameterDefinition('duration', 'Pointer move duration in seconds.'),
        ),
        usage_rules=(
            'Provide target_anchor_id or provide both x_percent and y_percent.',
            'When you use x_percent and y_percent, return the same 0-100 values shown by the rulers. Do not divide by 100 yourself.',
        ),
    ))

    registry.register(ToolDefinition(
        name='dragTo',
        description='Drag from the current pointer position to a target position.',
        parameters=(
            ToolParameterDefinition('x_percent', 'Target X position in the visible ruler scale [0, 100].'),
            ToolParameterDefinition('y_percent', 'Target Y position in the visible ruler scale [0, 100].'),
            ToolParameterDefinition('target_anchor_id', 'Stable target anchor id from the current runtime context.'),
            ToolParameterDefinition('button', 'Mouse button used for the drag.'),
            ToolParameterDefinition('duration', 'Drag duration in seconds.'),
        ),
        usage_rules=(
            'Provide target_anchor_id or provide both x_percent and y_percent.',
            'When you use x_percent and y_percent, return the same 0-100 values shown by the rulers. Do not divide by 100 yourself.',
            'Use button=left unless a different drag button is clearly required.',
        ),
    ))

    registry.register(ToolDefinition(
        name='write',
        description='Type or paste text into the currently focused input.',
        parameters=(
            ToolParameterDefinition('text', 'Text content to enter.', required=True),
            ToolParameterDefinition('interval', 'Delay between characters in seconds.'),
        ),
        usage_rules=(
            'Use this only when the target input already has focus.',
            'Use text as the only content field. Do not use string, message, or typewrite.',
        ),
    ))

    registry.register(ToolDefinition(
        name='press',
        description='Press one key or a repeated single key sequence.',
        parameters=(
            ToolParameterDefinition('key', 'Single key name to press.'),
            ToolParameterDefinition('keys', 'Single key name or a list of key names when the runtime supports a repeated press pattern.'),
            ToolParameterDefinition('presses', 'Number of repeated presses.'),
            ToolParameterDefinition('interval', 'Delay between repeated presses in seconds.'),
        ),
        usage_rules=(
            'Provide key for a single key press.',
            'Use presses only when repeating the same key sequence is necessary.',
        ),
    ))

    registry.register(ToolDefinition(
        name='scroll',
        description='Scroll the current view vertically.',
        parameters=(
            ToolParameterDefinition('clicks', 'Positive or negative scroll amount.', required=True),
        ),
        usage_rules=(
            'Use positive or negative clicks according to the required direction.',
        ),
    ))

    registry.register(ToolDefinition(
        name='sleep',
        description='Wait for the UI to update before the next observation.',
        parameters=(
            ToolParameterDefinition('secs', 'Number of seconds to wait.', required=True),
        ),
        usage_rules=(
            'Use this only when the UI likely needs time to update or load.',
        ),
    ))

    return registry
