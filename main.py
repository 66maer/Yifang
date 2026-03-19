"""蚁坊 (Yifang) 入口"""

from yifang import MeetingController, token_tracker


def main():
    print("=== 蚁坊 (Yifang) ===")
    print("输入 exit 退出\n")

    controller = MeetingController()

    while True:
        try:
            task = input("你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Yifang] 再见")
            break

        if not task:
            continue
        if task.lower() == "exit":
            print("[Yifang] 再见")
            break

        token_tracker.reset()
        result = controller.convene(task)
        # 每次请求新建 controller（每次请求 = 一次独立会议）
        controller = MeetingController()
        print(f"\nYifang: {result}")
        print(f"[统计] {token_tracker.summary()}\n")


if __name__ == "__main__":
    main()
