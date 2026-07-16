# MewCode

MewCode 是一个从零开始构建的终端 AI 编程助手。本阶段只实现纯对话能力：启动终端交互界面、读取 YAML 配置、调用 Claude 或 OpenAI 协议后端，并流式打印模型回复。

## 安装依赖

```bash
python -m pip install -e ".[dev]"
```

## 配置

复制示例配置并按需修改：

```bash
cp examples/config.example.yaml mewcode.yaml
```

配置字段：

- `name`: 供应商标识名。
- `protocol`: 协议，支持 `anthropic` 或 `openai`。
- `model`: 模型名。
- `base_url`: 请求地址。
- `api_key`: API Key。
- `thinking`: 是否启用 Claude extended thinking，可选。

## 启动

```bash
python -m mewcode --config mewcode.yaml
```

也可以在可编辑安装后运行：

```bash
mewcode --config mewcode.yaml
```

在对话中输入 `/exit` 或 `/quit` 退出。

## 当前阶段不做

- 不实现 tool use。
- 不读取、写入或编辑文件。
- 不执行命令。
- 不做长期记忆或会话持久化。
