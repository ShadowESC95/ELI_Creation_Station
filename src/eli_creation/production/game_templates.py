"""Game designs ready to play or to change, for when there is no main model to design one from a
pitch (and as starting points when there is). The kinds are the ones ELI VR plays; ``catch`` and
``targets`` also play in a browser."""

from __future__ import annotations

from typing import Any

DESIGNS: dict[str, dict[str, Any]] = {
    "star_catcher": {
        "title": "Star Catcher", "kind": "catch",
        "goal": "Catch the falling stars before they hit the ground; each round they fall faster.",
        "rules": ["Move the basket with the mouse, a finger or the arrow keys", "A caught star is a point",
                  "A missed star is a miss"],
        "seconds": 45, "pieces": 14, "palette": ["#facc15", "#22d3ee", "#a78bfa"],
        "player": "a glowing basket", "pieces_look": "five-pointed stars with trails",
        "design_notes": "Calm night-sky colours; the stars speed up every ten seconds."},
    "target_rush": {
        "title": "Target Rush", "kind": "targets",
        "goal": "Tap each target before it fades. Speed and accuracy both count.",
        "rules": ["Targets appear anywhere on the screen", "Tap one before it fades for a point",
                  "A faded target is a miss"],
        "seconds": 40, "pieces": 20, "palette": ["#f637ec", "#22d3ee", "#34f5c5"],
        "player": "your finger or cursor", "pieces_look": "neon rings that pulse",
        "design_notes": "Arcade energy: bright rings on a dark grid."},
    "fruit_drop": {
        "title": "Fruit Drop", "kind": "catch",
        "goal": "Fill the bowl with falling fruit; let none hit the floor.",
        "rules": ["Slide the bowl left and right", "Every fruit caught is a point", "Missed fruit counts against you"],
        "seconds": 50, "pieces": 16, "palette": ["#fb923c", "#facc15", "#34d399"],
        "player": "a wooden bowl", "pieces_look": "round, bright fruit", "design_notes": "Warm and friendly, for all ages."},
    "bubble_pop": {
        "title": "Bubble Pop", "kind": "targets",
        "goal": "Pop the bubbles as they float up; the small ones are worth catching quickly.",
        "rules": ["Tap a bubble to pop it", "Bubbles that float away are misses"],
        "seconds": 45, "pieces": 24, "palette": ["#7dd3fc", "#c4b5fd", "#f9a8d4"],
        "player": "your finger or cursor", "pieces_look": "soft pastel bubbles", "design_notes": "Relaxing, pastel."},
    "meteor_shield": {
        "title": "Meteor Shield", "kind": "catch",
        "goal": "Hold the shield under the meteors to protect the city below.",
        "rules": ["Move the shield to block meteors", "A blocked meteor is a point", "A meteor that lands is a miss"],
        "seconds": 60, "pieces": 18, "palette": ["#ef4444", "#f97316", "#22d3ee"],
        "player": "an energy shield", "pieces_look": "burning meteors", "design_notes": "Tense; faster in the last 20 seconds."},
    "logo_hunt": {
        "title": "Logo Hunt", "kind": "targets",
        "goal": "Tap your brand's logo wherever it appears: a playable ad for a campaign.",
        "rules": ["Tap the logo before it disappears", "Every logo tapped is a point"],
        "seconds": 30, "pieces": 15, "palette": ["#22d3ee", "#f637ec", "#ffffff"],
        "player": "your finger or cursor", "pieces_look": "your brand's mark",
        "design_notes": "Short and sharable: end on your call to action."},
}
