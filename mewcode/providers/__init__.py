"""模型 Provider 包。"""


class PromptTooLongError(Exception):
    """哨兵异常：provider 返回的上下文过长错误（F25）。

    Agent 主循环捕获此异常后应触发紧急压缩并重试。
    """
