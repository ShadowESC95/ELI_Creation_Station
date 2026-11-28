"""The social side of a brand: its kit (name, voice, colours, logo, hashtags) and its content
calendar (what goes out where and when, and what has gone), kept on this machine.

Creation Station does not post for anyone or read their accounts: the calendar is the plan, and
the person marks a post as posted. It can be exported as a calendar file any calendar app opens.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# General guidance on when each platform's audience is most often online (weekday, local time).
# A starting point to test against a brand's own results, not a promise.
GOOD_TIMES = {
    "x": "Weekdays 08:00–10:00 and 12:00–13:00",
    "threads": "Weekdays 09:00–12:00",
    "bluesky": "Weekdays 09:00–11:00",
    "instagram": "Tue–Fri 11:00–13:00 and 19:00–21:00",
    "tiktok": "Tue–Thu 18:00–22:00",
    "linkedin": "Tue–Thu 08:00–10:00",
    "facebook": "Weekdays 09:00–13:00",
    "youtube": "Thu–Sat 15:00–19:00",
}


@dataclass
class Brand:
    name: str = ""
    voice: str = ""
    colours: list[str] = field(default_factory=lambda: ["#22d3ee", "#f637ec", "#05070d"])
    logo: str = ""
    hashtags: list[str] = field(default_factory=list)
    website: str = ""

    @classmethod
    def from_dict(cls, raw: Any) -> Brand:
        if not isinstance(raw, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})


@dataclass
class Planned:
    day: str  # YYYY-MM-DD
    platform: str
    text: str
    time: str = "09:00"
    asset: str = ""
    status: str = "planned"  # planned | posted
    title: str = ""
    id: str = field(default_factory=lambda: f"post-{uuid.uuid4().hex[:8]}")


class Calendar:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def all(self) -> list[Planned]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        known = {f.name for f in fields(Planned)}
        out = [Planned(**{k: v for k, v in item.items() if k in known}) for item in raw if isinstance(item, dict)]
        return sorted(out, key=lambda p: (p.day, p.time))

    def _save(self, items: list[Planned]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".calendar-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump([asdict(i) for i in items], handle, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def put(self, item: Planned) -> Planned:
        items = [i for i in self.all() if i.id != item.id] + [item]
        self._save(items)
        return item

    def remove(self, item_id: str) -> None:
        self._save([i for i in self.all() if i.id != item_id])

    def month(self, year: int, month: int) -> dict[str, list[Planned]]:
        prefix = f"{year:04d}-{month:02d}-"
        out: dict[str, list[Planned]] = {}
        for item in self.all():
            if item.day.startswith(prefix):
                out.setdefault(item.day, []).append(item)
        return out

    def upcoming(self, limit: int = 8, today: date | None = None) -> list[Planned]:
        start = (today or date.today()).isoformat()
        return [i for i in self.all() if i.day >= start and i.status != "posted"][:limit]

    def stats(self, today: date | None = None) -> dict[str, int]:
        now = today or date.today()
        month = f"{now.year:04d}-{now.month:02d}-"
        items = self.all()
        return {
            "planned": sum(1 for i in items if i.status != "posted" and i.day >= now.isoformat()),
            "posted_month": sum(1 for i in items if i.status == "posted" and i.day.startswith(month)),
            "this_week": sum(1 for i in items if now.isoformat() <= i.day <= (now + timedelta(days=7)).isoformat()),
            "overdue": sum(1 for i in items if i.status != "posted" and i.day < now.isoformat()),
        }

    def ics(self, path: Path) -> Path:
        """The plan as an iCalendar file (one event per post)."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ELI//Creation Station//EN"]
        for item in self.all():
            when = item.day.replace("-", "") + "T" + item.time.replace(":", "") + "00"
            summary = f"{item.platform.capitalize()}: {(item.title or item.text)[:60]}"
            lines += ["BEGIN:VEVENT", f"UID:{item.id}@creation.eli", f"DTSTAMP:{stamp}", f"DTSTART:{when}",
                      "SUMMARY:" + _escape(summary), "DESCRIPTION:" + _escape(item.text), "END:VEVENT"]
        lines.append("END:VCALENDAR")
        path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        return path


def _escape(text: str) -> str:
    """Text as an iCalendar value: backslashes, new lines, commas and semicolons escaped."""
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
