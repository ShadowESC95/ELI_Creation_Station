"""The command line: ``eli-creation``. With no command it opens the desktop application.

    eli-creation                          the desktop application
    eli-creation licence [activate KEY | remove | buy]
    eli-creation bundle register [--if-eli-v3] | unregister [--this-copy] | show
    eli-creation hardware                 this machine, its tier, and what each feature needs
    eli-creation models [list | folders]  the models known, and where their files go
    eli-creation selftest                 make an image, an edit and an animatic; check the ledger
    eli-creation --version

The licence and bundle commands are ELI Legal's, word for word where they can be, so the
installers and ELI v3 speak to every bundle the same way.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eli_creation import TITLE, __version__


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_gui(_args: argparse.Namespace) -> int:
    from eli_creation.gui.app import main as gui_main

    return int(gui_main([]))


def cmd_licence(args: argparse.Namespace) -> int:
    from eli_sdk import InvalidKey

    from eli_creation import licensing

    if args.licence_cmd == "activate":
        try:
            lic = licensing.activate(args.key)
        except InvalidKey as exc:
            print(f"Not activated: {exc}", file=sys.stderr)
            return 3
        print(f"Activated: {lic.tier}, {lic.seats} seat(s). {licensing.standing().describe()}")
        return 0
    if args.licence_cmd == "deactivate":
        try:
            done = licensing.deactivate()
        except InvalidKey as exc:
            print(f"Not deactivated: {exc}", file=sys.stderr)
            return 2
        print("Deactivated: this computer's seat is free for another computer."
              if done else "There was no key on this computer to deactivate.")
        return 0
    if args.licence_cmd == "code":
        from eli_sdk.store import activate_page, manage_page

        print(f"This computer's activation code:\n  {licensing.activation_code()}")
        print(f"No internet here? Activate it from any other device at {activate_page(licensing.STORE_URL)}")
        print(f"Your computers, and releasing one you no longer have: {manage_page(licensing.STORE_URL)}")
        return 0
    if args.licence_cmd == "refresh":
        licensing.refresh_online()
        print(licensing.standing().describe())
        return 0
    if args.licence_cmd == "remove":
        print("Removed." if licensing.remove() else "There was no ELI Creation Station key to remove.")
        return 0
    if args.licence_cmd == "buy":
        print(f"Buy a licence: {licensing.buy_link()}\nThe key arrives by email: eli-creation licence activate YOUR-KEY")
        return 0
    st = licensing.standing()
    _print({"licensed": st.granted, "reason": st.reason, "on_trial": st.on_trial, "days_left": st.days_left,
            "describe": st.describe()})
    return 0 if st.granted else 3


def cmd_bundle(args: argparse.Namespace) -> int:
    from eli_creation import bundle

    target = Path(args.target) if getattr(args, "target", None) else None
    if args.bundle_cmd == "register":
        if getattr(args, "if_eli_v3", False) and target is None and not bundle.eli_v3_present():
            return 0
        path = bundle.register(target)
        print(f"registered with ELI v3: {path}\nELI v3 will offer to open {TITLE} (its Bundles menu, or: eli --bundle creation)")
        return 0
    if args.bundle_cmd == "unregister":
        removed = bundle.unregister(target, this_copy=getattr(args, "this_copy", False))
        print("\n".join(f"removed {p}" for p in removed) or "nothing was registered")
        return 0
    _print({**bundle.describe(), "command": bundle.own_command(),
            "registers_in": [str(p) for p in bundle.v3_bundle_dirs()]})
    return 0


def cmd_hardware(_args: argparse.Namespace) -> int:
    from eli_creation.engines import registry
    from eli_creation.models import catalogue
    from eli_creation.tiers import TIER_EXAMPLES, TIER_LABELS, probe

    machine = probe()
    cat = catalogue.load()
    specialists = []
    for spec in cat.models:
        ok, why = spec.runs_here(machine)
        specialists.append({"id": spec.id, "role": spec.role, "runs_here": ok, "note": why,
                            "status": "planned" if spec.planned else "available"})
    _print({"machine": machine.to_dict(), "tier": machine.tier, "tier_label": TIER_LABELS[machine.tier],
            "tier_examples": TIER_EXAMPLES[machine.tier], "models": specialists,
            "features": [{"id": e.id, "tab": e.tab, "planned": e.planned, "needs": e.task or ("main model" if e.uses_main else "nothing")}
                         for e in registry.ENGINES]})
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    from eli_creation.layout import layout
    from eli_creation.models import catalogue, folders

    if args.models_cmd == "folders":
        root = layout().models
        made = folders.ensure(root)
        _print({"root": str(root), "folders": [{"name": f.name, "holds": f.holds, "private": f.private}
                                               for f in folders.FOLDERS], "made": len(made)})
        return 0
    cat = catalogue.load()
    _print({"models": [m.to_dict() for m in cat.models],
            "never_fetched": [{"match": e.match, "licence": e.licence, "why": e.why} for e in cat.excluded]})
    return 0


def cmd_selftest(_args: argparse.Namespace) -> int:
    """What a release build runs to show it works on the machine it was built for (as ELI Legal's
    builds run `eli-legal demo`): no model, no network."""
    import tempfile

    from PIL import Image

    from eli_creation.layout import Layout
    from eli_creation.models.main import make_main_model
    from eli_creation.services import Studio
    from eli_creation.settings import Settings

    with tempfile.TemporaryDirectory(prefix="eli-creation-selftest-") as tmp:
        settings = Settings(main_model_source="none")
        studio = Studio(where=Layout(Path(tmp)), settings=settings, hosted=False,
                        main=make_main_model(settings, hosted=False))
        try:
            image = studio.queue.wait(studio.submit("images.procedural", {"prompt": "a lighthouse at dusk", "count": 1,
                                                                        "aspect": "landscape"}))
            print(f"image: {image.state} {image.error}")
            first = image.assets[0].path
            edit = studio.queue.wait(studio.submit("editing.image", {"path": str(first), "ops": [
                {"op": "crop_aspect", "aspect": "9:16"}, {"op": "caption", "text": "ELI"}], "format": "png"}))
            print(f"edit: {edit.state} {edit.error}")
            film = studio.queue.wait(studio.submit("videos.animatic", {"images": [str(first), str(edit.assets[0].path)],
                                                                       "seconds": 0.5}))
            print(f"animatic: {film.state} {film.error}")
            ok, why = studio.ledger.verify()
            print(f"ledger: {studio.ledger.count()} entries, {'whole' if ok else 'BROKEN: ' + why}")
            with Image.open(first) as im:
                marked = "XML:com.adobe.xmp" in getattr(im, "text", {})
            print(f"marking: {'present' if marked else 'MISSING'}")
            passed = all(j.state == "done" for j in (image, edit, film)) and ok and marked
        finally:
            studio.close()
    print("selftest passed" if passed else "selftest FAILED")
    return 0 if passed else 1


def cmd_worker(_args: argparse.Namespace) -> int:
    from eli_creation.runtimes.worker import serve

    return serve()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eli-creation", description=TITLE)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="the desktop application").set_defaults(func=cmd_gui)

    lic = sub.add_parser("licence", aliases=["license"], help="this copy's licence")
    lic.set_defaults(func=cmd_licence, licence_cmd="status")
    ls = lic.add_subparsers(dest="licence_cmd")
    ls.add_parser("status")
    ls.add_parser("activate").add_argument("key")
    ls.add_parser("remove", help="forget the key here, without giving its seat back (deactivate does)")
    ls.add_parser("deactivate", help="give this computer's seat back, so the licence can move to another")
    ls.add_parser("code", help="this computer's activation code, for activating it from another device")
    ls.add_parser("refresh", help="when online: the newest revocation lists, and the trial held to the store's")
    ls.add_parser("buy")

    b = sub.add_parser("bundle", help="tell ELI v3 where this copy is")
    b.set_defaults(func=cmd_bundle, bundle_cmd="show")
    bs = b.add_subparsers(dest="bundle_cmd")
    reg = bs.add_parser("register")
    reg.add_argument("--if-eli-v3", action="store_true", help="only when ELI v3 is on this machine")
    reg.add_argument("--target", help=argparse.SUPPRESS)
    un = bs.add_parser("unregister")
    un.add_argument("--this-copy", action="store_true", help="only a record that names this copy")
    un.add_argument("--target", help=argparse.SUPPRESS)
    bs.add_parser("show")

    sub.add_parser("hardware", help="this machine, its tier, what each feature needs").set_defaults(func=cmd_hardware)
    m = sub.add_parser("models", help="the models known, and their folders")
    m.set_defaults(func=cmd_models, models_cmd="list")
    m.add_argument("models_cmd", nargs="?", choices=["list", "folders"], default="list")
    sub.add_parser("selftest", help="check this copy works, with no model").set_defaults(func=cmd_selftest)
    sub.add_parser("_worker", help=argparse.SUPPRESS).set_defaults(func=cmd_worker)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "func", None):
        return cmd_gui(args)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
