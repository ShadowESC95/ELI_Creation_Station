"""Engines that write with the main model: posts for each platform, game designs, and code."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from eli_creation.engines.base import Engine, Progress
from eli_creation.library import slug
from eli_creation.provenance import manifest as manifests

if TYPE_CHECKING:
    from eli_creation.jobs import Job
    from eli_creation.services import Studio

# Each platform's limit for one post, in characters (as the platforms state them; check before
# relying on one, they change).
PLATFORMS: dict[str, tuple[str, int]] = {
    "x": ("X", 280),
    "threads": ("Threads", 500),
    "bluesky": ("Bluesky", 300),
    "instagram": ("Instagram caption", 2200),
    "tiktok": ("TikTok caption", 2200),
    "linkedin": ("LinkedIn post", 3000),
    "facebook": ("Facebook post", 5000),
    "youtube": ("YouTube description", 5000),
}


def parse_json(text: str) -> Any:
    """The first JSON value in a model's answer, tolerating a code fence or words around it."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    for opener in ("{", "["):
        start = text.find(opener)
        if start >= 0:
            try:
                return json.loads(text[start:])
            except ValueError:
                end = text.rfind("}" if opener == "{" else "]")
                if end > start:
                    try:
                        return json.loads(text[start : end + 1])
                    except ValueError:
                        pass
    raise ValueError("the model's answer held no JSON")


def _system(studio: Studio) -> str:
    from eli_creation.edition import policy

    return policy.system_prompt_addendum()


class SocialPosts(Engine):
    id = "socials.posts"
    tab = "socials"
    title = "Posts for each platform"
    summary = "Drafts of a post in your brand's voice, sized to each platform's limit."
    uses_main = True

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        r = job.request
        platforms = [p for p in r.get("platforms", ["x"]) if p in PLATFORMS] or ["x"]
        variants = max(1, min(5, int(r.get("variants", 3))))
        texts: list[str] = []
        for n, key in enumerate(platforms):
            label, limit = PLATFORMS[key]
            progress(n / len(platforms), f"Writing for {label}")
            prompt = (
                f"Write {variants} different {label} posts (each at most {limit} characters, hashtags "
                f"included) about: {r.get('brief', '')}\n"
                f"Audience: {r.get('audience') or 'general'}. Tone: {r.get('tone') or 'natural'}.\n"
                f"Brand voice notes: {r.get('voice') or 'none'}.\n"
                f"{'Include up to 4 relevant hashtags.' if r.get('hashtags', True) else 'No hashtags.'}\n"
                'Answer with JSON only: {"posts": [{"text": "..."}]}'
            )
            answer = studio.main.generate(system=_system(studio), prompt=prompt, max_tokens=1200,
                                          temperature=0.8, json_mode=True)
            try:
                posts = [str(p.get("text", "")).strip() for p in parse_json(answer).get("posts", [])]
            except (ValueError, AttributeError):
                posts = [answer.strip()]
            body = [f"# {label}: {r.get('brief', '')[:80]}", ""]
            for i, post in enumerate(posts, 1):
                over = len(post) - limit
                body += [f"## Draft {i} ({len(post)}/{limit} characters{', ' + str(over) + ' over' if over > 0 else ''})",
                         "", post, ""]
            text = "\n".join(body)
            texts.append(text)
            folder = studio.library.folder("post", r.get("project", ""))
            path = folder / f"{slug(r.get('brief', 'post'))}-{key}-{job.id}.md"
            path.write_text(text, encoding="utf-8")
            man = manifests.build(kind="post", engine=self.id, models=[self.describe_main(studio)],
                                  request={k: r.get(k) for k in ("platforms", "audience", "tone", "variants")},
                                  digital_source_type=manifests.TRAINED, project=r.get("project", ""))
            job.assets.append(studio.library.add(path, manifest=man, title=f"{label} posts", job=job.id))
        job.text = "\n\n".join(texts)


class GameDesign(Engine):
    id = "games.design"
    tab = "games"
    title = "Game design"
    summary = "A playable game's design from a short pitch: its kind, rules, look and pieces."
    uses_main = True
    # The kinds of game ELI v3's world sets (eli/world/games.py) and ELI VR plays (eli_play.gd).
    KINDS = ("targets", "catch", "sort", "order", "hide", "range")
    BROWSER_KINDS = ("targets", "catch")

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        r = job.request
        progress(0.1, "Designing")
        prompt = (
            f"Design a small game from this pitch: {r.get('pitch', '')}\n"
            f"Choose its kind from: {', '.join(self.KINDS)} (for a browser game, {' or '.join(self.BROWSER_KINDS)}).\n"
            "Answer with JSON only: {\"title\": ..., \"kind\": ..., \"goal\": ..., \"rules\": [...], "
            "\"seconds\": 45, \"pieces\": 12, \"palette\": [\"#hex\", \"#hex\", \"#hex\"], "
            "\"player\": ..., \"pieces_look\": ..., \"design_notes\": ...}"
        )
        answer = studio.main.generate(system=_system(studio), prompt=prompt, max_tokens=1200, temperature=0.7,
                                      json_mode=True)
        spec = parse_json(answer)
        if not isinstance(spec, dict):
            raise ValueError("the design was not an object")
        spec["kind"] = spec.get("kind") if spec.get("kind") in self.KINDS else "catch"
        progress(0.7, "Writing the design")
        folder = studio.library.folder("game", r.get("project", ""))
        name = slug(str(spec.get("title") or r.get("pitch") or "game"))
        design = folder / f"{name}-{job.id}.game.json"
        design.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        man = manifests.build(kind="game", engine=self.id, models=[self.describe_main(studio)],
                              request={"pitch_chars": len(str(r.get("pitch", "")))},
                              digital_source_type=manifests.TRAINED, project=r.get("project", ""))
        job.assets.append(studio.library.add(design, manifest=man, title=str(spec.get("title", "game")), job=job.id))
        job.text = json.dumps(spec, indent=2, ensure_ascii=False)


class Coding(Engine):
    id = "coding.agent"
    tab = "coding"
    title = "Code"
    summary = ("ELI v3's coding agent: it plans, writes, runs and repairs the code against tests it "
               "writes, on the main model.")
    uses_main = True

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.coding.agent import CodeAgent

        r = job.request
        progress(0.05, "Planning")
        agent = CodeAgent(generate=studio.main.as_generate(temperature=0.2))
        result = agent.solve(str(r.get("task", "")), language=str(r.get("language", "python")),
                             use_tests=bool(r.get("tests", True)), deadline=float(r.get("seconds", 240)))
        data = result.to_dict()
        code = str(data.get("code") or "")
        progress(0.9, "Saving")
        folder = studio.library.folder("code", r.get("project", ""))
        suffix = {"python": ".py", "javascript": ".js", "typescript": ".ts", "html": ".html", "gdscript": ".gd"}.get(
            str(r.get("language", "python")), ".txt")
        path = folder / f"{slug(str(r.get('task', 'code')))}-{job.id}{suffix}"
        path.write_text(code or "# the agent returned no code\n", encoding="utf-8")
        man = manifests.build(kind="code", engine=self.id, models=[self.describe_main(studio)],
                              request={"language": r.get("language"), "tests": r.get("tests", True),
                                       "score": data.get("score"), "solved": data.get("solved")},
                              digital_source_type=manifests.TRAINED, project=r.get("project", ""))
        job.assets.append(studio.library.add(path, manifest=man, title=path.stem, job=job.id))
        notes = {k: data.get(k) for k in ("solved", "score", "message") if k in data}
        job.text = code + ("\n\n# " + json.dumps(notes) if notes else "")


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
