# MewCode 初始对话能力 Plan

## 架构概览
MewCode 本阶段采用分层架构：CLI 入口负责解析启动参数并加载配置，TUI 层负责终端交互和流式展示，会话层负责维护多轮消息历史，Provider 层负责把统一的聊天请求转换为具体模型供应商的流式 API 调用。

配置层读取 YAML 配置文件并校验字段，输出统一的供应商配置对象。配置层只处理配置语义，不发起网络请求。

Provider 层以统一接口暴露“流式生成回复”的行为，上层只消费逐步产生的文本片段。Claude Provider 和 OpenAI Provider 分别处理各自协议、认证头、请求体、SSE 事件解析和错误转换。

TUI 层使用基础终端输入输出实现交互，不引入复杂布局。用户输入后，TUI 把消息交给会话层记录，再调用 Provider 流式生成回复，并将收到的片段立即打印到终端。

## 核心数据结构

### ProviderConfig
```python
@dataclass
class ProviderConfig:
    name: str
    protocol: Literal["anthropic", "openai"]
    model: str
    base_url: str
    api_key: str
    thinking: bool = False
```
表示从 YAML 中读取到的模型供应商配置。`thinking` 默认为 `False`，仅 Claude Provider 使用；OpenAI Provider 忽略该字段。

### ChatMessage
```python
@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str
```
表示一条会话消息。当前阶段只保留用户和助手两种角色，不加入 tool、system、developer 等扩展角色。

### ChatRequest
```python
@dataclass
class ChatRequest:
    messages: list[ChatMessage]
    config: ProviderConfig
```
表示一次模型调用所需的完整输入，包含当前会话历史和当前供应商配置。

### ProviderEvent
```python
@dataclass
class ProviderEvent:
    type: Literal["text", "thinking", "error", "done"]
    content: str = ""
```
表示 Provider 流式返回的事件。TUI 主要打印 `text` 事件；`thinking` 事件用于 Claude extended thinking 的可见输出或后续扩展；`error` 用于向用户展示可理解错误；`done` 表示本轮完成。

### ChatProvider
```python
class ChatProvider(Protocol):
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        ...
```
统一 Provider 接口。每个具体 Provider 都接收统一的 `ChatRequest`，返回统一的 `ProviderEvent` 流。

### Conversation
```python
@dataclass
class Conversation:
    messages: list[ChatMessage]

    def add_user_message(self, content: str) -> None: ...
    def add_assistant_message(self, content: str) -> None: ...
    def snapshot(self) -> list[ChatMessage]: ...
```
保存当前进程内的多轮对话历史。`snapshot` 返回一次调用时的消息副本，避免 Provider 调用过程中修改历史。

## 模块设计

### CLI 入口模块
**职责：** 提供 `python -m mewcode` 启动入口，解析可选配置文件路径，初始化配置、Provider 和 TUI。

**对外接口：**
```python
def main(argv: list[str] | None = None) -> int
```

**依赖：** 配置模块、Provider 工厂、TUI 模块。

### 配置模块
**职责：** 从 YAML 文件读取供应商配置，校验必填字段和协议取值，给出中文错误信息。

**对外接口：**
```python
def load_provider_config(path: str | Path) -> ProviderConfig
```

**依赖：** `yaml` 解析库、标准库路径处理。

### Provider 工厂模块
**职责：** 根据 `ProviderConfig.protocol` 创建对应 Provider；不支持的协议返回明确错误。

**对外接口：**
```python
def create_provider(config: ProviderConfig) -> ChatProvider
```

**依赖：** Claude Provider、OpenAI Provider。

### Claude Provider 模块
**职责：** 使用 Anthropic Claude Messages API 的流式接口发起请求，解析 SSE 流，输出统一的 `ProviderEvent`。当配置启用 `thinking` 时，在请求体中加入 extended thinking 配置。

**对外接口：**
```python
class ClaudeProvider:
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]: ...
```

**依赖：** HTTP 客户端、SSE 解析辅助逻辑、Provider 数据结构。

### OpenAI Provider 模块
**职责：** 使用 OpenAI Chat Completions 或兼容接口的流式能力发起请求，解析 SSE 流，输出统一的 `ProviderEvent`。

**对外接口：**
```python
class OpenAIProvider:
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]: ...
```

**依赖：** HTTP 客户端、SSE 解析辅助逻辑、Provider 数据结构。

### SSE 解析模块
**职责：** 统一处理 HTTP 流中的 SSE 行，解析 `data:` 事件，过滤心跳和结束标记，并把 JSON 数据交给具体 Provider 解读。

**对外接口：**
```python
def iter_sse_data_lines(response: httpx.Response) -> Iterator[str]
```

**依赖：** HTTP 客户端响应对象、JSON 解析由 Provider 自己负责。

### 会话模块
**职责：** 保存当前进程内的多轮对话历史，追加用户消息和助手完整回复。

**对外接口：**
```python
class Conversation:
    def add_user_message(self, content: str) -> None: ...
    def add_assistant_message(self, content: str) -> None: ...
    def snapshot(self) -> list[ChatMessage]: ...
```

**依赖：** Provider 数据结构。

### TUI 模块
**职责：** 显示欢迎信息和输入提示，读取用户输入，调用 Provider 流式输出回复，处理退出命令和用户可理解错误。

**对外接口：**
```python
def run_chat_loop(config: ProviderConfig, provider: ChatProvider) -> int
```

**依赖：** 会话模块、Provider 接口。

## 模块交互
1. 用户执行 `python -m mewcode --config path/to/config.yaml`。
2. CLI 入口解析参数，调用配置模块读取 YAML。
3. CLI 入口把配置传给 Provider 工厂，得到具体 Provider 实例。
4. CLI 入口调用 TUI 模块进入交互循环。
5. TUI 创建空会话，提示用户输入。
6. 用户输入消息后，TUI 将用户消息加入会话。
7. TUI 使用会话快照和配置构造 `ChatRequest`，调用 `provider.stream_chat(...)`。
8. Provider 发起对应协议的 SSE 流式请求，并逐步产出 `ProviderEvent`。
9. TUI 收到 `text` 事件后立即打印；收到 `error` 事件后显示中文错误。
10. 本轮完成后，TUI 将累计的助手文本加入会话，继续等待下一轮输入。

## 文件组织
```text
mewcode/
├── pyproject.toml
├── README.md
├── spec.md
├── plan.md
├── mewcode/
│   ├── __init__.py
│   ├── __main__.py          # python -m mewcode 入口
│   ├── cli.py               # 参数解析与启动编排
│   ├── config.py            # YAML 配置加载与校验
│   ├── conversation.py      # 多轮会话历史
│   ├── tui.py               # 基础交互式终端界面
│   └── providers/
│       ├── __init__.py
│       ├── base.py          # ProviderConfig、ChatMessage、ChatRequest、ProviderEvent、ChatProvider
│       ├── factory.py       # 根据 protocol 创建 Provider
│       ├── anthropic.py     # Claude 流式 Provider
│       ├── openai.py        # OpenAI 流式 Provider
│       └── sse.py           # SSE 数据行解析
├── tests/
│   ├── test_config.py
│   ├── test_conversation.py
│   ├── test_provider_factory.py
│   ├── test_anthropic_provider.py
│   ├── test_openai_provider.py
│   └── test_tui_flow.py
└── examples/
    └── config.example.yaml
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 启动方式 | 支持 `python -m mewcode`，并在项目配置中预留 `mewcode` 控制台命令 | 从零项目先保证无需安装脚本也能启动，同时方便后续发布为命令行工具 |
| TUI 实现 | 使用标准输入输出构建基础交互界面 | 当前阶段只需纯对话和流式输出，避免引入复杂 TUI 框架增加范围 |
| HTTP 客户端 | 使用 `httpx` 同步流式请求 | Python 下流式 HTTP 支持成熟，测试可用 mock transport 替代真实网络 |
| YAML 解析 | 使用 `PyYAML` | 配置格式简单，生态成熟，足够满足本阶段需求 |
| Provider 抽象 | `ChatProvider.stream_chat(ChatRequest) -> Iterator[ProviderEvent]` | TUI 只消费统一事件流，不关心供应商协议细节，满足 F11 |
| SSE 解析 | 抽出共享 SSE 数据行解析，协议事件解释留给具体 Provider | Claude 和 OpenAI 都使用 SSE 风格流，但事件结构不同，共享传输解析、分离业务解析 |
| 会话记忆 | 仅做进程内 `Conversation` 历史 | 满足多轮对话，不引入持久化，符合“不做长期记忆”边界 |
| Claude thinking | 在 Claude Provider 内根据 `thinking` 字段加入请求体配置 | thinking 是 Claude 特有能力，避免泄漏到 TUI 层 |
| 错误处理 | Provider 把网络、认证、协议错误转换为中文错误事件或异常，由 TUI 友好展示 | 满足 F12 和 AC10，避免用户看到原始堆栈 |

## Spec 覆盖检查
- F1: TUI 模块和 CLI 入口覆盖。
- F2: TUI、配置模块、Provider 工厂和 Provider 接口覆盖。
- F3: Provider 流式事件和 TUI 即时打印覆盖。
- F4: Conversation 会话模块覆盖。
- F5: Claude Provider 覆盖。
- F6: OpenAI Provider 覆盖。
- F7-F10: 配置模块和 ProviderConfig 覆盖。
- F11: ChatProvider 统一接口和 Provider 工厂覆盖。
- F12: 配置校验、Provider 错误转换和 TUI 错误展示覆盖。
