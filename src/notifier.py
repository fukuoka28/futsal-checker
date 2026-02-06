#!/usr/bin/env python3
"""
LINE通知モジュール
LINE Messaging APIを使用した通知送信と重複チェック
"""

import os
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .scraper import Event


class LineNotifier:
    """LINE Messaging API通知クラス"""

    PUSH_API_URL = "https://api.line.me/v2/bot/message/push"

    def __init__(
        self,
        sent_urls_file: str = "data/sent_urls.txt",
        channel_access_token: str | None = None,
        user_id: str | None = None
    ):
        self.sent_urls_file = sent_urls_file
        self.channel_access_token = channel_access_token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.user_id = user_id or os.getenv("LINE_USER_ID")

        # 通知済みURLをロード
        self.sent_urls = self._load_sent_urls()

    def _load_sent_urls(self) -> set[str]:
        """通知済みURLを読み込む"""
        if not os.path.exists(self.sent_urls_file):
            return set()

        with open(self.sent_urls_file, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}

    def _save_sent_url(self, url: str) -> None:
        """通知済みURLを保存"""
        with open(self.sent_urls_file, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")
        self.sent_urls.add(url)

    def is_new_event(self, event: "Event") -> bool:
        """新着イベントかどうかをチェック"""
        return event.url not in self.sent_urls

    def filter_new_events(self, events: list["Event"]) -> list["Event"]:
        """新着イベントのみをフィルタリング"""
        return [event for event in events if self.is_new_event(event)]

    def send_notification(self, event: "Event") -> bool:
        """単一イベントの通知を送信"""
        if not self.channel_access_token or not self.user_id:
            print("[ERROR] LINE credentials not configured")
            print("  Set LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID environment variables")
            return False

        # メッセージを作成
        message = self._format_message(event)

        # LINE APIに送信
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }

        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }

        try:
            response = requests.post(
                self.PUSH_API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                print(f"[OK] Notification sent: {event.title[:30]}...")
                self._save_sent_url(event.url)
                return True
            else:
                print(f"[ERROR] LINE API error: {response.status_code}")
                print(f"  Response: {response.text}")
                return False

        except requests.RequestException as e:
            print(f"[ERROR] Failed to send notification: {e}")
            return False

    def _format_message(self, event: "Event") -> str:
        """通知メッセージをフォーマット"""
        date_formatted = f"{event.date[:4]}/{event.date[4:6]}/{event.date[6:]}"

        return (
            f"🏃 フットサル募集【新着】\n"
            f"\n"
            f"📅 {date_formatted}\n"
            f"📍 {event.facility or '代々木'}\n"
            f"📝 {event.title}\n"
            f"\n"
            f"🔗 {event.url}"
        )

    def notify_all(self, events: list["Event"]) -> tuple[int, int]:
        """
        複数イベントを通知

        Returns:
            (成功数, 失敗数) のタプル
        """
        new_events = self.filter_new_events(events)

        if not new_events:
            print("[INFO] No new events to notify")
            return (0, 0)

        print(f"[INFO] Sending {len(new_events)} notifications...")

        success = 0
        failed = 0

        for event in new_events:
            if self.send_notification(event):
                success += 1
            else:
                failed += 1

        print(f"[INFO] Notifications complete: {success} sent, {failed} failed")
        return (success, failed)


def main():
    """テスト実行"""
    from .scraper import Event

    # テスト用イベント
    test_event = Event(
        title="【代々木競技場フットサルコート】テストイベント",
        facility="国立代々木競技場フットサルコート",
        url="https://labola.jp/r/shop/123/event/show/456/",
        date="20260207"
    )

    notifier = LineNotifier()

    print("=" * 60)
    print("LINE Notifier Test")
    print("=" * 60)

    # 重複チェックテスト
    print(f"\nIs new event: {notifier.is_new_event(test_event)}")

    # メッセージフォーマットテスト
    print("\nFormatted message:")
    print("-" * 40)
    print(notifier._format_message(test_event))
    print("-" * 40)

    # 実際の送信はコメントアウト
    # notifier.send_notification(test_event)


if __name__ == "__main__":
    main()
