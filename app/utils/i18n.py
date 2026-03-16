from typing import Optional

from utils.settings import Settings


DEFAULT_LANGUAGE = 'zh-CN'
FALLBACK_LANGUAGE = 'en-US'
SUPPORTED_LANGUAGES = ('zh-CN', 'en-US')

LANGUAGE_LABELS = {
    'zh-CN': '简体中文',
    'en-US': 'English',
}

LANGUAGE_ALIASES = {
    'zh': 'zh-CN',
    'zh-cn': 'zh-CN',
    'en': 'en-US',
    'en-us': 'en-US',
}

TRANSLATIONS = {
    'zh-CN': {
        'general.app_title': 'Open Interface',
        'main.heading': '你希望我帮你做什么？',
        'main.session_list': '会话列表',
        'main.new_session_placeholder': '新会话',
        'main.new_session': '新建会话',
        'main.no_sessions': '暂无会话',
        'main.chat_subtitle': '右侧统一展示消息与执行时间线',
        'main.history_title': '统一时间线',
        'main.no_messages': '暂无消息与执行记录',
        'main.input_title': '输入内容',
        'main.runtime_status': '正在运行',
        'main.runtime_idle': '等待新请求',
        'main.runtime_issue_path': '相关路径：{path}',
        'main.runtime_issue_hint': '恢复建议：{hint}',
        'main.runtime_issue_details': '技术细节：{details}',
        'main.session_updated': '最近更新：{updated_at}',
        'main.role.user': '用户',
        'main.role.assistant': '助手',
        'main.role.system': '系统',
        'main.role.status': '状态',
        'main.execution_step_title': '执行步骤 #{step_index}',
        'main.execution_status': '状态：{status}',
        'main.execution_status.started': '进行中',
        'main.execution_status.succeeded': '成功',
        'main.execution_status.failed': '失败',
        'main.execution_status.interrupted': '已中断',
        'main.execution_function': '动作：{function_name}',
        'main.execution_parameters': '参数：{parameters}',
        'main.execution_error': '错误：{error_message}',
        'main.submit': '提交',
        'main.settings': '设置',
        'main.interrupt': '中断',
        'main.restart_request': '重试',
        'main.fetching_instructions': '正在获取操作指令',
        'settings.title': '设置',
        'settings.active_provider': '当前启用 Provider：',
        'settings.provider_activation_help': 'OpenAI、Qwen、Claude 的配置会分别保存；运行时只会启用当前选中的一个 Provider。',
        'settings.provider_type': 'Provider 类型：',
        'settings.provider_api_key': 'API Key：',
        'settings.api_key': 'OpenAI / Gemini / Qwen / Claude API Key：',
        'settings.openai_base_url_help': 'OpenAI 或兼容中转可填写自定义 Base URL，例如 {base_url}；若留空则默认使用官方 OpenAI API。',
        'settings.base_url_help': 'Qwen 可填写 DashScope 兼容 Base URL，例如 {base_url}；若使用视觉代理，建议配合 VL 模型。',
        'settings.base_url_help_claude': 'Claude 可填写 Anthropic 兼容 Base URL，例如 {base_url}；若使用 Claude Code 中转商，通常可直接填写其中转根地址或其 `/v1/` 前缀。',
        'settings.custom_llm_guidance': '自定义 LLM 指引：',
        'settings.play_ding': '完成时播放提示音',
        'settings.disable_local_step_verification': '跳过本地步骤验证',
        'settings.disable_local_step_verification_help': '启用后：步骤执行成功后等待 1 秒，直接继续下一轮，不再做本地截图差分验证。',
        'settings.enable_reasoning': '启用推理',
        'settings.enable_qwen_thinking': '启用 Qwen Thinking',
        'settings.reasoning_depth': '推理深度：',
        'settings.enable_claude_thinking': '启用 Claude Thinking',
        'settings.claude_thinking_budget': 'Claude Thinking Budget Tokens：',
        'settings.claude_thinking_budget_invalid': 'Claude Thinking Budget Tokens 必须是大于 0 的整数。',
        'settings.qwen_model_help': 'Qwen 可优先使用支持图像输入的模型，例如 qwen3.5-plus 或 {model}。若填写纯文本模型，当前桌面代理会直接提示不支持图片输入。',
        'settings.qwen_thinking_help': '该开关会映射到 Qwen 的 `enable_thinking` 参数；推理深度当前仅用于 OpenAI 风格模型。',
        'settings.qwen_thinking_supported': '当前 Qwen 模型支持 `enable_thinking` 开关；推理深度下拉不适用于 Qwen，已自动禁用。',
        'settings.qwen_thinking_unsupported': '当前 Qwen 模型不支持 `enable_thinking`，已自动禁用该开关。',
        'settings.qwen_thinking_required': '当前 Qwen 模型属于仅思考模式，已固定开启思考。',
        'settings.reasoning_depth_openai_only': '推理深度仅对当前 OpenAI 配置生效。',
        'settings.claude_model_help': 'Claude 使用 Anthropic Messages API 兼容格式。推荐从 {model} 开始；如果第三方中转商使用自定义模型别名，可直接在下方输入。',
        'settings.openai_model_help': 'OpenAI / Gemini / 其他 OpenAI 兼容模型可直接在此配置；如果是视觉代理任务，请选择支持图像输入的模型。',
        'settings.claude_reasoning_help': 'Claude provider 当前不使用此开关；系统会直接调用 Anthropic Messages API，不传 OpenAI/Qwen 风格的推理参数。',
        'settings.claude_thinking_help_enabled': 'Claude Thinking 已启用，请填写 `budget_tokens`。系统会按 Anthropic 文档传入 `thinking: {type: enabled, budget_tokens: ...}`。',
        'settings.claude_thinking_help_disabled': 'Claude Thinking 当前关闭。若启用，将按 Anthropic Messages API 传入 `thinking` 参数。',
        'settings.claude_thinking_help_hidden': '当前模型不是 Claude provider，Claude Thinking 设置已隐藏。',
        'settings.model_required': '模型名称不能为空。',
        'settings.provider_model_required': '{provider} 的模型名称不能为空。',
        'settings.request_timeout_seconds': '请求超时时间（秒）：',
        'settings.request_timeout_invalid': '请求超时时间必须是数字。',
        'settings.save_model_prompt_images': '保存发送给模型的最终截图',
        'settings.save_model_prompt_images_help': '会在图片发送给模型之前，保存到项目目录下的 prompt_images/。',
        'settings.save_prompt_text_dumps': '保存最终 Prompt 文本调试文件',
        'settings.save_prompt_text_dumps_help': '默认关闭。开启后会把最终 system/user prompt 文本保存到项目目录下的 promptdump/。',
        'settings.ui_theme': '界面主题：',
        'settings.advanced_settings': '高级设置',
        'settings.save_settings': '保存设置',
        'settings.restart_after_change': '修改设置后请重启应用',
        'settings.theme_apply_after_save': '主题会在保存并关闭设置窗口后应用，以避免下拉框换肤异常。',
        'settings.theme_apply_failed_title': '主题切换失败',
        'settings.theme_apply_failed_message': '无法应用所选主题，已保留当前主题。',
        'settings.theme_apply_failed_hint': '请重新打开设置并选择其他主题，或重启应用后再尝试。',
        'settings.setup_instructions': '安装说明',
        'settings.check_updates': '检查更新',
        'settings.version': '版本：{version}',
        'advanced.title': '高级设置',
        'advanced.select_model': '选择模型：',
        'advanced.older_models_collapsed': '旧模型 ▸',
        'advanced.older_models_expanded': '旧模型 ▾',
        'advanced.custom_model_option': '自定义（在下方填写设置）',
        'advanced.custom_base_url': '自定义 API Base URL',
        'advanced.custom_model_name': '自定义模型名称：',
        'advanced.save_settings': '保存设置',
        'advanced.restart_after_change': '修改设置后请重启应用',
        'advanced.model.gpt54_default': 'GPT-5.4',
        'advanced.model.gpt52_default': 'GPT-5.2（默认）',
        'advanced.model.qwen35_plus': 'Qwen qwen3.5-plus（原生多模态）',
        'advanced.model.qwen_vl_max_latest': 'Qwen qwen-vl-max-latest（推荐视觉）',
        'advanced.model.qwen3_vl_plus': 'Qwen qwen3-vl-plus（视觉）',
        'advanced.model.qwen_plus_latest': 'Qwen qwen-plus-latest（文本）',
        'advanced.model.qwen3_32b': 'Qwen qwen3-32b（文本）',
        'advanced.model.claude_sonnet_46': 'Claude claude-sonnet-4-6（推荐）',
        'advanced.model.claude_opus_46': 'Claude claude-opus-4-6（高质量）',
        'advanced.model.computer_use_preview': 'OpenAI computer-use-preview（GUI 操作）',
        'advanced.model.gemini_3_pro_preview': 'Gemini gemini-3-pro-preview',
        'advanced.model.gemini_3_flash_preview': 'Gemini gemini-3-flash-preview',
        'advanced.model.gpt4o': 'GPT-4o（中等精度，中等速度）',
        'advanced.model.gpt4o_mini': 'GPT-4o-mini（最便宜，最快）',
        'advanced.model.gpt4v': 'GPT-4v（最准确，最慢）',
        'advanced.model.gpt4_turbo': 'GPT-4-Turbo（精度较低，速度较快）',
        'advanced.model.gemini_25_pro': 'Gemini gemini-2.5-pro',
        'advanced.model.gemini_25_flash': 'Gemini gemini-2.5-flash',
        'advanced.model.gemini_25_flash_lite': 'Gemini gemini-2.5-flash-lite',
        'advanced.model.gemini_20_flash': 'Gemini gemini-2.0-flash',
        'advanced.model.gemini_20_flash_lite': 'Gemini gemini-2.0-flash-lite',
        'advanced.model.gemini_20_flash_thinking': 'Gemini gemini-2.0-flash-thinking-exp',
        'advanced.model.gemini_20_pro_exp': 'Gemini gemini-2.0-pro-exp-02-05',
        'core.api_key_missing': '请在“设置”中填写 API Key 后重启应用。',
        'core.api_key_missing_with_error': '请在“设置”中填写 API Key 后重启应用。错误：{error}',
        'core.startup_error': '启动时发生错误。请修复后重启应用。\n问题可能出在文件 {settings_path}。\n错误：{error}',
        'core.startup_error_title': '启动失败',
        'core.config_error_title': '配置文件或模型配置问题',
        'core.config_error_message': '无法初始化模型配置。请检查配置中心中的模型名称、Base URL 与 API Key。',
        'core.config_error_hint': '可在“设置”中修正配置，必要时检查 {settings_path} 后重试。',
        'core.runtime_settings_reloaded': '配置已更新并完成热加载。',
        'core.database_error_title': '会话数据库问题',
        'core.database_startup_error_message': '无法初始化会话数据库，当前会话列表与历史记录不可用。',
        'core.database_runtime_error_message': '会话数据库当前不可用，无法完成该操作。',
        'core.database_error_hint': '请检查应用数据目录是否可写、数据库文件是否损坏，然后重启应用。',
        'core.request_error_title': '请求执行失败',
        'core.request_error_message': '请求执行过程中发生错误，当前会话未能正常完成。',
        'core.request_error_hint': '请检查模型配置或重试；如果问题持续出现，可重启应用后再试。',
        'core.database_operation_error_title': '会话存储失败',
        'core.database_operation_error_hint': '请检查数据库文件与目录权限，必要时备份后修复或删除该数据库文件。',
        'core.model_unavailable_message': '当前模型配置不可用，无法开始新的请求。',
        'core.interrupted': '已中断',
        'core.interrupt_requested': '已请求中断，等待当前模型调用或执行步骤安全结束。',
        'core.invalid_session_id': '无效的会话 ID',
        'core.no_previous_user_request': '当前会话没有可重试的上一条用户请求。',
        'core.requesting_model_initial': '正在采集屏幕并请求模型，请稍候。',
        'core.requesting_model_followup': '正在根据当前状态继续请求模型，请稍候。',
        'core.restarting_last_request': '正在重新执行上一条用户请求。',
        'core.session_not_found': '未找到目标会话',
        'core.unable_to_execute_request': '无法执行该请求',
        'core.exception_unable_to_execute_request': '发生异常：无法执行该请求 - {error}',
        'core.fetching_further_instructions': '正在根据当前状态继续获取后续指令',
        'app.switch_session_failed': '切换会话失败：{error}',
        'app.switch_session_failed_title': '切换会话失败',
        'app.switch_session_failed_message': '无法切换到所选会话。',
        'app.switch_session_failed_hint': '请确认会话仍然存在；如果是数据库异常，请先修复数据库后重试。',
        'app.create_session_failed': '新建会话失败：{error}',
        'app.create_session_failed_title': '新建会话失败',
        'app.create_session_failed_message': '无法创建新的会话。',
        'app.create_session_failed_hint': '请确认应用数据目录可写；如果问题持续出现，请检查数据库文件状态。',
        'app.session_view_hydration_failed_title': '会话视图恢复失败',
        'app.session_view_hydration_failed_message': '应用已启动，但当前无法加载会话列表或历史时间线。',
        'app.session_view_hydration_failed_hint': '请先检查数据库文件是否可读，再重启应用。',
        'llm.context.installed_apps': ' 本机已安装的应用包括 {apps}。',
        'llm.context.operating_system': ' 操作系统是 {os_name}。',
        'llm.context.primary_screen_size': ' 主屏幕尺寸是 {screen_size}。\n',
        'llm.context.custom_info': '\n用户补充说明：{instructions}。',
        'llm.context.response_language': '\n请优先使用简体中文（zh-CN）填写 "human_readable_justification" 与 "done"，但 JSON 键名和函数名保持不变。',
    },
    'en-US': {
        'general.app_title': 'Open Interface',
        'main.heading': 'What would you like me to do?',
        'main.session_list': 'Sessions',
        'main.new_session_placeholder': 'New Session',
        'main.new_session': 'New Session',
        'main.no_sessions': 'No sessions yet',
        'main.chat_subtitle': 'Messages and execution steps share one timeline',
        'main.history_title': 'Timeline',
        'main.no_messages': 'No messages or execution logs yet',
        'main.input_title': 'Your Request',
        'main.runtime_status': 'Running',
        'main.runtime_idle': 'Waiting for a new request',
        'main.runtime_issue_path': 'Related path: {path}',
        'main.runtime_issue_hint': 'Recovery tip: {hint}',
        'main.runtime_issue_details': 'Technical details: {details}',
        'main.session_updated': 'Updated: {updated_at}',
        'main.role.user': 'User',
        'main.role.assistant': 'Assistant',
        'main.role.system': 'System',
        'main.role.status': 'Status',
        'main.execution_step_title': 'Execution Step #{step_index}',
        'main.execution_status': 'Status: {status}',
        'main.execution_status.started': 'In Progress',
        'main.execution_status.succeeded': 'Succeeded',
        'main.execution_status.failed': 'Failed',
        'main.execution_status.interrupted': 'Interrupted',
        'main.execution_function': 'Action: {function_name}',
        'main.execution_parameters': 'Parameters: {parameters}',
        'main.execution_error': 'Error: {error_message}',
        'main.submit': 'Submit',
        'main.settings': 'Settings',
        'main.interrupt': 'Interrupt',
        'main.restart_request': 'Retry',
        'main.fetching_instructions': 'Fetching Instructions',
        'settings.title': 'Settings',
        'settings.active_provider': 'Active Provider:',
        'settings.provider_activation_help': 'OpenAI, Qwen, and Claude are saved separately. Only the currently selected provider is active at runtime.',
        'settings.provider_type': 'Provider Type:',
        'settings.provider_api_key': 'API Key:',
        'settings.api_key': 'OpenAI / Gemini / Qwen / Claude API Key:',
        'settings.openai_base_url_help': 'For OpenAI or compatible proxies, you can enter a custom Base URL such as {base_url}. Leave it empty to use the official OpenAI API.',
        'settings.base_url_help': 'For Qwen, you can enter a DashScope-compatible Base URL such as {base_url}. Use a VL model for the visual desktop agent.',
        'settings.base_url_help_claude': 'For Claude, enter an Anthropic-compatible Base URL such as {base_url}. For Claude Code proxy vendors, you can usually reuse the proxy root URL or its `/v1/` prefix.',
        'settings.custom_llm_guidance': 'Custom LLM Guidance:',
        'settings.play_ding': 'Play Ding on Completion',
        'settings.disable_local_step_verification': 'Skip local step verification',
        'settings.disable_local_step_verification_help': 'When enabled, a successful step waits 1 second and continues directly to the next loop without local screenshot-diff verification.',
        'settings.enable_reasoning': 'Enable Reasoning',
        'settings.enable_qwen_thinking': 'Enable Qwen Thinking',
        'settings.reasoning_depth': 'Reasoning Depth:',
        'settings.enable_claude_thinking': 'Enable Claude Thinking',
        'settings.claude_thinking_budget': 'Claude Thinking Budget Tokens:',
        'settings.claude_thinking_budget_invalid': 'Claude Thinking Budget Tokens must be an integer greater than 0.',
        'settings.qwen_model_help': 'For Qwen, prefer an image-capable model such as qwen3.5-plus or {model}. Text-only models will fail fast because the desktop agent requires image input.',
        'settings.qwen_thinking_help': 'This toggle maps to Qwen `enable_thinking`. Reasoning depth currently applies only to OpenAI-style reasoning models.',
        'settings.qwen_thinking_supported': 'The current Qwen model supports `enable_thinking`. The reasoning depth dropdown does not apply to Qwen and is disabled automatically.',
        'settings.qwen_thinking_unsupported': 'The current Qwen model does not support `enable_thinking`, so the toggle is disabled automatically.',
        'settings.qwen_thinking_required': 'The current Qwen model is reasoning-only, so thinking stays enabled automatically.',
        'settings.reasoning_depth_openai_only': 'Reasoning depth applies only to the current OpenAI configuration.',
        'settings.claude_model_help': 'Claude uses the Anthropic Messages API-compatible format. Start with {model}; if your proxy vendor uses a custom model alias, enter it below.',
        'settings.openai_model_help': 'Configure OpenAI, Gemini, or other OpenAI-compatible models here. For visual desktop tasks, choose a model that supports image input.',
        'settings.claude_reasoning_help': 'The Claude provider does not use this toggle right now. The app calls the Anthropic Messages API directly and does not send OpenAI/Qwen-style reasoning parameters.',
        'settings.claude_thinking_help_enabled': 'Claude Thinking is enabled. Fill in `budget_tokens`; the app will send `thinking: {type: enabled, budget_tokens: ...}` using the Anthropic Messages API format.',
        'settings.claude_thinking_help_disabled': 'Claude Thinking is currently disabled. If enabled, the app will send the Anthropic `thinking` parameter.',
        'settings.claude_thinking_help_hidden': 'The current model is not using the Claude provider, so Claude Thinking settings are hidden.',
        'settings.model_required': 'Model name cannot be empty.',
        'settings.provider_model_required': '{provider} model name cannot be empty.',
        'settings.request_timeout_seconds': 'Request Timeout (seconds):',
        'settings.request_timeout_invalid': 'Request timeout must be a number.',
        'settings.save_model_prompt_images': 'Save final images sent to model',
        'settings.save_model_prompt_images_help': 'Saved under the project folder prompt_images/ before image data is sent to the model.',
        'settings.save_prompt_text_dumps': 'Save final prompt text dumps',
        'settings.save_prompt_text_dumps_help': 'Disabled by default. When enabled, the final system/user prompt text is written under the project folder promptdump/.',
        'settings.ui_theme': 'UI Theme:',
        'settings.advanced_settings': 'Advanced Settings',
        'settings.save_settings': 'Save Settings',
        'settings.restart_after_change': 'Restart the app after any change in settings',
        'settings.theme_apply_after_save': 'The theme will be applied after you save and close Settings to avoid Combobox popdown errors.',
        'settings.theme_apply_failed_title': 'Theme change failed',
        'settings.theme_apply_failed_message': 'Unable to apply the selected theme. The current theme was kept.',
        'settings.theme_apply_failed_hint': 'Open Settings again and try a different theme, or restart the app before retrying.',
        'settings.setup_instructions': 'Setup Instructions',
        'settings.check_updates': 'Check for Updates',
        'settings.version': 'Version: {version}',
        'advanced.title': 'Advanced Settings',
        'advanced.select_model': 'Select Model:',
        'advanced.older_models_collapsed': 'Older Models ▸',
        'advanced.older_models_expanded': 'Older Models ▾',
        'advanced.custom_model_option': 'Custom (Specify Settings Below)',
        'advanced.custom_base_url': 'Custom API Base URL',
        'advanced.custom_model_name': 'Custom Model Name:',
        'advanced.save_settings': 'Save Settings',
        'advanced.restart_after_change': 'Restart the app after any change in settings',
        'advanced.model.gpt54_default': 'GPT-5.4',
        'advanced.model.gpt52_default': 'GPT-5.2 (Default)',
        'advanced.model.qwen35_plus': 'Qwen qwen3.5-plus (Native Multimodal)',
        'advanced.model.qwen_vl_max_latest': 'Qwen qwen-vl-max-latest (Recommended Vision)',
        'advanced.model.qwen3_vl_plus': 'Qwen qwen3-vl-plus (Vision)',
        'advanced.model.qwen_plus_latest': 'Qwen qwen-plus-latest (Text)',
        'advanced.model.qwen3_32b': 'Qwen qwen3-32b (Text)',
        'advanced.model.claude_sonnet_46': 'Claude claude-sonnet-4-6 (Recommended)',
        'advanced.model.claude_opus_46': 'Claude claude-opus-4-6 (Highest Quality)',
        'advanced.model.computer_use_preview': 'OpenAI computer-use-preview (GUI actions)',
        'advanced.model.gemini_3_pro_preview': 'Gemini gemini-3-pro-preview',
        'advanced.model.gemini_3_flash_preview': 'Gemini gemini-3-flash-preview',
        'advanced.model.gpt4o': 'GPT-4o (Medium-Accurate, Medium-Fast)',
        'advanced.model.gpt4o_mini': 'GPT-4o-mini (Cheapest, Fastest)',
        'advanced.model.gpt4v': 'GPT-4v (Most-Accurate, Slowest)',
        'advanced.model.gpt4_turbo': 'GPT-4-Turbo (Least Accurate, Fast)',
        'advanced.model.gemini_25_pro': 'Gemini gemini-2.5-pro',
        'advanced.model.gemini_25_flash': 'Gemini gemini-2.5-flash',
        'advanced.model.gemini_25_flash_lite': 'Gemini gemini-2.5-flash-lite',
        'advanced.model.gemini_20_flash': 'Gemini gemini-2.0-flash',
        'advanced.model.gemini_20_flash_lite': 'Gemini gemini-2.0-flash-lite',
        'advanced.model.gemini_20_flash_thinking': 'Gemini gemini-2.0-flash-thinking-exp',
        'advanced.model.gemini_20_pro_exp': 'Gemini gemini-2.0-pro-exp-02-05',
        'core.api_key_missing': 'Set your API Key in Settings and restart the app.',
        'core.api_key_missing_with_error': 'Set your API Key in Settings and restart the app. Error: {error}',
        'core.startup_error': 'An error occurred during startup. Please fix and restart the app.\nError likely in file {settings_path}.\nError: {error}',
        'core.startup_error_title': 'Startup failed',
        'core.config_error_title': 'Configuration or model setup issue',
        'core.config_error_message': 'Unable to initialize the model configuration. Check the model name, Base URL, and API key in the config center.',
        'core.config_error_hint': 'Update the configuration in Settings, or inspect {settings_path} and retry.',
        'core.runtime_settings_reloaded': 'Configuration updated and hot reloaded.',
        'core.database_error_title': 'Session database issue',
        'core.database_startup_error_message': 'Unable to initialize the session database. Session list and history are currently unavailable.',
        'core.database_runtime_error_message': 'The session database is currently unavailable, so this action could not be completed.',
        'core.database_error_hint': 'Check whether the app data directory is writable and whether the database file is damaged, then restart the app.',
        'core.request_error_title': 'Request execution failed',
        'core.request_error_message': 'An error occurred while processing the request, so the current session could not finish normally.',
        'core.request_error_hint': 'Check the model configuration or try again. If the problem continues, restart the app and retry.',
        'core.database_operation_error_title': 'Session storage failed',
        'core.database_operation_error_hint': 'Check the database file and directory permissions. If needed, back up and repair or delete the database file.',
        'core.model_unavailable_message': 'The current model configuration is unavailable, so a new request cannot start.',
        'core.interrupted': 'Interrupted',
        'core.interrupt_requested': 'Interrupt requested. Waiting for the current model call or execution step to finish safely.',
        'core.invalid_session_id': 'Invalid session ID',
        'core.no_previous_user_request': 'There is no previous user request to retry in the current session.',
        'core.requesting_model_initial': 'Capturing the screen and requesting the model. Please wait.',
        'core.requesting_model_followup': 'Requesting follow-up model instructions based on the current state. Please wait.',
        'core.restarting_last_request': 'Restarting the previous user request.',
        'core.session_not_found': 'Session not found',
        'core.unable_to_execute_request': 'Unable to execute the request',
        'core.exception_unable_to_execute_request': 'Exception: Unable to execute the request - {error}',
        'core.fetching_further_instructions': 'Fetching further instructions based on current state',
        'app.switch_session_failed': 'Failed to switch session: {error}',
        'app.switch_session_failed_title': 'Failed to switch session',
        'app.switch_session_failed_message': 'Unable to switch to the selected session.',
        'app.switch_session_failed_hint': 'Make sure the session still exists. If this is a database issue, repair it before retrying.',
        'app.create_session_failed': 'Failed to create session: {error}',
        'app.create_session_failed_title': 'Failed to create session',
        'app.create_session_failed_message': 'Unable to create a new session.',
        'app.create_session_failed_hint': 'Make sure the app data directory is writable. If the issue continues, check the database file state.',
        'app.session_view_hydration_failed_title': 'Failed to restore session view',
        'app.session_view_hydration_failed_message': 'The app started, but the session list or timeline could not be loaded.',
        'app.session_view_hydration_failed_hint': 'Check whether the database file is readable, then restart the app.',
        'llm.context.installed_apps': ' Locally installed apps are {apps}.',
        'llm.context.operating_system': ' OS is {os_name}.',
        'llm.context.primary_screen_size': ' Primary screen size is {screen_size}.\n',
        'llm.context.custom_info': '\nCustom user-added info: {instructions}.',
        'llm.context.response_language': '\nPreferred response language for "human_readable_justification" and "done" is English (en-US). Keep JSON keys and function names unchanged.',
    },
}


def normalize_language(language: Optional[str]) -> str:
    if language is None:
        return DEFAULT_LANGUAGE

    language_str = str(language).strip()
    if language_str in SUPPORTED_LANGUAGES:
        return language_str

    normalized_language = LANGUAGE_ALIASES.get(language_str.lower(), None)
    if normalized_language in SUPPORTED_LANGUAGES:
        return normalized_language

    return DEFAULT_LANGUAGE


class I18nManager:
    def __init__(self):
        self.current_language = DEFAULT_LANGUAGE
        self.reload_from_settings()

    def reload_from_settings(self) -> str:
        settings_dict = Settings().get_dict()
        appearance_settings = settings_dict.get('appearance')
        language = None
        if isinstance(appearance_settings, dict):
            language = appearance_settings.get('language')
        self.current_language = normalize_language(language)
        return self.current_language

    def get_language(self) -> str:
        return self.current_language

    def set_language(self, language: Optional[str], persist: bool = False) -> str:
        normalized_language = normalize_language(language)
        self.current_language = normalized_language

        if persist:
            Settings().save_settings_to_file({
                'appearance': {
                    'language': normalized_language,
                },
            })

        return normalized_language

    def translate(self, key: str, **kwargs) -> str:
        current_language_dict = TRANSLATIONS.get(self.current_language, {})
        fallback_language_dict = TRANSLATIONS.get(FALLBACK_LANGUAGE, {})

        template = current_language_dict.get(key)
        if template is None:
            template = fallback_language_dict.get(key, key)

        if len(kwargs) == 0:
            return template

        try:
            return template.format(**kwargs)
        except Exception:
            return template


I18N = I18nManager()


def t(key: str, **kwargs) -> str:
    return I18N.translate(key, **kwargs)


def get_current_language() -> str:
    return I18N.get_language()


def set_current_language(language: Optional[str], persist: bool = False) -> str:
    return I18N.set_language(language, persist)


def get_language_label(language: Optional[str]) -> str:
    normalized_language = normalize_language(language)
    return LANGUAGE_LABELS.get(normalized_language, LANGUAGE_LABELS[DEFAULT_LANGUAGE])


def get_language_options() -> list[tuple[str, str]]:
    options = []
    for language_code in SUPPORTED_LANGUAGES:
        options.append((language_code, LANGUAGE_LABELS[language_code]))
    return options
