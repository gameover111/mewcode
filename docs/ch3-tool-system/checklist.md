# MewCode ch3 工具系统 Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为。开发完成后必须逐项记录实际结果和证据。

## 实现完整性
- [ ] 工具基础接口已实现，成功和失败工具都会返回 `ToolResult`（验证：运行 `pytest tests/test_tools_base.py`，观察通过）。
- [ ] 工作区路径解析会拒绝 `..` 越界路径和工作区外绝对路径（验证：运行 `pytest tests/test_tools_security.py`，观察越界用例通过）。
- [ ] `.env` 和常见密钥文件默认不可被工具读取或写入（验证：运行 `pytest tests/test_tools_security.py tests/test_tools_file.py`，观察隐私文件用例通过）。
- [ ] 读文件工具能读取工作区内文本文件，并返回 `path`、`content`、`truncated` 字段（验证：运行 `pytest tests/test_tools_file.py -k read`，观察通过）。
- [ ] 写文件工具能在工作区内创建和覆盖文本文件（验证：运行 `pytest tests/test_tools_file.py -k write`，观察通过并检查测试文件内容）。
- [ ] 改文件工具只在原文唯一匹配时替换（验证：运行 `pytest tests/test_tools_file.py -k replace`，观察唯一匹配、零匹配、多匹配用例通过）。
- [ ] 执行命令工具返回退出码、stdout、stderr，并在超时时返回结构化错误（验证：运行 `pytest tests/test_tools_command.py`，观察通过）。
- [ ] 按模式找文件工具返回工作区内匹配文件，并跳过缓存目录（验证：运行 `pytest tests/test_tools_search.py -k find`，观察通过）。
- [ ] 搜代码内容工具返回匹配文件、行号和匹配行内容（验证：运行 `pytest tests/test_tools_search.py -k search`，观察通过）。
- [ ] 工具注册中心默认登记六个核心工具并能按名查找（验证：运行 `pytest tests/test_tools_registry.py`，观察默认工具数量和名称断言通过）。
- [ ] 注册中心输出的 OpenAI-compatible 工具定义包含名称、描述和 JSON Schema 参数定义（验证：运行 `pytest tests/test_tools_registry.py`，观察工具定义格式断言通过）。
- [ ] OpenAI Provider 请求体在有工具时包含 `tools` 和 `tool_choice`（验证：运行 `pytest tests/test_openai_tool_calls.py`，观察请求体断言通过）。
- [ ] OpenAI Provider 能把流式工具调用参数碎片拼接成完整 JSON 字符串（验证：运行 `pytest tests/test_openai_tool_calls.py`，观察碎片拼接用例通过）。
- [ ] Agent 能执行一次模型请求的已知工具，并把结果回灌进会话（验证：运行 `pytest tests/test_agent_tool_flow.py`，观察成功工具调用用例通过）。
- [ ] Agent 对未知工具和无效 JSON 参数返回结构化错误，不会崩溃（验证：运行 `pytest tests/test_agent_tool_flow.py`，观察错误分支用例通过）。
- [ ] Agent 在工具结果回灌后只生成最终回复，不进入第二次工具执行（验证：运行 `pytest tests/test_agent_tool_flow.py`，观察“第二次仍请求工具”用例通过）。

## 集成
- [ ] 纯对话路径保持兼容，模型不请求工具时仍直接流式输出回复（验证：运行 `pytest tests/test_agent_tool_flow.py tests/test_tui_flow.py`，观察纯对话用例通过）。
- [ ] TUI 能显示工具开始和工具结果状态提示（验证：运行 `pytest tests/test_tui_flow.py`，观察工具状态输出断言通过）。
- [ ] TUI 使用当前工作区作为工具执行边界（验证：运行 `pytest tests/test_tui_flow.py tests/test_agent_tool_flow.py`，观察 ToolContext workspace 断言通过）。
- [ ] Conversation 能保存 assistant 工具调用消息和 tool 结果消息（验证：运行 `pytest tests/test_conversation.py tests/test_agent_tool_flow.py`，观察消息结构断言通过）。
- [ ] 本地 SSE 假服务能模拟 OpenAI-compatible 工具调用完整流程：首轮工具调用、执行工具、第二轮最终回复（验证：运行 `pytest tests/test_agent_tool_flow.py`，观察端到端替代测试通过）。

## 编译与测试
- [ ] 项目 Python 文件全部可编译（验证：运行 `python -m compileall mewcode`，期望无错误）。
- [ ] 工具基础测试通过（验证：运行 `pytest tests/test_tools_base.py`，期望通过）。
- [ ] 工具安全测试通过（验证：运行 `pytest tests/test_tools_security.py`，期望通过）。
- [ ] 文件工具测试通过（验证：运行 `pytest tests/test_tools_file.py`，期望通过）。
- [ ] 搜索工具测试通过（验证：运行 `pytest tests/test_tools_search.py`，期望通过）。
- [ ] 命令工具测试通过（验证：运行 `pytest tests/test_tools_command.py`，期望通过）。
- [ ] 工具注册中心测试通过（验证：运行 `pytest tests/test_tools_registry.py`，期望通过）。
- [ ] OpenAI 工具调用解析测试通过（验证：运行 `pytest tests/test_openai_tool_calls.py`，期望通过）。
- [ ] Agent 工具流测试通过（验证：运行 `pytest tests/test_agent_tool_flow.py`，期望通过）。
- [ ] 原有 Provider、配置、会话、TUI 回归测试通过（验证：运行 `pytest tests/test_config.py tests/test_openai_provider.py tests/test_tui_flow.py`，期望通过）。
- [ ] 全量测试通过（验证：运行 `pytest`，期望通过）。

## 端到端场景
- [ ] 场景 1：用户要求“读取 README.md 并总结”，模型触发读文件工具，MewCode 执行工具并输出最终总结（验证：使用 DeepSeek 或本地 SSE 假服务启动 MewCode，观察工具状态和最终回复）。
- [ ] 场景 2：用户要求“把临时文件中的 old 改成 new”，模型触发改文件工具，文件内容被正确替换（验证：运行端到端请求后读取临时文件，确认内容改变）。
- [ ] 场景 3：用户要求“查找 tests 目录下的 test_*.py”，模型触发按模式找文件工具，最终回复包含匹配文件摘要（验证：观察工具结果和最终回复）。
- [ ] 场景 4：用户要求“搜索 ProviderEvent 在哪里出现”，模型触发搜代码内容工具，最终回复包含文件和行号摘要（验证：观察工具结果和最终回复）。
- [ ] 场景 5：用户要求“运行 python -m compileall mewcode”，模型触发执行命令工具，最终回复包含退出码和输出摘要（验证：观察工具结果中的退出码为 0）。
- [ ] 场景 6：用户要求读取 `.env`，工具返回拒绝访问，模型最终回复说明无法读取隐私文件（验证：观察结构化错误和最终回复）。
- [ ] 场景 7：模型在第二轮最终回复中再次请求工具时，MewCode 不执行第二个工具，并提示本章不支持自动循环（验证：本地 SSE 假服务模拟第二轮工具调用，观察错误事件）。

## Spec 对齐
- [ ] AC1 已覆盖：注册中心登记六个核心工具并可按名查找（验证：工具注册中心测试）。
- [ ] AC2 已覆盖：OpenAI-compatible 工具定义格式正确（验证：工具注册中心测试）。
- [ ] AC3 已覆盖：读文件工具读取工作区文本并拒绝 `.env` / 越界路径（验证：文件工具和安全测试）。
- [ ] AC4 已覆盖：写文件工具创建或覆盖文本文件（验证：文件工具测试）。
- [ ] AC5 已覆盖：改文件唯一匹配替换和清楚错误（验证：文件工具测试）。
- [ ] AC6 已覆盖：执行命令工具返回退出码、stdout、stderr 和超时错误（验证：命令工具测试）。
- [ ] AC7 已覆盖：按 glob 找文件（验证：搜索工具测试）。
- [ ] AC8 已覆盖：搜代码内容返回路径、行号、匹配行（验证：搜索工具测试）。
- [ ] AC9 已覆盖：工具异常被包装成结构化失败结果（验证：工具基础测试）。
- [ ] AC10 已覆盖：流式工具调用 JSON 参数碎片可拼接（验证：OpenAI 工具调用测试）。
- [ ] AC11 已覆盖：模型请求工具后执行并回灌，再流式输出最终回复（验证：Agent 工具流测试和端到端场景 1）。
- [ ] AC12 已覆盖：无工具调用时保持纯对话（验证：Agent 和 TUI 回归测试）。
- [ ] AC13 已覆盖：未知工具或无效 JSON 参数返回结构化错误并生成最终回复（验证：Agent 工具流测试）。
- [ ] AC14 已覆盖：查看项目文件端到端触发读文件工具（验证：端到端场景 1）。
- [ ] AC15 已覆盖：修改文件端到端触发改文件工具并改动文件（验证：端到端场景 2）。
- [ ] AC16 已覆盖：最多执行一次工具调用回合（验证：Agent 工具流测试和端到端场景 7）。
