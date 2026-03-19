"""秘书：管理所有信息流与上下文，主控不接触原文"""

from __future__ import annotations

from yifang.core import call_agent
from yifang.meeting.protocol import (
    ControllerDecision,
    ExpertResponse,
    MeetingRecord,
    RoundRecord,
)
from yifang.meeting import prompts as P
from yifang.meeting.debug import log_io


# 智能模式切换阈值（粗估 1 token ≈ 2 中文字符）
_TOKEN_THRESHOLD = 1000
_CHAR_THRESHOLD = _TOKEN_THRESHOLD * 2


class Secretary:
    """会议秘书"""

    def __init__(self):
        self.record = MeetingRecord(original_task="")

    def intake(self, user_input: str) -> str:
        """接收用户输入。短内容直接透传，长内容 LLM 压缩。"""
        self.record.original_task = user_input

        if len(user_input) < _CHAR_THRESHOLD:
            log_io("秘书", "用户输入较短，直接透传", input=user_input)
            return user_input
        else:
            log_io("秘书", f"用户输入较长（{len(user_input)} 字符），压缩中", input=user_input)
            compressed = call_agent(P.SECRETARY_INTAKE, user_input, role="秘书")
            log_io("秘书", "压缩完成", output=compressed)
            return compressed

    def compress_round(
        self,
        responses: list[ExpertResponse],
        decision: ControllerDecision,
        challenge: str = "",
    ) -> str:
        """轮后压缩：将专家发言 + 质疑者 + 主控决策压缩为下轮上下文。
        如果总量较短，直接拼接返回，跳过 LLM。
        """
        parts = []
        for r in responses:
            parts.append(f"【{r.expert_name}】\n{r.content}")
        if challenge:
            parts.append(f"【质疑者】\n{challenge}")
        parts.append(
            f"【主控决策】\n"
            f"动作: {decision.action}\n"
            f"召集: {decision.summon}\n"
            f"解散: {decision.dismiss}\n"
            f"理由: {decision.reasoning}"
        )
        round_content = "\n\n".join(parts)

        if len(round_content) < _CHAR_THRESHOLD:
            log_io("秘书", "轮后内容较短，跳过压缩", output=round_content)
            return round_content
        else:
            log_io("秘书", f"轮后内容较长（{len(round_content)} 字符），压缩中", input=round_content)
            prompt = P.SECRETARY_ROUND_COMPRESS.format(round_content=round_content)
            compressed = call_agent(prompt, round_content, role="秘书")
            log_io("秘书", "轮后压缩完成", output=compressed)
            return compressed

    def compile_output(self, conclusion: str) -> str:
        """整理最终结论输出给用户"""
        prompt = P.SECRETARY_FINAL.format(
            task=self.record.original_task,
            conclusion=conclusion,
        )
        log_io("秘书", "整理最终输出", input=conclusion)
        output = call_agent(prompt, conclusion, role="秘书")
        self.record.final_output = output
        log_io("秘书", "最终输出完成", output=output)
        return output

    def record_round(self, round_record: RoundRecord) -> None:
        """记录一轮会议"""
        self.record.rounds.append(round_record)

    def _build_meeting_summary(self) -> str:
        """构建当前会议进展摘要"""
        parts = [f"原始任务：{self.record.original_task}"]
        for r in self.record.rounds:
            parts.append(f"\n第 {r.round_number} 轮：")
            if r.secretary_summary:
                parts.append(r.secretary_summary)
        return "\n".join(parts)
