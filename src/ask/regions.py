"""Region detection for excluded content in session files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class Region:
    """A region of content to exclude from parsing."""

    type: Literal["code-fence", "expanded-dir", "expanded-url", "expanded-file"]
    start: int
    end: int


def find_excluded_regions(lines: list[str]) -> list[Region]:
    """Find all regions that should be excluded from turn detection."""
    regions: list[Region] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for code fence
        fence_match = re.match(r"^(`{3,})", line)
        if fence_match:
            fence = fence_match.group(1)
            start = i
            i += 1
            while i < len(lines):
                closing_match = re.match(r"^(`{3,})\s*$", lines[i])
                if closing_match and len(closing_match.group(1)) >= len(fence):
                    break
                i += 1
            regions.append(Region(type="code-fence", start=start, end=i))
            i += 1
            continue

        # Check for expanded directory
        if re.match(r"^<!-- dir: .+ -->$", line):
            start = i
            i += 1
            while i < len(lines) and not re.match(r"^<!-- /dir -->$", lines[i]):
                i += 1
            regions.append(Region(type="expanded-dir", start=start, end=i))
            i += 1
            continue

        # Check for expanded URL
        if re.match(r"^<!-- url: .+ -->$", line):
            start = i
            i += 1
            while i < len(lines) and not re.match(r"^<!-- /url -->$", lines[i]):
                i += 1
            regions.append(Region(type="expanded-url", start=start, end=i))
            i += 1
            continue

        # Check for expanded file
        if re.match(r"^<!-- file: .+ -->$", line):
            start = i
            i += 1
            while i < len(lines) and not re.match(r"^<!-- /file -->$", lines[i]):
                i += 1
            regions.append(Region(type="expanded-file", start=start, end=i))
            i += 1
            continue

        i += 1

    return regions


def is_in_excluded_region(line_index: int, regions: list[Region]) -> bool:
    """Check if a line index is within any excluded region."""
    return any(r.start <= line_index <= r.end for r in regions)
