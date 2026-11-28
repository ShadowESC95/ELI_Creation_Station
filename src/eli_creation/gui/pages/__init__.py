"""The window's pages, one per studio, with Home, the library and the settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.gui.pages.base import Page


def build_pages(shell: MainWindow) -> dict[str, Page]:
    from eli_creation.gui.pages.audio import AudioPage
    from eli_creation.gui.pages.coding import CodingPage
    from eli_creation.gui.pages.editing import EditingPage
    from eli_creation.gui.pages.film import FilmPage
    from eli_creation.gui.pages.games import GamesPage
    from eli_creation.gui.pages.home import HomePage
    from eli_creation.gui.pages.images import ImagesPage
    from eli_creation.gui.pages.library import LibraryPage
    from eli_creation.gui.pages.settings import SettingsPage
    from eli_creation.gui.pages.socials import SocialsPage

    pages: list[Page] = [HomePage(shell), SocialsPage(shell), ImagesPage(shell), FilmPage(shell), AudioPage(shell),
                         GamesPage(shell), EditingPage(shell), CodingPage(shell), LibraryPage(shell),
                         SettingsPage(shell)]
    return {page.key: page for page in pages}
