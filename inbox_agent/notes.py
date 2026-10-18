"""Find the parts of the shop notes that answer an email.

Plain word overlap, with rare words counting more. For a few pages of notes this is enough,
and you can always see why a section was picked. Swap in embeddings when the notes grow.
"""
import math
import os
import re
from dataclasses import dataclass

STOP = set("a an and are at be by can do does for from get had has have hi how i if in is it "
           "its like me my no not of off on or our please so that the there this to up was we "
           "what when where which will with would you your".split())


@dataclass
class Note:
    source: str   # "file.md#Heading", so every reply can be traced to the notes it used
    text: str


def stem(word):
    # Crude suffix stripping, so "serviced" finds "service" and "brakes" finds "brake".
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def words(text):
    return {stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1}


def load(folder):
    """Every '## Heading' section of every .md file in the folder is one note."""
    notes = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".md"):
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                sections = re.split(r"(?m)^## ", fh.read())[1:]
            for section in sections:
                heading, _, body = section.partition("\n")
                notes.append(Note(f"{name}#{heading.strip()}", f"{heading.strip()}\n{body.strip()}"))
    return notes


def search(query, notes, k=3):
    asked = words(query)
    seen_in = {}
    for note in notes:
        for w in words(note.text):
            seen_in[w] = seen_in.get(w, 0) + 1

    def score(note):
        return sum(math.log(1 + len(notes) / seen_in[w]) for w in asked & words(note.text))

    ranked = sorted(notes, key=score, reverse=True)
    return [note for note in ranked[:k] if score(note) > 0]
