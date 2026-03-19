"""调试工具：统一的输入输出打印"""

_ENABLED = True
_MAX_LEN = 1000  # 截断显示的最大字符数


def set_debug(enabled: bool) -> None:
    global _ENABLED
    _ENABLED = enabled


def _truncate(text: str) -> str:
    if len(text) <= _MAX_LEN:
        return text
    return text[:_MAX_LEN] + f"...({len(text)} 字符)"


def log_io(role: str, action: str, *, input: str = "", output: str = "") -> None:
    """打印角色的输入输出

    Args:
        role: 角色名（秘书/主控/审计/专家名）
        action: 动作描述
        input: 输入内容
        output: 输出内容
    """
    if not _ENABLED:
        return

    print(f"\n  ┌─[{role}] {action}")
    if input:
        for line in _truncate(input).splitlines():
            print(f"  │ IN:  {line}")
    if output:
        for line in _truncate(output).splitlines():
            print(f"  │ OUT: {line}")
    print(f"  └─")
