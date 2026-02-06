#!/usr/bin/env python3
"""
LaBOLA フットサル募集監視ツール
メインエントリーポイント
"""

import os
import sys
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scraper import LaBOLAScraper
from src.notifier import LineNotifier


def main():
    """メイン処理"""
    print("=" * 60)
    print(f"LaBOLA Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # スクレイパー初期化
    scraper = LaBOLAScraper(dates_file="data/dates.txt")

    # 全日付を巡回してイベントを取得
    print("\n[STEP 1] Scraping events...")
    events = list(scraper.scrape_all())

    if not events:
        print("[INFO] No matching events found")
        print("=" * 60)
        return 0

    print(f"\n[INFO] Found {len(events)} matching events")

    # 通知処理
    print("\n[STEP 2] Sending notifications...")
    notifier = LineNotifier(sent_urls_file="data/sent_urls.txt")

    # 新着イベントをフィルタリング
    new_events = notifier.filter_new_events(events)

    if not new_events:
        print("[INFO] No new events to notify (all already sent)")
        print("=" * 60)
        return 0

    print(f"[INFO] {len(new_events)} new events to notify")

    # イベント一覧を表示
    print("\n--- New Events ---")
    for event in new_events:
        print(f"  [{event.date}] {event.title[:50]}...")

    # LINE通知を送信
    success, failed = notifier.notify_all(events)

    print("\n" + "=" * 60)
    print(f"Summary: {success} notifications sent, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
