# MewCode

MewCode 是一个从零开始构建的终端 AI 编程助手。当前支持启动终端交互界面、读取 YAML 配置、调用 OpenAI-compatible 或 Claude 协议后端，并流式打印模型回复。

当前版本已经加入工具系统。模型可以在一次回复中请求一个本地工具，MewCode 执行工具后把结构化结果回灌给模型，再输出最终回复。

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

## Agent Loop (ch4)

MewCode 现在支持 ReAct 风格的 Agent Loop：模型可以自动多轮调用工具，直到任务完成。

- --max-rounds N: 设置最大循环轮数（默认 8）。
- --plan-only: 只允许读类工具（read_file、find_files、search_code），写类工具（write_file、replace_in_file、run_command）被拦截，最终输出计划供用户审批。
- --timeout SECONDS: 设置整体超时秒数。

示例：

`ash
# 正常执行（自动多轮循环）
python -m mewcode --config mewcode.yaml

# plan-only 模式
python -m mewcode --config mewcode.yaml --plan-only

# 限制最大轮数
python -m mewcode --config mewcode.yaml --max-rounds 3

# 限制整体超时 60 秒
python -m mewcode --config mewcode.yaml --timeout 60
`

## 工具系统

内置工具：

- `read_file`: 读取工作区内文本文件。
- `write_file`: 写入工作区内文本文件。
- `replace_in_file`: 只在原文唯一匹配时替换文本。
- `run_command`: 在工作区内执行一次命令。
- `find_files`: 按 glob 模式查找文件。
- `search_code`: 搜索代码内容。

安全边界：

- 文件、搜索和命令工作目录默认限制在当前工作区内。
- 默认拒绝访问 `.env` 等隐私文件。
- 工具输出会截断，避免把过大内容塞进模型上下文。
