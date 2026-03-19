"""专家库：自动发现、按需召集、完成即离场"""

from __future__ import annotations

import importlib
import pkgutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from yifang.core import call_agent
from yifang.meeting.protocol import ExpertResponse
from yifang.meeting.debug import log_io


@dataclass
class ExpertDef:
    """专家定义"""
    name: str
    focus: str
    prompt: str


# ── 专家注册表 ──────────────────────────────────────────────

_registry: dict[str, ExpertDef] = {}


def register(name: str, focus: str, prompt: str) -> None:
    """注册一个专家"""
    _registry[name] = ExpertDef(name=name, focus=focus, prompt=prompt)


def get_expert(name: str) -> ExpertDef | None:
    """获取专家定义"""
    return _registry.get(name)


def available_experts() -> list[ExpertDef]:
    """返回所有已注册专家"""
    return list(_registry.values())


def expert_catalog() -> str:
    """生成专家目录文本，供主控 prompt 使用"""
    lines = []
    for e in _registry.values():
        lines.append(f"- {e.name}：{e.focus}")
    return "\n".join(lines)


# ── 咨询逻辑 ────────────────────────────────────────────────


def consult_expert(expert_name: str, briefing: str) -> ExpertResponse:
    """召集一位专家，传入入会摘要，获取发言"""
    expert = _registry.get(expert_name)
    if not expert:
        # 未知专家用领域通才兜底
        expert = _registry.get("领域通才")
    if not expert:
        return ExpertResponse(expert_name=expert_name, content="[未找到该专家]")

    log_io(f"专家:{expert_name}", "收到入会摘要", input=briefing)
    response = call_agent(expert.prompt, briefing, role=expert_name)
    log_io(f"专家:{expert_name}", "发言", output=response)
    return ExpertResponse(expert_name=expert_name, content=response)


def consult_experts_parallel(
    experts: list[dict],
    briefings: dict[str, str],
) -> list[ExpertResponse]:
    """并行召集多位专家

    Args:
        experts: [{"expert": "名称", ...}, ...]
        briefings: {专家名: 入会摘要}
    """
    if not experts:
        return []

    def _consult(item: dict) -> ExpertResponse:
        name = item["expert"]
        briefing = briefings.get(name, "")
        return consult_expert(name, briefing)

    with ThreadPoolExecutor(max_workers=len(experts)) as pool:
        futures = [pool.submit(_consult, item) for item in experts]
        return [f.result() for f in futures]


# ── 自动发现 ────────────────────────────────────────────────

def _auto_discover() -> None:
    """自动导入 experts/ 下所有模块，触发各模块的 register() 调用"""
    package_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(package_path)]):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{info.name}")


_auto_discover()
