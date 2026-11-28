"""ELI as an agent across the studio: it answers, and it proposes what to make, each proposal a card
the person runs with one click (nothing is made until they do).

With the main model, ELI reads the question with the project's context and where the person is, and
answers with its reply and up to three actions. Without one, it still knows where each kind of work
is done and offers to take the person there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    icon: str
    studio: str
    args: str  # what the model fills in, as it is told
    words: tuple[str, ...]  # what in a question points to it, without the model


ACTIONS: dict[str, Action] = {a.key: a for a in (
    Action("image", "Make an image", "image", "images", '{"prompt": "a detailed picture prompt"}',
           ("image", "picture", "photo", "illustrat", "draw", "poster", "artwork", "render")),
    Action("posts", "Write posts", "message", "socials", '{"brief": "what the posts are about"}',
           ("post", "tweet", "caption", "instagram", "linkedin", "social", "threads", "tiktok")),
    Action("plan_week", "Plan the week's posts", "calendar", "socials", "{}",
           ("calendar", "schedule", "plan the week", "content plan", "posting plan")),
    Action("ad", "Make an ad", "bolt", "videos",
           '{"product": "...", "tagline": "...", "point1": "...", "point2": "...", "cta": "..."}',
           (" ad ", " ad,", " ad.", "advert", "commercial", "promo")),
    Action("film", "Start a film from a template", "film", "videos", "{}",
           ("film", "video", "trailer", "movie", "explainer", "intro", "short")),
    Action("voice", "Record a voice-over", "mic", "audio", '{"text": "the words to speak"}',
           ("voice", "narrat", "voice-over", "voiceover", "read it", "speak")),
    Action("music", "Compose music", "music", "audio",
           '{"mood": "cinematic|uplifting|ambient|tense|lofi|epic|corporate|electronic", "seconds": 30}',
           ("music", "soundtrack", "song", "score", "beat", "jingle")),
    Action("game", "Design a game", "gamepad", "games", '{"pitch": "the game in a sentence"}',
           ("game", "playable", "arcade")),
    Action("code", "Write code", "code", "coding", '{"task": "what the code should do"}',
           ("code", "script", "program", "function", "python", "javascript", "bug")),
    Action("edit", "Edit a picture", "sliders", "editing", "{}",
           ("edit", "crop", "resize", "watermark", "filter", "colour grade", "color grade")),
)}

SYSTEM = ("You are ELI, the AI inside ELI Creation Station, beside a creator on their project. Answer briefly and "
          "specifically. You can also propose things to make, each one an action the person runs with one click. "
          "Actions (key: arguments):\n"
          + "\n".join(f"- {a.key}: {a.args} ({a.label})" for a in ACTIONS.values())
          + '\nAnswer with JSON only: {"reply": "your answer", "actions": [{"do": "<key>", "args": {...}}]}. '
            "Propose actions only when the person wants something made (at most three); fill the arguments "
            "concretely from what they said and the project's context.")


def suggest(question: str) -> list[dict[str, Any]]:
    """Actions a question points to, found without the model (where to go to do it)."""
    text = f" {question.lower()} "
    found = []
    for action in ACTIONS.values():
        if any(word in text for word in action.words):
            found.append({"do": action.key, "args": {}})
    return found[:3]


def plan(studio: Any, question: str, context: str, where: str) -> dict[str, Any]:
    """ELI's reply and its proposed actions (blocking: call it off the window's thread)."""
    from eli_creation.engines.writing import parse_json

    raw = studio.main.generate(system=SYSTEM, prompt=f"Project context: {context}\nThey are in: {where}\n\n"
                                                    f"They say: {question}", max_tokens=900, temperature=0.4,
                               json_mode=True)
    try:
        found = parse_json(raw)
    except Exception:
        found = None
    if not isinstance(found, dict):
        return {"reply": re.sub(r"\s+", " ", raw).strip(), "actions": []}
    actions = [a for a in found.get("actions") or [] if isinstance(a, dict) and a.get("do") in ACTIONS][:3]
    for action in actions:
        if not isinstance(action.get("args"), dict):
            action["args"] = {}
    return {"reply": str(found.get("reply") or "").strip(), "actions": actions}


def run(shell: MainWindow, key: str, args: dict[str, Any]) -> None:
    """Do what an action card proposes."""
    words = {k: str(v) for k, v in args.items() if v not in (None, "")}
    if key == "image":
        shell.go("images", prompt=words.get("prompt", ""), create=bool(words.get("prompt")))
    elif key == "posts":
        shell.go("socials", prompt=words.get("brief", ""), create=bool(words.get("brief")))
    elif key == "plan_week":
        shell.go("socials", room="calendar")
        page = shell.pages.get("socials")
        calendar = getattr(page, "calendar", None)
        if calendar is not None:
            calendar.plan_week()
    elif key == "ad":
        shell.go("videos", ad=words or True)
    elif key == "film":
        shell.go("videos", template=True)
    elif key == "voice":
        shell.go("audio", mode="voice", text=words.get("text", ""))
    elif key == "music":
        shell.go("audio", mode="music", mood=words.get("mood", ""), seconds=words.get("seconds", ""))
    elif key == "game":
        shell.go("games", prompt=words.get("pitch", ""), create=bool(words.get("pitch")))
    elif key == "code":
        shell.go("coding", prompt=words.get("task", ""), focus=True)
    elif key == "edit":
        shell.go("editing")


class ActionCard(ui.Card):
    """One thing ELI proposes to make, with what it would make it from, and a button to do it."""

    def __init__(self, shell: MainWindow, key: str, args: dict[str, Any]) -> None:
        super().__init__(soft=True, padding=12, spacing=6)
        action = ACTIONS[key]
        accent = design.accent(action.studio)
        mark = QLabel()
        mark.setPixmap(icons.pixmap(action.icon, accent, 18))
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(mark)
        head.addWidget(ui.text(action.label, "small"), 1)
        head.addWidget(ui.text(design.STUDIOS[action.studio].name, "tiny", tone="muted"))
        self.add(head)
        detail = next((str(v) for v in args.values() if isinstance(v, str) and v.strip()), "")
        if detail:
            self.add(ui.text(detail[:220] + ("…" if len(detail) > 220 else ""), "tiny", tone="subtle", wrap=True))
        do = ui.button("Do it" if args else "Take me there", lambda: self._do(shell, key, args), primary=True,
                       icon="check" if args else "chevron_right")
        dismiss = ui.button("Not now", self.deleteLater, variant="flat")
        row = QHBoxLayout()
        row.addWidget(do)
        row.addWidget(dismiss)
        row.addStretch(1)
        self.add(row)
        self.setStyleSheet(f"QFrame[card=\"soft\"] {{ border: 1px solid {design.alpha(accent, 0.45)}; }}")

    def _do(self, shell: MainWindow, key: str, args: dict[str, Any]) -> None:
        run(shell, key, args)
        self.setEnabled(False)


def cards(shell: MainWindow, actions: list[dict[str, Any]]) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setSpacing(6)
    for action in actions:
        box.addWidget(ActionCard(shell, str(action["do"]), dict(action.get("args") or {})))
    return box
