"""会议架构测试"""

import json

from yifang.meeting.protocol import (
    AuditAlert,
    BriefingPacket,
    ControllerDecision,
    ExpertResponse,
    MeetingRecord,
    RiskLevel,
    RoundRecord,
)
from yifang.meeting.auditor import Auditor
from yifang.meeting.secretary import Secretary
from yifang.meeting.experts import available_experts, get_expert, expert_catalog
from yifang.meeting.controller import MeetingController


# ── protocol 测试 ───────────────────────────────────────────


class TestBriefingPacket:
    def test_to_text(self):
        bp = BriefingPacket(
            task="分析问题",
            current_conclusion="初步结论",
            open_questions=["问题1", "问题2"],
            your_mission="找漏洞",
            relevant_context="背景信息",
        )
        text = bp.to_text()
        assert "分析问题" in text
        assert "初步结论" in text
        assert "问题1" in text
        assert "找漏洞" in text

    def test_to_text_no_questions(self):
        bp = BriefingPacket(
            task="简单任务",
            current_conclusion="",
            open_questions=[],
            your_mission="做事",
            relevant_context="无",
        )
        text = bp.to_text()
        assert "(无)" in text
        assert "(尚无结论)" in text


class TestRiskLevel:
    def test_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"


class TestControllerDecision:
    def test_creation(self):
        d = ControllerDecision(
            summon=["质疑者"],
            dismiss=["领域通才"],
            action="continue",
            reasoning="需要深入分析",
        )
        assert d.summon == ["质疑者"]
        assert d.action == "continue"


class TestMeetingRecord:
    def test_creation(self):
        record = MeetingRecord(original_task="测试任务")
        assert record.original_task == "测试任务"
        assert record.rounds == []
        assert record.final_output == ""


# ── experts 测试 ────────────────────────────────────────────


class TestExperts:
    def test_available_experts(self):
        experts = available_experts()
        names = [e.name for e in experts]
        assert "常识推理专家" in names
        assert "风险官" in names
        assert "伦理顾问" in names
        assert "领域通才" in names
        assert len(experts) == 4
        # 质疑者已升级为永驻角色，不在专家池中
        assert "质疑者" not in names

    def test_get_expert_known(self):
        expert = get_expert("风险官")
        assert expert is not None
        assert expert.name == "风险官"
        assert "风险" in expert.focus

    def test_get_expert_unknown(self):
        expert = get_expert("不存在的专家")
        assert expert is None

    def test_expert_catalog(self):
        catalog = expert_catalog()
        assert "常识推理专家" in catalog
        assert "风险官" in catalog
        assert "质疑者" not in catalog


# ── auditor 测试 ────────────────────────────────────────────


class TestAuditor:
    def test_parse_low_risk(self, mocker):
        mocker.patch(
            "yifang.meeting.auditor.call_agent",
            return_value=json.dumps({
                "risk_level": "low",
                "reason": "无风险",
                "recommendation": "继续",
            }),
        )
        auditor = Auditor()
        alert = auditor.audit("测试内容")
        assert alert.risk_level == RiskLevel.LOW

    def test_parse_high_risk(self, mocker):
        mocker.patch(
            "yifang.meeting.auditor.call_agent",
            return_value=json.dumps({
                "risk_level": "high",
                "reason": "发现恶意内容",
                "recommendation": "暂停",
            }),
        )
        auditor = Auditor()
        alert = auditor.audit("恶意内容")
        assert alert.risk_level == RiskLevel.HIGH
        assert "恶意" in alert.reason

    def test_parse_invalid_json(self, mocker):
        mocker.patch(
            "yifang.meeting.auditor.call_agent",
            return_value="这不是JSON",
        )
        auditor = Auditor()
        alert = auditor.audit("测试")
        assert alert.risk_level == RiskLevel.LOW


# ── controller 决策解析测试 ─────────────────────────────────


class TestControllerParsing:
    def test_parse_valid_decision(self):
        mc = MeetingController()
        raw = json.dumps({
            "summon": ["质疑者"],
            "dismiss": [],
            "action": "continue",
            "reasoning": "需要质疑",
        })
        d = mc._parse_decision(raw)
        assert d.action == "continue"
        assert d.summon == ["质疑者"]

    def test_parse_blocks_auditor_dismiss(self):
        mc = MeetingController()
        raw = json.dumps({
            "summon": [],
            "dismiss": ["安全审计", "质疑者"],
            "action": "converge",
            "reasoning": "结束",
        })
        d = mc._parse_decision(raw)
        assert "安全审计" not in d.dismiss
        assert "质疑者" in d.dismiss

    def test_parse_invalid_json_converges(self):
        mc = MeetingController()
        d = mc._parse_decision("完全不是JSON内容")
        assert d.action == "converge"

    def test_parse_json_in_markdown(self):
        mc = MeetingController()
        raw = '```json\n{"summon": [], "dismiss": [], "action": "converge", "reasoning": "ok"}\n```'
        d = mc._parse_decision(raw)
        assert d.action == "converge"


# ── secretary 测试 ──────────────────────────────────────────


class TestSecretary:
    def test_intake_short_passthrough(self):
        """短输入直接透传，不调用 LLM"""
        sec = Secretary()
        result = sec.intake("这是一个测试")
        assert result == "这是一个测试"
        assert sec.record.original_task == "这是一个测试"

    def test_intake_long_compresses(self, mocker):
        """长输入调用 LLM 压缩"""
        mocker.patch(
            "yifang.meeting.secretary.call_agent",
            return_value="压缩后的摘要",
        )
        sec = Secretary()
        long_input = "很长的内容" * 500  # 超过 2000 字符
        result = sec.intake(long_input)
        assert result == "压缩后的摘要"

    def test_compress_round_short_skip(self):
        """轮后内容较短，跳过 LLM 压缩"""
        sec = Secretary()
        responses = [ExpertResponse(expert_name="质疑者", content="没问题")]
        decision = ControllerDecision(
            summon=[], dismiss=[],
            action="converge", reasoning="ok",
        )
        result = sec.compress_round(responses, decision)
        assert "质疑者" in result
        assert "没问题" in result
        assert "converge" in result

    def test_compress_round_long_compresses(self, mocker):
        """轮后内容较长，调用 LLM 压缩"""
        mocker.patch(
            "yifang.meeting.secretary.call_agent",
            return_value="压缩后的轮次摘要",
        )
        sec = Secretary()
        responses = [
            ExpertResponse(expert_name="质疑者", content="很长的分析" * 500),
        ]
        decision = ControllerDecision(
            summon=[], dismiss=[],
            action="continue", reasoning="继续",
        )
        result = sec.compress_round(responses, decision)
        assert result == "压缩后的轮次摘要"

    def test_record_round(self):
        sec = Secretary()
        sec.record.original_task = "测试"
        r = RoundRecord(round_number=1, secretary_summary="摘要")
        sec.record_round(r)
        assert len(sec.record.rounds) == 1
        assert sec.record.rounds[0].round_number == 1


# ── 集成测试（mock LLM）────────────────────────────────────


class TestMeetingIntegration:
    def test_high_risk_halts_meeting(self, mocker):
        """安全审计高风险应暂停会议，经秘书整理后输出"""
        mocker.patch(
            "yifang.meeting.auditor.call_agent",
            return_value=json.dumps({
                "risk_level": "high",
                "reason": "危险操作",
                "recommendation": "立即停止",
            }),
        )
        mocker.patch(
            "yifang.meeting.secretary.call_agent",
            return_value="经秘书整理：安全审计暂停，检测到危险操作，请立即停止。",
        )

        mc = MeetingController()
        result = mc.convene("删除所有数据")
        assert "秘书整理" in result

    def test_converge_produces_output(self, mocker):
        """主控决定收敛时应产出最终输出"""
        call_count = {"n": 0}

        def fake_call(system, user, **kwargs):
            call_count["n"] += 1
            # 短输入透传，无秘书 intake 调用
            # 第 1 次：审计 → 低风险
            if call_count["n"] == 1:
                return json.dumps({
                    "risk_level": "low",
                    "reason": "无风险",
                    "recommendation": "继续",
                })
            # 第 2 次：主控首轮 → 直接收敛
            if call_count["n"] == 2:
                return json.dumps({
                    "summon": [],
                    "dismiss": [],
                    "action": "converge",
                    "reasoning": "简单问题无需专家",
                })
            # 第 3 次：秘书最终输出
            if call_count["n"] == 3:
                return "1+1=2"
            return ""

        mocker.patch("yifang.meeting.auditor.call_agent", side_effect=fake_call)
        mocker.patch("yifang.meeting.controller.call_agent", side_effect=fake_call)
        mocker.patch("yifang.meeting.secretary.call_agent", side_effect=fake_call)

        mc = MeetingController()
        result = mc.convene("1+1等于几")
        assert "2" in result
