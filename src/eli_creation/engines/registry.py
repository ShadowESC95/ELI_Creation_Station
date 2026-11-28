"""Every engine, by tab, in the order the tab shows them."""

from __future__ import annotations

from eli_creation.engines.base import Engine
from eli_creation.engines.games import BrowserGame
from eli_creation.engines.production import (
    AdMaker,
    Film,
    GameTemplate,
    Music,
    Narration,
    PlatformCards,
    SoundEffect,
    Transcribe,
)
from eli_creation.engines.visual import (
    Animatic,
    DiffusionImages,
    ImageEdits,
    Planned,
    ProceduralImages,
)
from eli_creation.engines.writing import Coding, GameDesign, SocialPosts

TABS = ("socials", "images", "videos", "audio", "games", "editing", "coding")

ENGINES: tuple[Engine, ...] = (
    SocialPosts(),
    Planned("socials.calendar", "socials", "Content calendar",
            "A month of posts across platforms from one brief, scheduled in a calendar you approve."),
    PlatformCards(),
    DiffusionImages(),
    ProceduralImages(),
    Film(),
    AdMaker(),
    Animatic(),
    Planned("videos.text_to_video", "videos", "Text or image to video",
            "Short clips from words or a still, with a local video model.", task="video"),
    Narration(),
    Music(),
    SoundEffect(),
    Transcribe(),
    Planned("audio.music_model", "audio", "Music with a model",
            "Songs and scores from a description, with a local music model.", task="music"),
    GameDesign(),
    GameTemplate(),
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
