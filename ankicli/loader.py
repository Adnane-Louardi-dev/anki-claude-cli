import os
import re
import yaml

from anki.storage import Collection
from anki.exporting import AnkiPackageExporter


SOUND_RE = re.compile(r"(?i)\[sound:(.*?)\]")
IMG_RE = re.compile(r'(?i)<img\s+src="(.*?)"\s*/?>')


class CardSchemaError(ValueError):
  """Raised when a card in the input YAML is missing required keys or has the wrong shape."""


class UnknownNoteTypeError(ValueError):
  """Raised when a card's `type` does not match any note type in the Anki collection."""


class UnknownFieldError(ValueError):
  """Raised when a card lists a field name that the note type does not define."""


def parse_cards(path):
  """Parse and shallow-validate the input YAML file.

  Returns a list of card dicts. Each card is guaranteed to have `type` (str),
  `tags` (list, defaulted to []), and `fields` (dict). Anki-aware validation
  (note type and field names exist in the collection) happens later in
  `Loader.load`.
  """
  with open(path) as file:
    cards = yaml.full_load(file) or []

  if not isinstance(cards, list):
    raise CardSchemaError("Input YAML must be a list of cards at the top level.")

  for i, card in enumerate(cards):
    if not isinstance(card, dict):
      raise CardSchemaError("Card #%d is not a mapping." % (i + 1))
    if 'type' not in card:
      raise CardSchemaError("Card #%d is missing required 'type'." % (i + 1))
    if not isinstance(card['type'], str):
      raise CardSchemaError("Card #%d 'type' must be a string." % (i + 1))
    if 'fields' not in card:
      raise CardSchemaError("Card #%d is missing required 'fields'." % (i + 1))
    if not isinstance(card['fields'], dict):
      raise CardSchemaError("Card #%d 'fields' must be a mapping." % (i + 1))
    card.setdefault('tags', [])
    if not isinstance(card['tags'], list):
      raise CardSchemaError("Card #%d 'tags' must be a list." % (i + 1))

  return cards


class Loader:

  def __init__(self, anki_dir, media_dir):
    self.anki_dir = anki_dir
    self.media_dir = os.path.realpath(media_dir)
    self.cwd = os.getcwd()
    self._open_collection()

  def _open_collection(self):
    anki_collection_path = os.path.join(self.anki_dir, "collection.anki2")
    print("📂 Opening Anki collection...")
    self.col = Collection(anki_collection_path)

  def _resolve_notetype(self, model_name):
    notetype = self.col.models.by_name(model_name)
    if notetype is None:
      known = sorted(m['name'] for m in self.col.models.all())
      raise UnknownNoteTypeError(
        "Unknown note type '%s'. Known types in this collection: %s"
        % (model_name, ", ".join(known) or "(none)")
      )
    return notetype

  def _add_note(self, entry, deck_id):
    notetype = self._resolve_notetype(entry['type'])

    # Map YAML field names to the notetype's declared field indices.
    field_index = {f['name']: i for i, f in enumerate(notetype['flds'])}
    fields = entry['fields']

    unknown = [name for name in fields if name not in field_index]
    if unknown:
      raise UnknownFieldError(
        "Note type '%s' has no field(s) %s. Known fields: %s"
        % (entry['type'], unknown, list(field_index.keys()))
      )

    note = self.col.new_note(notetype)
    for name, value in fields.items():
      note.fields[field_index[name]] = value if value is not None else ""

    # Copy referenced media files into the collection's media store.
    for value in fields.values():
      if not isinstance(value, str):
        continue
      for filename in SOUND_RE.findall(value) + IMG_RE.findall(value):
        media_path = os.path.join(self.media_dir, filename)
        if os.path.exists(media_path):
          print("\t- copying media file '%s'" % filename)
          self.col.media.add_file(media_path)
        else:
          print("🙈 Ignoring media file '%s'. Not found: %s" % (filename, media_path))

    if entry['tags']:
      note.tags = self.col.tags.canonify(entry['tags'])

    self.col.add_note(note, deck_id)

  def load(self, cards, deck_name="Default"):
    print("🔍 Loading notes into the deck '%s'..." % deck_name)

    # Create the deck on demand. col.decks.id returns the existing deck's id
    # if one is already named deck_name, and creates a new deck otherwise.
    deck_id = self.col.decks.id(deck_name)

    for entry in cards:
      self._add_note(entry, deck_id)

    print("💾 Saving Anki collection...")
    self.col.save()
    os.chdir(self.cwd)

  def export(self, archive_file):
    e = AnkiPackageExporter(self.col)
    e.exportInto(archive_file)
