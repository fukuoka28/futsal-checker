#!/usr/bin/env python3
"""
LaBOLA フットサル募集スクレイパー
サイト巡回・解析ロジック
"""

import os
import re
from dataclasses import dataclass
from typing import Generator

import requests
from bs4 import BeautifulSoup


@dataclass
class Event:
    """募集イベント情報"""
    title: str
    facility: str
    url: str
    date: str


class LaBOLAScraper:
    """LaBOLAサイトのスクレイパー"""

    BASE_URL = "https://labola.jp"
    SEARCH_URL_TEMPLATE = (
        "https://labola.jp/reserve/events/search/personal/"
        "area-13/day-{date}/"
    )

    # フィルタリング条件
    ACCEPTING_STATUS = "受付け中"
    REQUIRED_KEYWORD = "大会"
    EXCLUDED_KEYWORD = "千住大橋"

    def __init__(self, dates_file: str = "data/dates.txt"):
        self.dates_file = dates_file
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        })

    def load_dates(self) -> list[str]:
        """監視対象の日付リストを読み込む"""
        if not os.path.exists(self.dates_file):
            print(f"[ERROR] dates file not found: {self.dates_file}")
            return []

        with open(self.dates_file, "r", encoding="utf-8") as f:
            dates = [line.strip() for line in f if line.strip()]

        # 8桁の数字形式をバリデーション
        valid_dates = []
        for date in dates:
            if re.match(r"^\d{8}$", date):
                valid_dates.append(date)
            else:
                print(f"[WARN] Invalid date format: {date}")

        return valid_dates

    def fetch_page(self, date: str) -> BeautifulSoup | None:
        """指定日付のページを取得"""
        url = self.SEARCH_URL_TEMPLATE.format(date=date)
        print(f"[INFO] Fetching: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None

    def parse_events(self, soup: BeautifulSoup, date: str) -> list[Event]:
        """ページから募集イベントを抽出"""
        events = []

        # イベントリンクを探す（/event/show/ を含むリンク）
        event_links = soup.find_all("a", href=lambda x: x and "/event/show/" in x)

        seen_urls = set()
        for link in event_links:
            href = link.get("href", "")

            # 重複除去
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 完全なURLを構築
            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

            # タイトルを取得
            title = link.get_text(strip=True)
            if not title:
                continue

            # フィルタリング条件をチェック
            if not self._is_valid_event(link):
                continue

            # 施設名を推定（親要素から探す）
            facility = self._extract_facility(link)

            events.append(Event(
                title=title,
                facility=facility,
                url=full_url,
                date=date
            ))

        return events

    def _extract_facility(self, link_element) -> str:
        """リンク要素から施設名を抽出"""
        # 親要素を遡って施設情報を探す
        parent = link_element.parent
        for _ in range(5):
            if parent is None:
                break

            text = parent.get_text(separator=" ", strip=True)

            # 【施設名】の形式を探す
            match = re.search(r"【(.+?)】", text)
            if match:
                return match.group(1)

            parent = parent.parent

        return ""

    def _is_valid_event(self, link_element) -> bool:
        """イベントが条件を満たすかチェック"""
        # 親要素を遡ってテキストを収集
        parent = link_element.parent
        for _ in range(5):
            if parent is None:
                break

            text = parent.get_text(separator=" ", strip=True)

            # 必須条件: 「受付け中」と「大会」の両方が含まれていること
            has_accepting = self.ACCEPTING_STATUS in text
            has_tournament = self.REQUIRED_KEYWORD in text

            if has_accepting and has_tournament:
                # 除外条件: 「千住大橋」が含まれていたら除外
                if self.EXCLUDED_KEYWORD in text:
                    return False
                return True

            parent = parent.parent

        return False

    def scrape_all(self) -> Generator[Event, None, None]:
        """全日付を巡回してイベントを取得"""
        dates = self.load_dates()

        if not dates:
            print("[WARN] No dates to scrape")
            return

        print(f"[INFO] Scraping {len(dates)} dates...")

        for date in dates:
            soup = self.fetch_page(date)
            if soup is None:
                continue

            events = self.parse_events(soup, date)
            print(f"[INFO] Found {len(events)} valid events for {date}")

            for event in events:
                yield event


def main():
    """テスト実行"""
    # プロジェクトルートからの相対パスで実行
    scraper = LaBOLAScraper(dates_file="data/dates.txt")

    print("=" * 60)
    print("LaBOLA Scraper Test")
    print("=" * 60)

    events = list(scraper.scrape_all())

    print("\n" + "=" * 60)
    print(f"Total valid events: {len(events)}")
    print("=" * 60)

    for event in events:
        print(f"\n[{event.date}] {event.title}")
        print(f"  施設: {event.facility}")
        print(f"  URL: {event.url}")


if __name__ == "__main__":
    main()
