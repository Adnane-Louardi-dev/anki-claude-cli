"""Shared fixtures for tests that need a real Anki collection.

Tests in `test_loader.py` and `test_e2e.py` require the `anki` package and
will be skipped automatically if it is not importable in the environment.
"""

import os
import shutil

import pytest

anki = pytest.importorskip("anki", reason="anki package not installed")
from anki.storage import Collection  # noqa: E402


@pytest.fixture
def anki_dir(tmp_path):
  """A fresh per-test Anki user directory.

  Mirrors the temp-dir bootstrap that `cli.py` does for sandbox runs:
  Anki's Collection() will populate `collection.anki2` with default
  decks and note types on first open.
  """
  user_dir = tmp_path / "User 1"
  user_dir.mkdir()
  yield str(user_dir)


@pytest.fixture
def fresh_collection(anki_dir):
  """A bare Collection opened against the empty anki_dir."""
  col = Collection(os.path.join(anki_dir, "collection.anki2"))
  yield col
  col.close()


@pytest.fixture
def media_dir(tmp_path):
  """Directory with a small image and sound file the loader can pick up."""
  d = tmp_path / "media"
  d.mkdir()
  # Minimal valid PNG (1x1 transparent pixel).
  (d / "car.jpg").write_bytes(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff"
    b"\xff?\x03\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
  )
  # Anything will do for the audio fixture; loader doesn't decode it.
  (d / "voiture.mp3").write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")
  yield str(d)
