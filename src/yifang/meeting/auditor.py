"""安全审计：独立监控全程，分级响应"""

from __future__ import annotations

import json

from yifang.core import call_agent
from yifang.meeting.protocol import AuditAlert, RiskLevel
from yifang.meeting import prompts as P
from yifang.meeting.debug import log_io


class Auditor:
    """安全审计官——独立运行，主控无法解散"""

    def audit(self, content: str) -> AuditAlert:
        """审计内容，返回风险评估"""
        log_io("安全审计", "审计输入", input=content)
        raw = call_agent(P.AUDITOR, content, role="安全审计")
        # raw = '{"risk_level": "low", "reason": "", "recommendation": "继续"}'
        log_io("安全审计", "审计原始输出", output=raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            alert = AuditAlert(
                risk_level=RiskLevel.LOW,
                reason="审计输出解析失败，默认低风险",
                recommendation="继续",
            )
            log_io("安全审计", "JSON 解析失败，默认低风险")
            return alert

        risk_str = data.get("risk_level", "low").lower()
        try:
            risk_level = RiskLevel(risk_str)
        except ValueError:
            risk_level = RiskLevel.LOW

        alert = AuditAlert(
            risk_level=risk_level,
            reason=data.get("reason", ""),
            recommendation=data.get("recommendation", "继续"),
        )

        level_label = {
            RiskLevel.HIGH: "⚠ 高风险",
            RiskLevel.MEDIUM: "⚡ 中风险",
            RiskLevel.LOW: "✓ 低风险",
        }[risk_level]

        log_io(
            "安全审计",
            f"判定: {level_label}",
            output=f"原因: {alert.reason}\n建议: {alert.recommendation}",
        )

        return alert
