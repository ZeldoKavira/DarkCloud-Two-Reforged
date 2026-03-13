"""Changelog entries keyed by version tag."""

CHANGELOG = {
    "v0.1.0": [
        "* Initial release — base mod framework",
    ],
}

VERSIONS = sorted(CHANGELOG.keys(), reverse=True)


def get_changes_since(old_version, include_current=None):
    """Return changelog text for all versions newer than old_version."""
    lines = []
    count = 0
    if include_current and include_current in CHANGELOG:
        lines.append(f"^Y{include_current}")
        for entry in CHANGELOG[include_current]:
            lines.append(f"^W- {entry}")
        count += 1
    for ver in VERSIONS:
        if count >= 3:
            break
        if ver == include_current:
            continue
        if old_version and ver <= old_version:
            break
        lines.append(f"^Y{ver}")
        for entry in CHANGELOG[ver]:
            lines.append(f"^W- {entry}")
        count += 1
    if not lines:
        return None
    lines.append("^s^WFull changelog at github.com/ZeldoKavira/DarkCloud-Two-Reforged")
    return "\n".join(lines)
