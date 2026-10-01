"""Calcula etiquetas SemVer a partir de commits convencionales.

Primera versión: v0.1.0. Después, `feat` incrementa minor,
`!`/BREAKING CHANGE incrementa major y el resto incrementa patch.
"""

import argparse
import re
import subprocess

TAG_PATTERN = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
BREAKING_PATTERN = re.compile(r"^[a-z]+(?:\([^)]*\))?!:", re.IGNORECASE | re.MULTILINE)
FEATURE_PATTERN = re.compile(r"^feat(?:\([^)]*\))?:", re.IGNORECASE | re.MULTILINE)


def parse_tag(tag: str) -> tuple[int, int, int] | None:
    match = TAG_PATTERN.fullmatch(tag)
    return tuple(map(int, match.groups())) if match else None


def next_tag(previous: str | None, messages: list[str]) -> str:
    if previous is None:
        return "v0.1.0"
    version = parse_tag(previous)
    if version is None:
        raise ValueError(f"Etiqueta inválida: {previous}")
    major, minor, patch = version
    if any(re.search(r"BREAKING[ -]CHANGE:", message, re.IGNORECASE) or BREAKING_PATTERN.search(message) for message in messages):
        major, minor, patch = major + 1, 0, 0
    elif any(FEATURE_PATTERN.search(message) for message in messages):
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"v{major}.{minor}.{patch}"


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def calculate() -> tuple[str, bool]:
    reachable = [tag for tag in git("tag", "--merged", "HEAD").splitlines() if parse_tag(tag)]
    if not reachable:
        return "v0.1.0", False
    previous = max(reachable, key=lambda tag: parse_tag(tag) or (-1, -1, -1))
    if previous in git("tag", "--points-at", "HEAD").splitlines():
        return previous, True
    log = git("log", "--format=%B%x00", f"{previous}..HEAD")
    messages = [message.strip() for message in log.split("\x00") if message.strip()]
    return next_tag(previous, messages), False


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--next", action="store_true")
    group.add_argument("--tag")
    args = parser.parse_args()
    if args.tag:
        if parse_tag(args.tag) is None:
            parser.error("La etiqueta debe tener formato vMAJOR.MINOR.PATCH")
        print(f"tag={args.tag}\nexisting_tag=true")
        return
    tag, existing = calculate()
    print(f"tag={tag}\nexisting_tag={str(existing).lower()}")


if __name__ == "__main__":
    main()
