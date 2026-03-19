"""质疑者：永驻角色，在专家发言后、主控决策前提出质疑"""

from __future__ import annotations

from yifang.core import call_agent
from yifang.meeting.protocol import ExpertResponse
from yifang.meeting.debug import log_io


PROMPT = """你是质疑者。

你要对各专家的分析提出质疑。

要求：
- 找出专家发言中的错误假设和逻辑漏洞
- 可以假设用户在撒谎或设计陷阱，寻找是否存在‘自相矛盾’或‘定义冲突’。
- 指出被忽略的重要角度
- 提出具体的反例或反驳论点
- 如果专家的分析没有明显问题，简短说明即可，不要强行质疑
- 输出简洁，直接输出你的质疑"""


class Challenger:
    """质疑者——永驻角色，不受主控管辖"""

    def challenge(self, meeting_context: str, expert_responses: str) -> str:
        """审视专家发言，提出质疑"""
        user_input = (
            f"会议上下文：\n{meeting_context}\n\n本轮专家发言：\n{expert_responses}"
        )
        log_io("质疑者", "审视专家发言", input=user_input)
        response = call_agent(PROMPT, user_input, role="质疑者")
        log_io("质疑者", "质疑完成", output=response)
        return response
