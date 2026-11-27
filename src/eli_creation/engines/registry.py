"""Every engine, by tab, in the order the tab shows them."""

from __future__ import annotations

from eli_creation.engines.base import Engine
from eli_creation.engines.games import BrowserGame
from eli_creation.engines.visual import (
    Animatic,
    DiffusionImages,
    ImageEdits,
    Planned,
    ProceduralImages,
)
from eli_creation.engines.writing import Coding, GameDesign, SocialPosts

TABS = ("socials", "images", "videos", "games", "editing", "coding")

ENGINES: tuple[Engine, ...] = (
    SocialPosts(),
    Planned("socials.calendar", "socials", "Content calendar",
            "A month of posts across platforms from one brief, scheduled in a calendar you approve."),
    Planned("socials.thumbnail", "socials", "Thumbnails and cards",
            "A post's image in each platform's shape, from the Images tab's engines.", task="image"),
    DiffusionImages(),
    ProceduralImages(),
    Animatic(),
    Planned("videos.text_to_video", "videos", "Text or image to video",
            "Short clips from words or a still, with a local video model.", task="video"),
    Planned("videos.narration", "videos", "Narration",
            "A script read in a chosen voice (ELI v3's voices when opened from ELI v3).", task="speech"),
    Planned("videos.captions", "videos", "Captions and subtitles",
            "Words heard in a video, timed, in each platform's caption format.", task="transcription"),
    Planned("videos.music", "videos", "Music and sound",
            "A soundtrack or sound effects for a cut.", task="music"),
    GameDesign(),
    BrowserGame(),
    Planned("games.vr", "games", "Play it in ELI VR",
            "Set the game in ELI's rooms: the design's kinds are the ones ELI VR plays."),
    Planned("games.assets", "games", "3D assets",
            "Props and characters from an image, for a game or ELI VR's rooms.", task="3d"),
    ImageEdits(),
    Planned("editing.upscale", "editing", "AI upscale", "Enlarge with detail restored.", task="upscale"),
    Planned("editing.background", "editing", "Remove the background",
            "A clean cut-out of the subject.", task="background_removal"),
    Coding(),
)


def for_tab(tab: str) -> list[Engine]:
    return [e for e in ENGINES if e.tab == tab]


def get(engine_id: str) -> Engine:
    for engine in ENGINES:
        if engine.id == engine_id:
            return engine
    raise KeyError(engine_id)
