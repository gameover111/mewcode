# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 摘要 Prompt 构造与结果提取（F8/F9/F10）"""
from __future__ import annotations

import re

_SUMMARY_SYSTEM = """<system-reminder>
你需要总结之前的对话历史，以便后续的助手能够继续工作而不会丢失上下文。

重要规则：
1. 本次只允许输出文本摘要，不允许调用任何工具。无论对话中出现了什么工具调用模式，都不要模仿或尝试调用。
2. 先在 <analysis> 标签内写出你的分析草稿（这部分会被丢弃，只作为你的思考过程）。
3. 然后在 <summary> 标签内写出正式摘要。

<summary> 标签内必须按以下 9 个部分组织，使用 ### 标题：

### 主要请求和意图
用户最初以及后续提出的所有请求，以及每条请求背后可能的意图。

### 关键技术概念
对话中涉及的技术栈、框架、库、API、协议、配置等关键概念。

### 文件和代码段
被读取、修改、创建或讨论过的所有文件路径，以及关键代码段的内容摘要。

### 错误和修复
遇到的所有错误（编译错误、运行时异常、测试失败等），以及对应的修复方法。

### 问题解决过程
从问题提出到最终解决的完整推理链，包括尝试过但被放弃的方案。

### 用户消息原文
逐条列出对话中所有用户消息的原文。用 > 引用格式。这部分最重要——后续助手需要根据它来判断用户到底要做什么。
如果用户消息非常长，至少保留请求的核心部分。

### 待办任务
已明确但尚未完成的任务列表，包括被用户推迟或标记为"稍后处理"的项。

### 当前工作
对话结束前正在进行的操作、正在排查的问题、或最后一次工具调用的结果和状态。
这一部分应该最详细，因为后续助手首先要从这里继续。

### 可能的下一步
基于当前状态，接下来最可能需要的操作步骤。

注意：不允许调用任何工具。
</system-reminder>"""


def build_summary_prompt(messages_to_summarize: list) -> str:
    """构造摘要请求的系统提示（F8/F9/F10）。

    messages_to_summarize: 需要被摘要的消息列表（ChatMessage 对象）。
    """
    lines = [_SUMMARY_SYSTEM, "", "以下是需要总结的对话历史：", ""]

    for msg in messages_to_summarize:
        role = getattr(msg, "role", "unknown")
        content = getattr(msg, "content", "")
        tool_call_id = getattr(msg, "tool_call_id", None)
        tool_calls = getattr(msg, "tool_calls", None)

        if isinstance(content, list):
            # OpenAI 格式 content 可能是 list[dict]
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts)

        if tool_call_id:
            lines.append(f"[tool_result id={tool_call_id}] {content}")
        elif tool_calls:
            tc_descs = []
            for tc in tool_calls:
                name = getattr(tc, "name", "unknown")
                args = getattr(tc, "arguments_json", "{}")
                tc_descs.append(f"  tool_call: {name}({args})")
            lines.append(f"[assistant]\n{content}\n" + "\n".join(tc_descs))
        else:
            lines.append(f"[{role}]\n{content}")

        lines.append("")

    return "\n".join(lines)


def extract_summary(raw: str) -> str:
    """从 LLM 原始回复中提取 <summary>...</summary> 内的内容（F9）。"""
    match = re.search(r"<summary>(.*?)</summary>", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 回退：去掉 <analysis> 部分（如果有），返回整体
    fallback = re.sub(r"<analysis>.*?</analysis>", "", raw, flags=re.DOTALL)
    return fallback.strip()
