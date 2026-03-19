"""主控：只做决策，不做内容，不接触原文"""

from __future__ import annotations

import json

from yifang.core import call_agent
from yifang.meeting.protocol import (
    AuditAlert,
    ControllerDecision,
    ExpertResponse,
    RiskLevel,
    RoundRecord,
)
from yifang.meeting.secretary import Secretary
from yifang.meeting.auditor import Auditor
from yifang.meeting.challenger import Challenger
from yifang.meeting.experts import consult_experts_parallel, expert_catalog
from yifang.meeting import prompts as P
from yifang.meeting.debug import log_io


MAX_ROUNDS = 5


class MeetingController:
    """会议主控——召开会议，调度专家，推进讨论"""

    def __init__(self):
        self.secretary = Secretary()
        self.auditor = Auditor()
        self.challenger = Challenger()
        self.active_experts: list[str] = []

    def convene(self, user_input: str) -> str:
        """召开会议：从用户输入到最终输出的完整流程"""
        print("\n[Yifang] ══ 会议召开 ══")

        # 1. 秘书接收用户输入（短透传，长压缩）
        intake_summary = self.secretary.intake(user_input)

        # 2. 安全审计：审计原始输入
        audit_alert = self.auditor.audit(
            f"用户输入：{user_input}\n秘书摘要：{intake_summary}"
        )

        # 高风险：暂停会议，秘书整理后输出
        if audit_alert.risk_level == RiskLevel.HIGH:
            print("[Yifang] ══ 会议暂停（安全审计高风险）══")
            halt_conclusion = (
                f"安全审计判定高风险，会议暂停。\n"
                f"原因：{audit_alert.reason}\n"
                f"建议：{audit_alert.recommendation}"
            )
            return self.secretary.compile_output(halt_conclusion)

        # 3. 主控首轮决策
        controller_input = intake_summary
        if audit_alert.risk_level == RiskLevel.MEDIUM:
            controller_input += f"\n\n[安全审计中风险警告] {audit_alert.reason}"

        decision = self._controller_decide_first(controller_input)

        # 4. 会议循环
        for round_num in range(1, MAX_ROUNDS + 1):
            print(f"\n[Yifang] ── 第 {round_num} 轮 ──")

            round_record = RoundRecord(round_number=round_num)
            round_record.controller_decision = decision

            # 更新在场专家
            self._apply_staffing(decision)

            # 判断是否结束
            if decision.action in ("converge", "wait_user"):
                label = "收敛输出" if decision.action == "converge" else "等待用户输入"
                print(f"[Yifang] 主控决定{label}")
                self.secretary.record_round(round_record)
                break

            # 直接将会议上下文发给在场专家，专家自主分析
            meeting_context = self.secretary._build_meeting_summary()
            briefings = {name: meeting_context for name in self.active_experts}

            # 并行咨询专家
            expert_items = [{"expert": name} for name in self.active_experts]
            responses = consult_experts_parallel(expert_items, briefings)
            round_record.expert_responses = responses

            # 质疑者审视专家发言
            responses_text = self._format_responses(responses)
            challenge = self.challenger.challenge(meeting_context, responses_text)
            round_record.challenge = challenge

            # 安全审计：审计本轮专家发言 + 质疑者意见
            audit_content = f"{responses_text}\n\n【质疑者】\n{challenge}"
            round_audit = self.auditor.audit(audit_content)
            round_record.audit_alert = round_audit

            if round_audit.risk_level == RiskLevel.HIGH:
                print("[Yifang] ══ 会议暂停（安全审计高风险）══")
                self.secretary.record_round(round_record)
                halt_conclusion = (
                    f"安全审计判定高风险，会议暂停。\n"
                    f"原因：{round_audit.reason}\n"
                    f"建议：{round_audit.recommendation}"
                )
                return self.secretary.compile_output(halt_conclusion)

            # 主控基于专家原始发言 + 质疑者意见做决策
            decision = self._controller_decide_followup(
                responses,
                challenge=challenge,
                audit_alert=(
                    round_audit if round_audit.risk_level == RiskLevel.MEDIUM else None
                ),
            )

            # 轮后：秘书压缩专家发言 + 质疑者 + 主控决策 → 下轮上下文
            round_summary = self.secretary.compress_round(
                responses, decision, challenge
            )
            round_record.secretary_summary = round_summary

            self.secretary.record_round(round_record)

        # 5. 秘书整理最终输出
        final_conclusion = self._build_conclusion()
        output = self.secretary.compile_output(final_conclusion)

        print("[Yifang] ══ 会议结束 ══")
        return output

    def _controller_decide_first(self, summary: str) -> ControllerDecision:
        """主控首轮决策"""
        log_io("主控", "首轮决策输入", input=summary)
        prompt = P.CONTROLLER.format(expert_catalog=expert_catalog())
        raw = call_agent(prompt, summary, role="主控")
        log_io("主控", "首轮决策原始输出", output=raw)
        decision = self._parse_decision(raw)
        self._log_decision(decision)
        return decision

    def _controller_decide_followup(
        self,
        responses: list[ExpertResponse],
        *,
        challenge: str = "",
        audit_alert: AuditAlert | None = None,
    ) -> ControllerDecision:
        """主控后续决策：专家原始发言 + 质疑者意见 + 会议历史摘要"""
        responses_text = self._format_responses(responses)
        meeting_summary = self.secretary._build_meeting_summary()

        audit_note = ""
        if audit_alert:
            audit_note = (
                f"[安全审计中风险警告] {audit_alert.reason}\n"
                f"建议：{audit_alert.recommendation}\n"
                "你必须在决策中响应此警告。"
            )

        prompt = P.CONTROLLER_FOLLOWUP.format(
            meeting_summary=meeting_summary,
            active_experts="、".join(self.active_experts) or "(无)",
            expert_responses=responses_text,
            challenge=challenge,
            audit_note=audit_note,
            expert_catalog=expert_catalog(),
        )

        full_input = f"{responses_text}\n\n【质疑者】\n{challenge}"
        log_io(
            "主控",
            "后续决策输入",
            input=f"会议摘要: {meeting_summary}\n在场专家: {', '.join(self.active_experts) or '(无)'}\n专家+质疑者:\n{full_input}",
        )
        raw = call_agent(prompt, full_input, role="主控")
        log_io("主控", "后续决策原始输出", output=raw)
        decision = self._parse_decision(raw)
        self._log_decision(decision)
        return decision

    @staticmethod
    def _format_responses(responses: list[ExpertResponse]) -> str:
        """将专家发言格式化为文本"""
        return "\n\n".join(f"【{r.expert_name}】\n{r.content}" for r in responses)

    @staticmethod
    def _log_decision(decision: ControllerDecision) -> None:
        log_io(
            "主控",
            "决策解析结果",
            output=(
                f"召集: {decision.summon}\n"
                f"解散: {decision.dismiss}\n"
                f"动作: {decision.action}\n"
                f"理由: {decision.reasoning}"
            ),
        )

    def _parse_decision(self, raw: str) -> ControllerDecision:
        """解析主控输出的 JSON 决策"""
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ControllerDecision(
                summon=[],
                dismiss=[],
                action="converge",
                reasoning="决策输出解析失败，默认收敛",
            )

        # 过滤：主控不能解散安全审计
        dismiss = data.get("dismiss", [])
        if "安全审计" in dismiss:
            dismiss.remove("安全审计")
            print("  [主控] 试图解散安全审计，已被拒绝")

        return ControllerDecision(
            summon=data.get("summon", []),
            dismiss=dismiss,
            action=data.get("action", "converge"),
            reasoning=data.get("reasoning", ""),
        )

    def _apply_staffing(self, decision: ControllerDecision) -> None:
        """根据决策更新在场专家"""
        for name in decision.dismiss:
            if name in self.active_experts:
                self.active_experts.remove(name)
                print(f"  [调度] {name} 离场")

        for name in decision.summon:
            if name not in self.active_experts:
                self.active_experts.append(name)
                print(f"  [调度] {name} 入场")

    def _build_conclusion(self) -> str:
        """从会议记录构建结论摘要"""
        parts = []
        for r in self.secretary.record.rounds:
            if r.secretary_summary:
                parts.append(f"第 {r.round_number} 轮摘要：{r.secretary_summary}")
            if r.controller_decision and r.controller_decision.reasoning:
                parts.append(f"主控判断：{r.controller_decision.reasoning}")
        return "\n\n".join(parts) if parts else "(无会议记录)"
