from dataclasses import dataclass
from typing import Any

from prompting.composer import compose_prompt_text
from prompting.constants import PROMPT_SCHEMA_VERSION
from prompting.execution_timeline import build_execution_timeline
from prompting.output_contract import build_output_contract
from prompting.recent_details import build_recent_details
from prompting.system_context import build_system_context
from prompting.task_context import build_task_context
from prompting.visual_context import build_visual_context


@dataclass
class PromptPackage:
    schema_version: str
    system_context: str
    task_context: str
    execution_timeline: str
    recent_details: str
    visual_context: str
    output_contract: str
    user_context: str
    debug_text: str
    metadata: dict[str, Any]


def build_prompt_package(
    *,
    base_system_rules: str,
    custom_instructions: str,
    original_user_request: str,
    step_num: int,
    request_context: dict[str, Any] | None,
    frame_context: dict[str, Any] | None,
    machine_profile: dict[str, Any] | None,
) -> PromptPackage:
    system_context = build_system_context(
        base_rules_text=base_system_rules,
        schema_version=PROMPT_SCHEMA_VERSION,
        custom_instructions=custom_instructions,
    )
    task_context = build_task_context(
        original_user_request=original_user_request,
        step_num=step_num,
        request_context=request_context,
        machine_profile=machine_profile,
    )
    execution_timeline = build_execution_timeline(request_context)
    recent_details = build_recent_details(request_context)
    visual_context = build_visual_context(frame_context)
    output_contract = build_output_contract(PROMPT_SCHEMA_VERSION)
    user_context = compose_prompt_text(
        schema_version=PROMPT_SCHEMA_VERSION,
        task_context=task_context,
        execution_timeline=execution_timeline,
        recent_details=recent_details,
        visual_context=visual_context,
        output_contract=output_contract,
    )
    debug_text = '\n\n'.join([
        system_context,
        user_context,
    ])

    metadata = {
        'request_id': None if not isinstance(request_context, dict) else request_context.get('request_id'),
        'step_num': step_num,
        'schema_version': PROMPT_SCHEMA_VERSION,
    }

    return PromptPackage(
        schema_version=PROMPT_SCHEMA_VERSION,
        system_context=system_context,
        task_context=task_context,
        execution_timeline=execution_timeline,
        recent_details=recent_details,
        visual_context=visual_context,
        output_contract=output_contract,
        user_context=user_context,
        debug_text=debug_text,
        metadata=metadata,
    )
