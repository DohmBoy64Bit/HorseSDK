"""Parser for sound.xml."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class SoundEvent:
    name: str
    event_type: str
    file: Optional[str] = None
    volume: Optional[int] = None
    pitch: Optional[int] = None
    pitch_low: Optional[int] = None
    pitch_high: Optional[int] = None

    @staticmethod
    def from_xml(element: ET.Element, event_type: str) -> SoundEvent:
        a = element.attrib
        return SoundEvent(
            a.get("n", ""),
            event_type,
            a.get("f") or None,
            int(a["vol"]) if "vol" in a else None,
            int(a["pitch"]) if "pitch" in a else None,
            int(a["pitchlow"]) if "pitchlow" in a else None,
            int(a["pitchhigh"]) if "pitchhigh" in a else None,
        )


@dataclass
class SoundSet:
    music_events: List[SoundEvent] = field(default_factory=list)
    sound_events: List[SoundEvent] = field(default_factory=list)

    @staticmethod
    def load(file_path: str | Path) -> SoundSet:
        root = ET.parse(file_path).getroot()
        out = SoundSet()
        for elem in root:
            if elem.tag == "music":
                out.music_events.append(SoundEvent.from_xml(elem, "music"))
            elif elem.tag == "sound":
                out.sound_events.append(SoundEvent.from_xml(elem, "sound"))
        return out
