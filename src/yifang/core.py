"""基础设施：TokenTracker + LLM 调用"""

import time
import threading
from dataclasses import dataclass, field

from yifang.config import client, MODEL


@dataclass
class RoleStats:
    """单个角色的统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    call_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class TokenTracker:
    """线程安全的 token 统计器，支持按角色统计"""

    def __init__(self):
        self._lock = threading.Lock()
        self._roles: dict[str, RoleStats] = {}
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.call_count = 0

    def add(self, usage, role: str = ""):
        with self._lock:
            pt = getattr(usage, "prompt_tokens", 0) or 0
            ct = getattr(usage, "completion_tokens", 0) or 0
            self.prompt_tokens += pt
            self.completion_tokens += ct
            self.call_count += 1

            if role:
                if role not in self._roles:
                    self._roles[role] = RoleStats()
                stats = self._roles[role]
                stats.prompt_tokens += pt
                stats.completion_tokens += ct
                stats.call_count += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def reset(self):
        with self._lock:
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.call_count = 0
            self._roles.clear()

    def summary(self) -> str:
        lines = [
            f"调用 {self.call_count} 次 | "
            f"输入 {self.prompt_tokens:,} + 输出 {self.completion_tokens:,} = "
            f"共 {self.total_tokens:,} tokens"
        ]
        if self._roles:
            lines.append("  角色明细：")
            for name, s in sorted(self._roles.items(), key=lambda x: -x[1].total_tokens):
                lines.append(
                    f"    {name:8s}  {s.call_count} 次 | "
                    f"入 {s.prompt_tokens:,} + 出 {s.completion_tokens:,} = {s.total_tokens:,}"
                )
        return "\n".join(lines)


token_tracker = TokenTracker()


def call_agent(
    system: str, user: str, *, role: str = "", thinking: bool = False
) -> str:
    """最基础的 LLM 调用，所有 Agent 共用"""
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
            temperature=0.1,
        )
        elapsed = time.time() - start
        if response.usage:
            token_tracker.add(response.usage, role=role)
            pt = response.usage.prompt_tokens or 0
            ct = response.usage.completion_tokens or 0
            tag = f" {role}" if role else ""
            print(f"  [耗时 {elapsed:.1f}s |{tag} {pt}+{ct}={pt+ct} tokens]")
        else:
            print(f"  [耗时 {elapsed:.1f}s]")
        content = response.choices[0].message.content or ""
        return content.strip()
    except Exception as e:
        print(f"[Yifang] 模型调用失败: {e}")
        return ""


def call_agent_with_history(
    messages: list[dict], *, role: str = "", thinking: bool = False
) -> str:
    """支持多轮对话历史的 LLM 调用"""
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
            temperature=0.1,
        )
        elapsed = time.time() - start
        if response.usage:
            token_tracker.add(response.usage, role=role)
            pt = response.usage.prompt_tokens or 0
            ct = response.usage.completion_tokens or 0
            tag = f" {role}" if role else ""
            print(f"  [耗时 {elapsed:.1f}s |{tag} {pt}+{ct}={pt+ct} tokens]")
        else:
            print(f"  [耗时 {elapsed:.1f}s]")
        content = response.choices[0].message.content or ""
        return content.strip()
    except Exception as e:
        print(f"[Yifang] 模型调用失败: {e}")
        return ""
