"""Upload filename sanitisation, container validation and collision handling."""

from pathlib import Path

import pytest

from app import config
from app.errors import UnsupportedMediaError
from app.uploads import safe_stem, unique_source_path, validate_suffix


@pytest.fixture
def source_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the upload helpers at an isolated source directory."""
    monkeypatch.setattr(config, "SOURCE_DIR", tmp_path)
    monkeypatch.setattr("app.uploads.SOURCE_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("suzume_animenz.webm", "suzume_animenz"),
        ("My Clip (final).mp4", "My-Clip-final"),
        ("../../etc/passwd.mp4", "passwd"),
        ("  spaced name .mkv", "spaced-name"),
        ("....mp4", "upload"),
        ("", "upload"),
        (None, "upload"),
        ("кириллица.mp4", "upload"),
    ],
)
def test_safe_stem(filename: str | None, expected: str) -> None:
    assert safe_stem(filename) == expected


def test_safe_stem_truncates_long_names() -> None:
    assert len(safe_stem("a" * 200 + ".mp4")) == config.MAX_UPLOAD_STEM_LENGTH


def test_safe_stem_never_escapes_the_media_directory(source_dir: Path) -> None:
    path = unique_source_path(safe_stem("../../../etc/shadow.mp4"), ".mp4")
    assert path.parent == source_dir


@pytest.mark.parametrize("filename", ["a.mp4", "a.WEBM", "a.MkV", "a.mov"])
def test_validate_suffix_accepts_video_containers(filename: str) -> None:
    assert validate_suffix(filename) == Path(filename).suffix.lower()


@pytest.mark.parametrize("filename", ["notes.md", "archive.zip", "noextension", "a.mp3", ""])
def test_validate_suffix_rejects_everything_else(filename: str) -> None:
    with pytest.raises(UnsupportedMediaError):
        validate_suffix(filename)


def test_unique_source_path_is_free_when_directory_is_empty(source_dir: Path) -> None:
    assert unique_source_path("clip", ".mp4") == source_dir / "clip.mp4"


def test_unique_source_path_never_overwrites(source_dir: Path) -> None:
    (source_dir / "clip.mp4").touch()
    assert unique_source_path("clip", ".mp4") == source_dir / "clip-2.mp4"

    (source_dir / "clip-2.mp4").touch()
    assert unique_source_path("clip", ".mp4") == source_dir / "clip-3.mp4"


def test_unique_source_path_ignores_container_when_detecting_collisions(source_dir: Path) -> None:
    """Source ids are extension-free, so clip.webm must not shadow clip.mp4."""
    (source_dir / "clip.webm").touch()
    assert unique_source_path("clip", ".mp4") == source_dir / "clip-2.mp4"
