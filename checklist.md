# MewCode 初始对话能力 Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为。开发完成后必须逐项记录实际结果和证据。

## 实现完整性
- [ ] 用户可以启动 MewCode 并看到中文欢迎信息、当前配置名、输入提示和退出提示（验证：运行 `python -m mewcode --config examples/config.example.yaml`，观察终端首屏输出）。
- [ ] 用户可以连续输入多轮消息，程序不会在第一轮回复后退出（验证：在交互界面输入两条消息，观察第二次仍出现输入提示）。
- [ ] 模型回复以流式片段打印，而不是等待完整回复后一次性出现（验证：使用测试 Provider 或真实 API 输入问题，观察回复在生成过程中分段出现）。
- [ ] 同一会话内第二轮请求包含第一轮用户消息和助手回复（验证：运行 `pytest tests/test_tui_flow.py`，观察多轮上下文测试通过）。
- [ ] Claude 协议配置可以创建 Claude Provider 并发起流式请求（验证：运行 `pytest tests/test_provider_factory.py tests/test_anthropic_provider.py`，观察测试通过）。
- [ ] OpenAI 协议配置可以创建 OpenAI Provider 并发起流式请求（验证：运行 `pytest tests/test_provider_factory.py tests/test_openai_provider.py`，观察测试通过）。
- [ ] YAML 配置中的 `name`、`protocol`、`model`、`base_url`、`api_key` 字段被正确读取并用于请求（验证：运行 `pytest tests/test_config.py tests/test_anthropic_provider.py tests/test_openai_provider.py`，观察字段断言通过）。
- [ ] YAML 配置缺省 `thinking` 字段时仍能正常加载，且默认关闭 extended thinking（验证：运行 `pytest tests/test_config.py`，观察缺省 thinking 用例通过）。
- [ ] Claude 配置启用 `thinking` 时，请求体包含 extended thinking 配置（验证：运行 `pytest tests/test_anthropic_provider.py`，观察 thinking 请求体用例通过）。
- [ ] Provider 层对 TUI 暴露统一事件流，TUI 不依赖 Claude 或 OpenAI 的具体事件结构（验证：运行 `pytest tests/test_tui_flow.py`，观察假 Provider 驱动的 TUI 测试通过）。
- [ ] 不支持的 `protocol` 会显示中文错误，说明协议不受支持（验证：使用含非法 protocol 的配置运行 `python -m mewcode --config <bad-config>`，观察错误信息）。
- [ ] API 调用失败时显示中文失败信息，主界面不直接把 Python 异常堆栈作为回复展示（验证：运行 Provider 错误测试或使用无效 API 地址启动并提问，观察中文错误输出）。

## 集成
- [ ] CLI 能通过 `--config` 指定配置文件并进入 TUI（验证：运行 `python -m mewcode --config examples/config.example.yaml`，观察进入交互界面）。
- [ ] CLI 默认读取 `mewcode.yaml`，缺失时给出中文错误并返回非零退出码（验证：在没有 `mewcode.yaml` 的目录运行 `python -m mewcode`，观察错误和退出码）。
- [ ] `python -m mewcode --help` 显示 `--config` 参数说明（验证：运行命令并观察帮助文本）。
- [ ] `mewcode` 控制台入口指向同一套 CLI 编排逻辑（验证：安装为可编辑包后运行 `mewcode --help`，观察与 `python -m mewcode --help` 等价）。
- [ ] 配置模块、Provider 工厂、TUI、会话模块可以串联完成一轮对话（验证：运行 `pytest tests/test_tui_flow.py`，观察集成用例通过）。
- [ ] SSE 解析可以处理普通 data 行、空行、注释行和连续事件（验证：运行 `pytest tests/test_sse.py`，观察测试通过）。
- [ ] README 和示例配置覆盖 Anthropic Claude、OpenAI、退出命令和本阶段不做事项（验证：阅读 `README.md` 和 `examples/config.example.yaml`，确认信息存在）。

## 编译与测试
- [ ] 项目 Python 文件全部可编译（验证：运行 `python -m compileall mewcode`，期望无错误）。
- [ ] 配置加载测试全部通过（验证：运行 `pytest tests/test_config.py`，期望通过）。
- [ ] 会话历史测试全部通过（验证：运行 `pytest tests/test_conversation.py`，期望通过）。
- [ ] Provider 工厂测试全部通过（验证：运行 `pytest tests/test_provider_factory.py`，期望通过）。
- [ ] SSE 解析测试全部通过（验证：运行 `pytest tests/test_sse.py`，期望通过）。
- [ ] Claude Provider 测试全部通过（验证：运行 `pytest tests/test_anthropic_provider.py`，期望通过）。
- [ ] OpenAI Provider 测试全部通过（验证：运行 `pytest tests/test_openai_provider.py`，期望通过）。
- [ ] TUI 流程测试全部通过（验证：运行 `pytest tests/test_tui_flow.py`，期望通过）。
- [ ] 全量测试全部通过（验证：运行 `pytest`，期望通过）。

## 端到端场景
- [ ] 场景 1：在 tmux 中启动 MewCode，输入“你好，请用一句话介绍你自己”，观察 MewCode 以流式方式输出中文回复，并回到输入提示（验证：tmux 捕获窗格输出，确认有欢迎信息、用户输入、分段回复和下一轮提示）。
- [ ] 场景 2：在同一个 tmux 会话中继续输入“我刚才问你的第一句话是什么？”，观察回复能引用上一轮内容，证明多轮上下文生效（验证：tmux 捕获窗格输出，确认回复提到第一轮问题）。
- [ ] 场景 3：使用 OpenAI 协议配置启动 MewCode，输入一条真实问题，观察回复流式输出且无协议错误（验证：tmux 捕获窗格输出，确认模型回复逐步出现）。
- [ ] 场景 4：使用 Claude 协议配置并启用 `thinking` 启动 MewCode，输入一条真实问题，观察请求成功且正文正常流式输出（验证：tmux 捕获窗格输出，确认没有配置错误或协议错误）。
- [ ] 场景 5：使用非法 `protocol` 配置启动 MewCode，观察程序显示中文错误并明确退出（验证：tmux 或普通终端运行，确认错误包含“不支持”含义且退出码非零）。
- [ ] 场景 6：启动 MewCode 后输入 `/exit`，观察程序显示退出信息并结束进程（验证：tmux 捕获窗格输出，确认会话结束）。

## Spec 对齐
- [ ] AC1 已覆盖：启动后看到交互式输入提示并可输入第一条消息（验证：端到端场景 1）。
- [ ] AC2 已覆盖：Claude 配置真实调用并流式显示回复（验证：端到端场景 4）。
- [ ] AC3 已覆盖：OpenAI 配置真实调用并流式显示回复（验证：端到端场景 3）。
- [ ] AC4 已覆盖：同一会话第二轮引用第一轮内容（验证：端到端场景 2）。
- [ ] AC5 已覆盖：流式输出可观察（验证：实现完整性流式条目和端到端场景 1）。
- [ ] AC6 已覆盖：五个必填配置字段被读取并用于请求（验证：配置和 Provider 测试）。
- [ ] AC7 已覆盖：`thinking` 缺省时正常普通对话（验证：配置测试和普通 Provider 测试）。
- [ ] AC8 已覆盖：Claude thinking 请求配置生效（验证：Claude Provider 测试和端到端场景 4）。
- [ ] AC9 已覆盖：不支持协议显示明确错误（验证：实现完整性错误条目和端到端场景 5）。
- [ ] AC10 已覆盖：API 调用失败显示可理解错误（验证：实现完整性 API 失败条目）。
- [ ] AC11 已覆盖：TUI 可在不修改对话流程的前提下切换 Provider（验证：Provider 工厂和 TUI 测试）。
- [ ] AC12 已覆盖：tmux 中执行端到端测试并对照本 checklist 验收（验证：端到端场景 1-6）。
