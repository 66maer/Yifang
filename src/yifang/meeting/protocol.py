"""入会摘要和会议纪要的数据结构"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    """安全审计风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class BriefingPacket:
    """入会摘要：秘书为新加入的专家准备"""
    task: str
    current_conclusion: str
    open_questions: list[str]
    your_mission: str
    relevant_context: str

    def to_text(self) -> str:
        questions = "\n".join(f"  - {q}" for q in self.open_questions) if self.open_questions else "  (无)"
        return (
            f"任务：{self.task}\n"
            f"目前结论：{self.current_conclusion or '(尚无结论)'}\n"
            f"未解决的问题：\n{questions}\n"
            f"你被召集来解决的具体问题：{self.your_mission}\n"
            f"相关上下文：{self.relevant_context}"
        )


@dataclass
class ExpertResponse:
    """专家发言"""
    expert_name: str
    content: str


@dataclass
class AuditAlert:
    """安全审计告警"""
    risk_level: RiskLevel
    reason: str
    recommendation: str


@dataclass
class ControllerDecision:
    """主控决策"""
    summon: list[str]         # 召集的专家名
    dismiss: list[str]        # 解散的专家名
    action: str               # "continue" / "converge" / "wait_user"
    reasoning: str            # 决策理由


@dataclass
class MeetingRecord:
    """会议纪要"""
    original_task: str
    rounds: list[RoundRecord] = field(default_factory=list)
    final_output: str = ""
    audit_alerts: list[AuditAlert] = field(default_factory=list)


@dataclass
class RoundRecord:
    """单轮会议记录"""
    round_number: int
    controller_decision: ControllerDecision | None = None
    expert_responses: list[ExpertResponse] = field(default_factory=list)
    challenge: str = ""
    secretary_summary: str = ""
    audit_alert: AuditAlert | None = None
