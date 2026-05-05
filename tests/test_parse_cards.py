import textwrap

import pytest

from ankicli.loader import CardSchemaError, parse_cards


def write(tmp_path, content):
  path = tmp_path / "cards.yaml"
  path.write_text(textwrap.dedent(content), encoding="utf-8")
  return str(path)


def test_valid_minimal_card(tmp_path):
  path = write(tmp_path, """
    - type: Basic
      fields:
        Front: hello
        Back: world
  """)
  cards = parse_cards(path)
  assert len(cards) == 1
  assert cards[0]['type'] == 'Basic'
  assert cards[0]['tags'] == []
  assert cards[0]['fields'] == {'Front': 'hello', 'Back': 'world'}


def test_tags_default_to_empty_list(tmp_path):
  path = write(tmp_path, """
    - type: Basic
      fields:
        Front: a
        Back: b
  """)
  assert parse_cards(path)[0]['tags'] == []


def test_tags_preserved_when_present(tmp_path):
  path = write(tmp_path, """
    - type: Basic
      tags: [foo, bar]
      fields:
        Front: a
        Back: b
  """)
  assert parse_cards(path)[0]['tags'] == ['foo', 'bar']


def test_empty_file_returns_empty_list(tmp_path):
  path = tmp_path / "cards.yaml"
  path.write_text("", encoding="utf-8")
  assert parse_cards(str(path)) == []


def test_missing_type_raises(tmp_path):
  path = write(tmp_path, """
    - fields:
        Front: a
        Back: b
  """)
  with pytest.raises(CardSchemaError, match="missing required 'type'"):
    parse_cards(path)


def test_missing_fields_raises(tmp_path):
  path = write(tmp_path, """
    - type: Basic
  """)
  with pytest.raises(CardSchemaError, match="missing required 'fields'"):
    parse_cards(path)


def test_top_level_must_be_list(tmp_path):
  path = write(tmp_path, """
    type: Basic
    fields:
      Front: a
      Back: b
  """)
  with pytest.raises(CardSchemaError, match="list of cards"):
    parse_cards(path)


def test_card_must_be_mapping(tmp_path):
  path = write(tmp_path, """
    - "just a string"
  """)
  with pytest.raises(CardSchemaError, match="not a mapping"):
    parse_cards(path)


def test_type_must_be_string(tmp_path):
  path = write(tmp_path, """
    - type: 42
      fields:
        Front: a
        Back: b
  """)
  with pytest.raises(CardSchemaError, match="'type' must be a string"):
    parse_cards(path)


def test_fields_must_be_mapping(tmp_path):
  path = write(tmp_path, """
    - type: Basic
      fields: [a, b]
  """)
  with pytest.raises(CardSchemaError, match="'fields' must be a mapping"):
    parse_cards(path)


def test_tags_must_be_list(tmp_path):
  path = write(tmp_path, """
    - type: Basic
      tags: "not a list"
      fields:
        Front: a
        Back: b
  """)
  with pytest.raises(CardSchemaError, match="'tags' must be a list"):
    parse_cards(path)


def test_error_includes_card_index(tmp_path):
  path = write(tmp_path, """
    - type: Basic
      fields: {Front: a, Back: b}
    - type: Basic
  """)
  with pytest.raises(CardSchemaError, match="Card #2"):
    parse_cards(path)
