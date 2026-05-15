"""
Academic Paper Tracker
Monitors arXiv and Google Scholar for new papers in your research field
"""

import requests
import arxiv
import time
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — edit this section before running
# ---------------------------------------------------------------------------
CONFIG = {
    # Keywords used to filter results from arXiv and Google Scholar
    "keywords": [
        "machine learning",
        "deep learning",
        "neural networks",
        "NLP",
        "computer vision",
    ],
    # arXiv category codes  (https://arxiv.org/category_taxonomy)
    "arxiv_categories": ["cs.LG", "cs.CV", "cs.CL", "cs.AI"],
    # How many results to fetch per category / keyword before filtering
    "max_results": 20,
    # Only papers published within this many days will be kept
    "days_back": 7,
    # Folder where downloaded PDFs are stored
    "download_dir": "papers",
    # JSON file that persists all tracked papers across runs
    "database_file": "papers_database.json",
    # Set to your Anthropic API key (or export ANTHROPIC_API_KEY env var)
    # Used to generate short AI summaries of each abstract
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
}


# ---------------------------------------------------------------------------
# PaperTracker
# ---------------------------------------------------------------------------
class PaperTracker:
    def __init__(self, config: dict):
        self.config = config
        self.papers_db = self._load_database()
        Path(config["download_dir"]).mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------
    def _load_database(self) -> dict:
        db_file = self.config["database_file"]
        if os.path.exists(db_file):
            with open(db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"papers": [], "last_run": None}

    def save_database(self):
        self.papers_db["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.config["database_file"], "w", encoding="utf-8") as f:
            json.dump(self.papers_db, f, indent=2, ensure_ascii=False)

    def _is_tracked(self, paper_id: str) -> bool:
        return any(p["id"] == paper_id for p in self.papers_db["papers"])

    def _add_paper(self, paper: dict):
        self.papers_db["papers"].append(paper)

    # ------------------------------------------------------------------
    # arXiv search
    # ------------------------------------------------------------------
    def search_arxiv(self) -> list[dict]:
        print("🔍  Searching arXiv …")
        new_papers: list[dict] = []
        date_threshold = datetime.now() - timedelta(days=self.config["days_back"])
        client = arxiv.Client()

        for category in self.config["arxiv_categories"]:
            print(f"     category: {category}")
            search = arxiv.Search(
                query=f"cat:{category}",
                max_results=self.config["max_results"],
                sort_by=arxiv.SortCriterion.SubmittedDate,
            )

            for result in client.results(search):
                # Date filter
                if result.published.replace(tzinfo=None) < date_threshold:
                    continue

                # Keyword filter
                text = f"{result.title} {result.summary}".lower()
                if not any(kw.lower() in text for kw in self.config["keywords"]):
                    continue

                paper_id = result.entry_id.split("/")[-1]
                if self._is_tracked(paper_id):
                    continue

                paper = {
                    "id": paper_id,
                    "title": result.title,
                    "authors": [a.name for a in result.authors],
                    "summary": result.summary,
                    "published": result.published.strftime("%Y-%m-%d"),
                    "url": result.entry_id,
                    "pdf_url": result.pdf_url,
                    "categories": result.categories,
                    "source": "arxiv",
                    "downloaded": False,
                    "local_path": None,
                    "ai_summary": None,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                new_papers.append(paper)
                self._add_paper(paper)
                print(f"     ✓  {result.title[:70]}…")

        return new_papers

    # ------------------------------------------------------------------
    # Google Scholar search  (lightweight requests-based scraping)
    # ------------------------------------------------------------------
    def search_google_scholar(self) -> list[dict]:
        """
        Scrape the first page of Google Scholar results for each keyword.
        Uses requests + BeautifulSoup — no browser dependency.
        Rate-limits itself to be polite.
        """
        from bs4 import BeautifulSoup

        print("🔍  Searching Google Scholar …")
        new_papers: list[dict] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        }
        year = datetime.now().year

        for keyword in self.config["keywords"][:3]:  # cap to avoid blocks
            url = (
                f"https://scholar.google.com/scholar"
                f"?q={requests.utils.quote(keyword)}&as_ylo={year}"
            )
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                print(f"     ⚠️   Scholar request failed for '{keyword}': {exc}")
                time.sleep(5)
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            for block in soup.select(".gs_ri")[:5]:
                try:
                    title_tag = block.select_one(".gs_rt")
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    link_tag = title_tag.find("a") if title_tag else None
                    link = link_tag["href"] if link_tag else None

                    snippet_tag = block.select_one(".gs_rs")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                    authors_tag = block.select_one(".gs_a")
                    authors = (
                        authors_tag.get_text(strip=True).split("-")[0].strip()
                        if authors_tag
                        else "Unknown"
                    )

                    paper_id = f"gs_{abs(hash(title)) % 10 ** 10}"
                    if self._is_tracked(paper_id):
                        continue

                    paper = {
                        "id": paper_id,
                        "title": title,
                        "authors": [authors],
                        "summary": snippet,
                        "published": datetime.now().strftime("%Y-%m-%d"),
                        "url": link,
                        "pdf_url": None,
                        "categories": [keyword],
                        "source": "google_scholar",
                        "downloaded": False,
                        "local_path": None,
                        "ai_summary": None,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    new_papers.append(paper)
                    self._add_paper(paper)
                    print(f"     ✓  {title[:70]}…")

                except Exception:
                    continue

            time.sleep(4)  # polite delay between Scholar requests

        return new_papers

    # ------------------------------------------------------------------
    # PDF download
    # ------------------------------------------------------------------
    def download_pdfs(self, papers: list[dict]):
        downloadable = [p for p in papers if p.get("pdf_url")]
        if not downloadable:
            print("📥  No PDFs to download.")
            return

        print(f"📥  Downloading {len(downloadable)} PDF(s) …")
        for paper in downloadable:
            filename = f"{paper['id']}.pdf"
            filepath = os.path.join(self.config["download_dir"], filename)
            try:
                resp = requests.get(paper["pdf_url"], stream=True, timeout=60)
                resp.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Update in-memory DB record
                for p in self.papers_db["papers"]:
                    if p["id"] == paper["id"]:
                        p["downloaded"] = True
                        p["local_path"] = filepath

                print(f"     ✓  {paper['title'][:60]}…")
                time.sleep(1)
            except Exception as exc:
                print(f"     ⚠️   Failed {paper['id']}: {exc}")

    # ------------------------------------------------------------------
    # AI summarisation (Anthropic claude-haiku — fast & cheap)
    # ------------------------------------------------------------------
    def summarise_with_claude(self, abstract: str) -> str | None:
        api_key = self.config.get("anthropic_api_key")
        if not api_key:
            return None

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 160,
                    "system": (
                        "You are a research assistant. Summarise academic abstracts "
                        "in 2–3 crisp sentences, highlighting the key contribution and method."
                    ),
                    "messages": [
                        {"role": "user", "content": f"Summarise:\n\n{abstract}"}
                    ],
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()
        except Exception as exc:
            print(f"     ⚠️   AI summary failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Citation / keyword mention check
    # ------------------------------------------------------------------
    def check_citations(self, keywords: list[str]) -> list[dict]:
        print(f"\n🔎  Checking mentions of: {', '.join(keywords)}")
        matches = [
            p
            for p in self.papers_db["papers"]
            if any(
                kw.lower() in f"{p['title']} {p['summary']}".lower()
                for kw in keywords
            )
        ]
        if matches:
            print(f"     ✨  {len(matches)} paper(s) mention your keywords:")
            for p in matches[:5]:
                print(f"         – {p['title'][:70]}…")
        else:
            print("     No matches found yet.")
        return matches

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------
    def generate_report(self, new_papers: list[dict]):
        if not new_papers:
            print("\n📭  No new papers found this run.")
            return

        print(f"\n{'=' * 80}")
        print(f"  📊  {len(new_papers)} new paper(s) found")
        print(f"{'=' * 80}")

        for i, paper in enumerate(new_papers, 1):
            authors_str = ", ".join(paper["authors"][:3])
            if len(paper["authors"]) > 3:
                authors_str += " et al."

            print(f"\n{i}.  {paper['title']}")
            print(f"    Authors   : {authors_str}")
            print(f"    Published : {paper['published']}   Source: {paper['source']}")
            print(f"    URL       : {paper['url']}")

            snippet = paper["summary"][:200]
            if len(paper["summary"]) > 200:
                snippet += "…"
            print(f"    Abstract  : {snippet}")

            # AI summary (generate if missing)
            if paper.get("ai_summary"):
                print(f"    🤖 Summary: {paper['ai_summary']}")
            elif self.config.get("anthropic_api_key"):
                ai_sum = self.summarise_with_claude(paper["summary"])
                if ai_sum:
                    paper["ai_summary"] = ai_sum
                    # persist into DB record too
                    for p in self.papers_db["papers"]:
                        if p["id"] == paper["id"]:
                            p["ai_summary"] = ai_sum
                    print(f"    🤖 Summary: {ai_sum}")

            print(f"    {'─' * 74}")

        # Save plain-text report
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"paper_report_{ts}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"Paper Tracking Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            for i, paper in enumerate(new_papers, 1):
                f.write(f"{i}. {paper['title']}\n")
                f.write(f"   Authors   : {', '.join(paper['authors'])}\n")
                f.write(f"   Published : {paper['published']}\n")
                f.write(f"   URL       : {paper['url']}\n")
                if paper.get("ai_summary"):
                    f.write(f"   AI Summary: {paper['ai_summary']}\n")
                f.write(f"   Abstract  : {paper['summary']}\n")
                f.write("─" * 80 + "\n\n")

        print(f"\n💾  Report saved → {report_path}")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(
        self,
        download_pdfs: bool = True,
        check_my_citations: list[str] | None = None,
    ):
        print("\n🚀  Academic Paper Tracker")
        print(f"    Looking back {self.config['days_back']} day(s)")
        print(f"    Keywords : {', '.join(self.config['keywords'])}\n")

        arxiv_papers = self.search_arxiv()
        scholar_papers = self.search_google_scholar()
        all_new = arxiv_papers + scholar_papers

        if download_pdfs and all_new:
            self.download_pdfs(all_new)

        self.save_database()
        self.generate_report(all_new)

        if check_my_citations:
            self.check_citations(check_my_citations)

        print(
            f"\n✅  Done.  Database now holds "
            f"{len(self.papers_db['papers'])} paper(s) total."
        )


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tracker = PaperTracker(CONFIG)
    tracker.run(
        download_pdfs=True,
        check_my_citations=["BERT", "transformer", "attention mechanism"],
    )
