from __future__ import annotations

from mewcode.conversation import Conversation


def test_conversation_keeps_message_order():
    conversation = Conversation()

    conversation.add_user_message("你好")
    conversation.add_assistant_message("你好，我是 MewCode")
    conversation.add_user_message("记得我刚才说什么了吗？")

    assert [message.role for message in conversation.messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert conversation.messages[0].content == "你好"


def test_snapshot_does_not_mutate_original_list():
    conversation = Conversation()
    conversation.add_user_message("第一句")

    snapshot = conversation.snapshot()
    snapshot.clear()

    assert len(conversation.messages) == 1
    assert conversation.messages[0].content == "第一句"
