"""End-to-end test: YAML → Loader.load → Loader.export → reopen .apkg."""

import os
import zipfile

from ankicli.loader import Loader, parse_cards


def test_roundtrip_yaml_to_apkg(tmp_path, anki_dir, media_dir):
  yaml_path = tmp_path / "cards.yaml"
  yaml_path.write_text(
    "- type: Basic\n"
    "  tags: [smoke]\n"
    "  fields:\n"
    "    Front: hello\n"
    "    Back: world\n"
    "- type: Basic\n"
    "  tags: []\n"
    "  fields:\n"
    "    Front: '<img src=\"car.jpg\" />'\n"
    "    Back: voiture\n",
    encoding="utf-8",
  )
  cards = parse_cards(str(yaml_path))
  assert len(cards) == 2

  loader = Loader(anki_dir, media_dir)
  loader.load(cards, deck_name='Default')

  archive = str(tmp_path / "out.apkg")
  loader.export(archive)
  loader.col.close()

  assert os.path.exists(archive)
  # An .apkg is a zip containing collection.anki2 (or .anki21) and a media manifest.
  with zipfile.ZipFile(archive) as z:
    names = set(z.namelist())
  assert any(n.startswith("collection.anki2") for n in names) or "collection.anki21" in names
  assert "media" in names
