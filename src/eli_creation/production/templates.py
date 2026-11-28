"""Templates: a finished piece's plan with blanks for the person's own details: its scenes (what
each shows, how the camera moves, how long, the words on screen), its narration and its music.

Every word here is Creation Station's own. A template is filled from a few answers (the product,
its promise, the call to action); with the main model, ELI writes the specifics instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from eli_creation.production.project import Clip, Project, Scene, Step


@dataclass(frozen=True)
class Shot:
    title: str
    picture: str  # what the picture shows (a prompt, with {blanks})
    camera: str
    seconds: float
    words: str = ""  # on screen
    transition: str = "crossfade"


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    category: str
    format: str
    blurb: str
    shots: tuple[Shot, ...]
    narration: str
    mood: str
    style: str = "cinematic"
    look: str = "cinematic"


CATEGORIES = ("Ads", "Social media", "Product", "Film", "Trailer", "Event", "Promotional", "Explainer")

TEMPLATES: dict[str, Template] = {t.key: t for t in (
    Template("launch", "Product launch ad", "Ads", "youtube", "Reveal, three reasons, the call to act",
             (Shot("Reveal", "{product}, hero shot, dramatic light", "reveal", 3.5, "{product}"),
              Shot("Why", "{product} in use, {point1}", "push_in", 3.0, "{point1}"),
              Shot("Detail", "close detail of {product}, {point2}", "pan_right", 3.0, "{point2}"),
              Shot("Life", "people enjoying {product}, {point3}", "drift", 3.0, "{point3}"),
              Shot("Act", "{product} on a clean background", "pull_out", 3.5, "{cta}", "fade_black")),
             "Meet {product}. {tagline}. {point1}. {point2}. {point3}. {cta}.", "uplifting"),
    Template("square_ad", "Social media ad (square)", "Social media", "square", "Fast, bold, made for feeds",
             (Shot("Hook", "{product}, bold colours, eye-catching", "push_in", 2.5, "{tagline}"),
              Shot("Proof", "{product} close up, {point1}", "pan_left", 2.5, "{point1}"),
              Shot("Act", "{product} with space for text", "static", 3.0, "{cta}", "cut")),
             "{tagline}. {point1}. {cta}.", "electronic", style="neon", look="vivid"),
    Template("story_ad", "Story ad (vertical)", "Social media", "story", "Three beats for Stories and Reels",
             (Shot("Stop the scroll", "{product}, vertical composition, striking", "reveal", 2.5, "{tagline}"),
              Shot("Show it", "{product} in use, {point1}", "tilt_up", 3.0, "{point1}"),
              Shot("Swipe up", "{product}, clean background", "push_in", 2.5, "{cta}")),
             "{tagline}. {point1}. {cta}.", "electronic", look="vivid"),
    Template("promo", "Product promo (vertical)", "Product", "promo", "A tour of the product in five shots",
             (Shot("Hero", "{product}, studio product photograph", "reveal", 3.0, "{product}"),
              Shot("Feature one", "{product} detail, {point1}", "push_in", 3.0, "{point1}"),
              Shot("Feature two", "{product} detail, {point2}", "pan_right", 3.0, "{point2}"),
              Shot("Feature three", "{product} lifestyle, {point3}", "drift", 3.0, "{point3}"),
              Shot("Price and offer", "{product} with a gift box", "pull_out", 3.0, "{cta}")),
             "This is {product}. {point1}, {point2} and {point3}. {cta}.", "corporate", style="luxury", look="golden"),
    Template("trailer", "Cinematic trailer", "Trailer", "trailer", "Mood, mystery, the title, the date",
             (Shot("World", "wide establishing shot, {topic}, epic scale", "push_in", 4.0, ""),
              Shot("Hero", "a lone figure, {topic}, rim light", "drift", 3.5, ""),
              Shot("Threat", "dark storm, {topic}, tension", "tilt_down", 3.0, "{tagline}", "fade_black"),
              Shot("Title", "{topic}, iconic image", "reveal", 4.0, "{product}", "fade_black"),
              Shot("Date", "{topic}, sunrise", "pull_out", 3.0, "{cta}")),
             "In a world of {topic}, one story is about to begin. {tagline}. {product}. {cta}.", "epic",
             look="cinematic"),
    Template("short_film", "Cinematic short", "Film", "film", "A three-act short from a logline",
             (Shot("Opening", "{topic}, establishing shot at dawn", "push_in", 5.0, "{product}"),
              Shot("Arrival", "the hero arrives, {topic}", "pan_right", 5.0, ""),
              Shot("Discovery", "a discovery, {topic}, glowing", "push_in", 5.0, ""),
              Shot("Turn", "danger rises, {topic}, storm light", "tilt_up", 5.0, ""),
              Shot("Return", "the hero walks home at sunset, {topic}", "pull_out", 6.0, "{tagline}", "fade_black")),
             "{tagline}. {point1}. {point2}. {point3}.", "cinematic"),
    Template("event", "Event teaser", "Event", "square", "What, when, where, why come",
             (Shot("Mood", "{topic}, crowd, lights, energy", "push_in", 3.0, "{product}"),
              Shot("Date", "{topic}, stage, colourful light", "pan_left", 3.0, "{point1}"),
              Shot("Place", "{topic}, venue exterior at night", "drift", 3.0, "{point2}"),
              Shot("Tickets", "{topic}, confetti", "pull_out", 3.0, "{cta}")),
             "{product}. {point1}. {point2}. {cta}.", "electronic", style="neon", look="neon"),
    Template("explainer", "Explainer", "Explainer", "youtube", "Problem, solution, how, result",
             (Shot("Problem", "a frustrated person, {topic}", "push_in", 4.0, "The problem"),
              Shot("Solution", "{product}, clean and simple", "reveal", 4.0, "{product}"),
              Shot("How", "{product} in use, {point1}", "pan_right", 4.0, "{point1}"),
              Shot("Result", "a happy person, {point2}", "drift", 4.0, "{point2}"),
              Shot("Start", "{product} on a clean background", "pull_out", 4.0, "{cta}")),
             "Tired of {topic}? Meet {product}. {point1}. {point2}. {cta}.", "corporate", style="minimal", look="cool"),
    Template("testimonial", "Customer story", "Promotional", "feed", "A customer, their words, the result",
             (Shot("Who", "a friendly customer portrait, {topic}", "push_in", 3.5, "{point1}"),
              Shot("Before", "{topic}, before, muted", "pan_left", 3.5, ""),
              Shot("After", "{topic}, after, bright and happy", "pan_right", 3.5, "{point2}"),
              Shot("Brand", "{product}, logo on clean background", "static", 3.0, "{cta}")),
             "{point1}. Before {product}, {topic} was hard. Now, {point2}. {cta}.", "lofi", look="matte"),
    Template("intro", "Channel intro", "Promotional", "youtube", "Five seconds that say who you are",
             (Shot("Logo", "{product}, abstract glowing shapes", "reveal", 2.5, "{product}"),
              Shot("Promise", "{topic}, energetic", "push_in", 2.5, "{tagline}", "fade_white")),
             "", "electronic", style="neon", look="neon"),
)}


def blanks(template: Template) -> list[str]:
    import re

    found: list[str] = []
    text = " ".join([template.narration] + [s.picture + " " + s.words for s in template.shots])
    for name in re.findall(r"{(\w+)}", text):
        if name not in found:
            found.append(name)
    return found


class _Fill(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def fill(text: str, answers: dict[str, str]) -> str:
    out = text.format_map(_Fill({k: str(v).strip() for k, v in answers.items()}))
    return " ".join(out.replace(" .", ".").replace("..", ".").replace(" ,", ",").split()).strip(" .,") + (
        "." if text.endswith(".") and out.strip() else "")


def build(template: Template, answers: dict[str, str], *, title: str = "") -> tuple[Project, str]:
    """A project from a template, and the narration to speak. ``answers`` fills the blanks."""
    project = Project(title=title or answers.get("product") or template.name, format=template.format,
                      template=template.key, stage="produce")
    project.goal = template.blurb
    project.direction = f"{template.style.capitalize()} pictures, a {template.look} look, {template.mood} music"
    for shot in template.shots:
        scene = Scene(title=shot.title, description=fill(shot.picture, answers), camera=shot.camera,
                      seconds=shot.seconds, transition=shot.transition, title_text=fill(shot.words, answers))
        scene.grade.look = template.look
        project.scenes.append(scene)
    project.moments = [s.title for s in template.shots]
    project.steps = [Step("Check every picture"), Step("Listen to the narration"), Step("Export and share")]
    narration = fill(template.narration, answers) if template.narration else ""
    return project, narration


ELI_SYSTEM = ("You are ELI, a creative director. You write tight, vivid ad and film plans. Never invent facts "
              "about a real company beyond what you are told. Answer with JSON only.")


def eli_plan(generate: Any, template: Template, answers: dict[str, str]) -> dict[str, Any]:
    """ELI writes the specifics: each scene's picture, its words on screen, and the narration."""
    shots = [{"title": s.title, "camera": s.camera, "seconds": s.seconds} for s in template.shots]
    prompt = (f"Template: {template.name} ({template.blurb}). Format: {template.format}.\n"
              f"What we know: {json.dumps(answers, ensure_ascii=False)}\n"
              f"Shots: {json.dumps(shots)}\n"
              "For each shot write 'picture' (an image prompt of at most 30 words, concrete and visual) and "
              "'words' (at most 6 words on screen, or empty). Then 'narration': at most "
              f"{int(sum(s.seconds for s in template.shots) * 2.3)} words, spoken, warm and persuasive.\n"
              'Answer as {"shots": [{"picture": "...", "words": "..."}], "narration": "..."}')
    from eli_creation.engines.writing import parse_json

    answer = parse_json(generate(system=ELI_SYSTEM, prompt=prompt, max_tokens=1200, temperature=0.7, json_mode=True))
    return answer if isinstance(answer, dict) else {}


def apply_plan(project: Project, plan: dict[str, Any]) -> str:
    """ELI's plan written into the project. Returns the narration."""
    for scene, shot in zip(project.scenes, plan.get("shots") or [], strict=False):
        if isinstance(shot, dict):
            scene.description = str(shot.get("picture") or scene.description)[:400]
            scene.title_text = str(shot.get("words") or "")[:60]
    return str(plan.get("narration") or "").strip()


def music_clip(path: str, seconds: float) -> Clip:
    return Clip(kind="music", path=path, start=0.0, gain=0.75, label="Music", duration=seconds, fade_out=1.5)
