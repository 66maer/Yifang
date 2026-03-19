"""core 模块测试：TokenTracker"""

import threading
from yifang.core import TokenTracker


class FakeUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class TestTokenTracker:
    def test_initial_state(self):
        tracker = TokenTracker()
        assert tracker.prompt_tokens == 0
        assert tracker.completion_tokens == 0
        assert tracker.call_count == 0
        assert tracker.total_tokens == 0

    def test_add_usage(self):
        tracker = TokenTracker()
        tracker.add(FakeUsage(prompt_tokens=100, completion_tokens=50))
        assert tracker.prompt_tokens == 100
        assert tracker.completion_tokens == 50
        assert tracker.total_tokens == 150
        assert tracker.call_count == 1

    def test_add_multiple(self):
        tracker = TokenTracker()
        tracker.add(FakeUsage(100, 50))
        tracker.add(FakeUsage(200, 30))
        assert tracker.prompt_tokens == 300
        assert tracker.completion_tokens == 80
        assert tracker.call_count == 2

    def test_add_none_fields(self):
        """usage 字段为 None 时不崩溃"""
        tracker = TokenTracker()
        tracker.add(FakeUsage(prompt_tokens=None, completion_tokens=None))
        assert tracker.total_tokens == 0
        assert tracker.call_count == 1

    def test_add_missing_fields(self):
        """usage 对象缺字段时不崩溃"""
        tracker = TokenTracker()
        tracker.add(object())  # 没有 prompt_tokens/completion_tokens 属性
        assert tracker.total_tokens == 0
        assert tracker.call_count == 1

    def test_reset(self):
        tracker = TokenTracker()
        tracker.add(FakeUsage(100, 50))
        tracker.reset()
        assert tracker.prompt_tokens == 0
        assert tracker.completion_tokens == 0
        assert tracker.call_count == 0

    def test_summary_format(self):
        tracker = TokenTracker()
        tracker.add(FakeUsage(1000, 500))
        tracker.add(FakeUsage(2000, 300))
        s = tracker.summary()
        assert "调用 2 次" in s
        assert "3,000" in s  # prompt
        assert "800" in s    # completion
        assert "3,800" in s  # total

    def test_thread_safety(self):
        """多线程并发 add 不丢数据"""
        tracker = TokenTracker()
        n_threads = 50

        def add_one():
            tracker.add(FakeUsage(10, 5))

        threads = [threading.Thread(target=add_one) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert tracker.call_count == n_threads
        assert tracker.prompt_tokens == 10 * n_threads
        assert tracker.completion_tokens == 5 * n_threads

    def test_role_tracking(self):
        """按角色统计 token"""
        tracker = TokenTracker()
        tracker.add(FakeUsage(100, 50), role="秘书")
        tracker.add(FakeUsage(200, 80), role="主控")
        tracker.add(FakeUsage(150, 60), role="秘书")
        tracker.add(FakeUsage(50, 20))  # 无角色

        assert tracker.call_count == 4
        assert tracker.total_tokens == 100 + 50 + 200 + 80 + 150 + 60 + 50 + 20

        assert tracker._roles["秘书"].call_count == 2
        assert tracker._roles["秘书"].prompt_tokens == 250
        assert tracker._roles["秘书"].completion_tokens == 110

        assert tracker._roles["主控"].call_count == 1
        assert tracker._roles["主控"].total_tokens == 280

        # 无角色的不记录到 _roles
        assert "" not in tracker._roles

    def test_role_summary(self):
        """summary 包含角色明细"""
        tracker = TokenTracker()
        tracker.add(FakeUsage(100, 50), role="秘书")
        tracker.add(FakeUsage(200, 80), role="主控")
        s = tracker.summary()
        assert "角色明细" in s
        assert "秘书" in s
        assert "主控" in s

    def test_role_reset(self):
        """reset 清空角色统计"""
        tracker = TokenTracker()
        tracker.add(FakeUsage(100, 50), role="秘书")
        tracker.reset()
        assert len(tracker._roles) == 0
