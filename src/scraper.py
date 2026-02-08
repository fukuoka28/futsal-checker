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
    REQUIRED_KEYWORDS = ["受付け中", "大会"]  # AND条件：すべて含む必要あり
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
        """ページから募集イベントを抽出（イベントカード単位でループ）"""
        events = []

        # イベントカード（募集枠）を探す
        event_cards = soup.find_all("div", class_="c-eventcard")

        print(f"\n[DEBUG] Found {len(event_cards)} event cards on page")
        print("-" * 60)

        for idx, card in enumerate(event_cards, 1):
            # カード全体のテキストを取得
            card_text = card.get_text(separator=" ", strip=True)

            # タイトルとURLを取得
            title_elem = card.find("p", class_="c-eventcard__title")
            if not title_elem:
                print(f"\n[枠 {idx}] タイトル要素が見つかりません → スキップ")
                continue

            link = title_elem.find("a")
            if not link:
                print(f"\n[枠 {idx}] リンクが見つかりません → スキップ")
                continue

            href = link.get("href", "")
            title = link.get_text(strip=True)
            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

            # ステータスを取得（受付け中、満席、空いたら通知、開催中止など）
            status_elem = card.find("p", class_=lambda x: x and "c-eventcard__state" in x)
            status = status_elem.get_text(strip=True) if status_elem else ""

            # 施設名を取得（主催者行から）
            facility = self._extract_facility_from_card(card)

            # デバッグ出力
            print(f"\n[枠 {idx}] テキスト情報:")
            print(f"  タイトル: {title}")
            print(f"  ステータス: {status}")
            print(f"  施設: {facility}")
            print(f"  URL: {full_url}")

            if not title:
                print(f"  → [除外] タイトルが空のためスキップ")
                continue

            # フィルタリング条件をチェック（カード単位のテキストで判定）
            is_valid, reason = self._is_valid_card(card_text, title, status)
            if not is_valid:
                print(f"  → [除外] {reason}")
                continue

            print(f"  → [通過] フィルター条件を満たしました")

            events.append(Event(
                title=title,
                facility=facility,
                url=full_url,
                date=date
            ))

        print("-" * 60)
        return events

    def _extract_facility_from_card(self, card) -> str:
        """イベントカードから施設名を抽出"""
        # 主催者の行を探す
        text_elems = card.find_all("p", class_="c-eventcard__text")
        for elem in text_elems:
            text = elem.get_text(strip=True)
            if text.startswith("主催者："):
                # 主催者リンクからテキストを取得
                link = elem.find("a")
                if link:
                    return link.get_text(strip=True)
                # リンクがなければ「主催者：」の後のテキスト
                return text.replace("主催者：", "")

        # 【施設名】の形式も試す
        card_text = card.get_text(separator=" ", strip=True)
        match = re.search(r"【(.+?)】", card_text)
        if match:
            return match.group(1)

        return ""

    def _is_valid_card(self, card_text: str, title: str, status: str) -> tuple[bool, str]:
        """イベントカードが条件を満たすかチェック"""
        # 除外条件を最初にチェック: 「千住大橋」が含まれていたら除外
        if self.EXCLUDED_KEYWORD in card_text:
            return False, f"除外キーワード「{self.EXCLUDED_KEYWORD}」が含まれています"

        # 必須条件をチェック
        # 「受付け中」はステータスで判定
        if "受付け中" in self.REQUIRED_KEYWORDS and status != "受付け中":
            return False, f"ステータスが「受付け中」ではありません（現在: {status or '不明'}）"

        # 「大会」はタイトルまたはカード全体のテキストで判定
        if "大会" in self.REQUIRED_KEYWORDS and "大会" not in card_text:
            return False, "必須キーワード「大会」が見つかりません"

        return True, "OK"

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
