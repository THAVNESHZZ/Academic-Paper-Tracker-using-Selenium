"""
Enhanced Paper Tracker — Email Alerts & Scheduling
Run once manually, or uncomment schedule_daily_tracking() for cron-style automation.
"""

import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import schedule  # pip install schedule

from paper_tracker import CONFIG, PaperTracker

# ---------------------------------------------------------------------------
# Email configuration  (fill in or pass via environment variables)
# ---------------------------------------------------------------------------
EMAIL_CONFIG = {
    "enabled": False,               # ← flip to True to activate
    "from_email": "you@gmail.com",
    "to_email": "you@gmail.com",
    "password": "YOUR_APP_PASSWORD",  # Gmail → Settings → App Passwords
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
}


# ---------------------------------------------------------------------------
class EnhancedPaperTracker(PaperTracker):
    """Adds email alerts on top of the base PaperTracker."""

    def __init__(self, config: dict, email_config: dict | None = None):
        super().__init__(config)
        self.email_config = email_config or {}

    # ------------------------------------------------------------------
    # Email helpers
    # ------------------------------------------------------------------
    def send_email_alert(self, new_papers: list[dict]):
        if not self.email_config.get("enabled") or not new_papers:
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"📚 {len(new_papers)} new research paper(s) found"
            msg["From"] = self.email_config["from_email"]
            msg["To"] = self.email_config["to_email"]
            msg.attach(MIMEText(self._build_html(new_papers), "html"))

            with smtplib.SMTP(
                self.email_config["smtp_server"], self.email_config["smtp_port"]
            ) as srv:
                srv.starttls()
                srv.login(self.email_config["from_email"], self.email_config["password"])
                srv.send_message(msg)

            print("📧  Email alert sent!")
        except Exception as exc:
            print(f"⚠️   Email failed: {exc}")

    def _build_html(self, papers: list[dict]) -> str:
        rows = ""
        for i, p in enumerate(papers, 1):
            authors = ", ".join(p["authors"][:3])
            if len(p["authors"]) > 3:
                authors += " et al."
            snippet = p["summary"][:300] + ("…" if len(p["summary"]) > 300 else "")
            ai_row = (
                f"<p style='color:#27ae60;font-size:13px'>"
                f"🤖 <strong>AI summary:</strong> {p['ai_summary']}</p>"
                if p.get("ai_summary")
                else ""
            )
            link = p.get("url") or "#"
            rows += f"""
            <div style="border:1px solid #ddd;border-radius:6px;padding:16px;margin:12px 0">
                <p style="font-size:16px;font-weight:bold;color:#2c3e50;margin:0 0 4px">
                    {i}. {p['title']}
                </p>
                <p style="color:#7f8c8d;font-size:13px;margin:0 0 8px">{authors}</p>
                <p style="font-size:14px;margin:0 0 8px">{snippet}</p>
                {ai_row}
                <p style="font-size:12px;color:#95a5a6;margin:0">
                    Published: {p['published']} &nbsp;|&nbsp; Source: {p['source']} &nbsp;|&nbsp;
                    <a href="{link}" style="color:#3498db">View paper</a>
                </p>
            </div>"""

        return f"""
        <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:auto;padding:20px">
          <h2 style="color:#2c3e50">🎓 New Research Papers — {datetime.now():%Y-%m-%d}</h2>
          <p>Found <strong>{len(papers)}</strong> new paper(s) matching your interests.</p>
          {rows}
          <hr style="border:none;border-top:1px solid #eee;margin-top:24px">
          <p style="font-size:12px;color:#bdc3c7">Sent by Academic Paper Tracker</p>
        </body></html>"""

    # ------------------------------------------------------------------
    # Main entry point (overrides base run to add email step)
    # ------------------------------------------------------------------
    def run(
        self,
        download_pdfs: bool = True,
        check_my_citations: list[str] | None = None,
    ):
        print("\n🚀  Enhanced Paper Tracker (with email alerts)")
        print(f"    Looking back {self.config['days_back']} day(s)")
        print(f"    Keywords : {', '.join(self.config['keywords'])}\n")

        arxiv_papers = self.search_arxiv()
        scholar_papers = self.search_google_scholar()
        all_new = arxiv_papers + scholar_papers

        if download_pdfs and all_new:
            self.download_pdfs(all_new)

        self.save_database()
        self.generate_report(all_new)

        # Email alert with AI summaries already filled in
        self.send_email_alert(all_new)

        if check_my_citations:
            self.check_citations(check_my_citations)

        print(
            f"\n✅  Done.  Database now holds "
            f"{len(self.papers_db['papers'])} paper(s) total."
        )


# ---------------------------------------------------------------------------
# Scheduling helpers
# ---------------------------------------------------------------------------
def _make_tracker() -> EnhancedPaperTracker:
    return EnhancedPaperTracker(CONFIG, EMAIL_CONFIG)


def run_once(
    download_pdfs: bool = True,
    citations: list[str] | None = None,
):
    """Run a single immediate sweep."""
    _make_tracker().run(
        download_pdfs=download_pdfs,
        check_my_citations=citations or ["BERT", "transformer", "diffusion models"],
    )


def schedule_daily_tracking(
    at: str = "09:00",
    download_pdfs: bool = True,
    citations: list[str] | None = None,
):
    """
    Block and run the tracker every day at *at* (24-h HH:MM).
    Press Ctrl-C to stop.
    """
    tracker = _make_tracker()
    cit = citations or ["BERT", "transformer", "diffusion models"]

    schedule.every().day.at(at).do(
        tracker.run,
        download_pdfs=download_pdfs,
        check_my_citations=cit,
    )

    print(f"⏰  Scheduler running — next sweep at {at} daily.  Ctrl-C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # ── Option A: single run ──────────────────────────────────────────
    run_once()

    # ── Option B: daily schedule (uncomment to use) ───────────────────
    # schedule_daily_tracking(at="09:00")
