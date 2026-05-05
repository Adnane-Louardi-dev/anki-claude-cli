"""Tests for ankicli.loader.Loader against a real Anki collection.

These require the `anki` package; the conftest.py importorskip will
skip the whole module if anki is missing.
"""

import os

import pytest

from ankicli.loader import (
  Loader,
  UnknownFieldError,
  UnknownNoteTypeError,
)


def test_basic_note_loaded(anki_dir, media_dir):
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Basic',
      'tags': [],
      'fields': {'Front': 'bonjour', 'Back': 'hello'},
    }],
    deck_name='Default',
  )
  assert loader.col.card_count() == 1
  notes = loader.col.find_notes("")
  assert len(notes) == 1
  note = loader.col.get_note(notes[0])
  assert note['Front'] == 'bonjour'
  assert note['Back'] == 'hello'
  loader.col.close()


def test_field_mapping_is_by_name_not_dict_order(anki_dir, media_dir):
  """Even with Back declared before Front in YAML, Front must end up in field 0."""
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Basic',
      'tags': [],
      'fields': {'Back': 'hello', 'Front': 'bonjour'},
    }],
    deck_name='Default',
  )
  note = loader.col.get_note(loader.col.find_notes("")[0])
  assert note['Front'] == 'bonjour'
  assert note['Back'] == 'hello'
  loader.col.close()


def test_unknown_note_type_raises(anki_dir, media_dir):
  loader = Loader(anki_dir, media_dir)
  with pytest.raises(UnknownNoteTypeError, match="Unknown note type 'NotARealType'"):
    loader.load(
      [{'type': 'NotARealType', 'tags': [], 'fields': {'X': 'y'}}],
      deck_name='Default',
    )
  loader.col.close()


def test_unknown_field_raises(anki_dir, media_dir):
  loader = Loader(anki_dir, media_dir)
  with pytest.raises(UnknownFieldError, match="no field"):
    loader.load(
      [{'type': 'Basic', 'tags': [], 'fields': {'NotAField': 'x'}}],
      deck_name='Default',
    )
  loader.col.close()


def test_deck_auto_created_when_missing(anki_dir, media_dir):
  """Loader creates the deck on demand. Each input file → its own deck."""
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{'type': 'Basic', 'tags': [], 'fields': {'Front': 'a', 'Back': 'b'}}],
    deck_name='chapter-3',
  )
  deck_names = {d['name'] for d in loader.col.decks.all()}
  assert 'chapter-3' in deck_names
  loader.col.close()


def test_existing_deck_is_reused(anki_dir, media_dir):
  """Loading twice with the same deck_name must not create a duplicate deck."""
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{'type': 'Basic', 'tags': [], 'fields': {'Front': 'a', 'Back': 'b'}}],
    deck_name='reused',
  )
  loader.load(
    [{'type': 'Basic', 'tags': [], 'fields': {'Front': 'c', 'Back': 'd'}}],
    deck_name='reused',
  )
  reused_decks = [d for d in loader.col.decks.all() if d['name'] == 'reused']
  assert len(reused_decks) == 1
  loader.col.close()


def test_image_media_copied(anki_dir, media_dir):
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Basic',
      'tags': [],
      'fields': {'Front': '<img src="car.jpg" />', 'Back': 'voiture'},
    }],
    deck_name='Default',
  )
  assert os.path.exists(os.path.join(loader.col.media.dir(), 'car.jpg'))
  loader.col.close()


def test_sound_media_copied(anki_dir, media_dir):
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Basic',
      'tags': [],
      'fields': {'Front': 'bonjour', 'Back': '[sound:voiture.mp3] Voiture'},
    }],
    deck_name='Default',
  )
  assert os.path.exists(os.path.join(loader.col.media.dir(), 'voiture.mp3'))
  loader.col.close()


def test_missing_media_warns_does_not_crash(anki_dir, media_dir, capsys):
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Basic',
      'tags': [],
      'fields': {'Front': '<img src="missing.jpg" />', 'Back': 'b'},
    }],
    deck_name='Default',
  )
  out = capsys.readouterr().out
  assert "Ignoring media file 'missing.jpg'" in out
  assert loader.col.card_count() == 1
  loader.col.close()


def test_tags_applied(anki_dir, media_dir):
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Basic',
      'tags': ['idiom', 'french'],
      'fields': {'Front': 'a', 'Back': 'b'},
    }],
    deck_name='Default',
  )
  note = loader.col.get_note(loader.col.find_notes("")[0])
  assert 'idiom' in note.tags
  assert 'french' in note.tags
  loader.col.close()


def test_cloze_note(anki_dir, media_dir):
  """Cloze is a stock model with a different field set; verifies non-Basic too."""
  loader = Loader(anki_dir, media_dir)
  loader.load(
    [{
      'type': 'Cloze',
      'tags': [],
      'fields': {'Text': 'The capital of France is {{c1::Paris}}.', 'Back Extra': ''},
    }],
    deck_name='Default',
  )
  assert loader.col.card_count() == 1
  loader.col.close()
