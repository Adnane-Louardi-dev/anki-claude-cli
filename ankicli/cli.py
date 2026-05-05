import argparse
import logging
import os
import platform
import sys
import tempfile
from pathlib import Path

from .loader import (
  CardSchemaError,
  Loader,
  UnknownFieldError,
  UnknownNoteTypeError,
  parse_cards,
)

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_ANKI_ERROR = 3
EXIT_USER_ABORT = 4

log = logging.getLogger("anki-cli-unofficial")


def _setup_logging(verbose: bool, quiet: bool) -> None:
  level = logging.INFO
  if verbose:
    level = logging.DEBUG
  if quiet:
    level = logging.WARNING
  # Keep the existing emoji-prefixed UX as the format so existing users
  # don't see a regression — each log.info() call already includes its emoji.
  logging.basicConfig(level=level, format="%(message)s")


def get_anki_dir_default() -> str:
  plt = platform.system()
  home = str(Path.home())
  if plt == "Windows":
    return os.path.join(os.getenv("APPDATA"), "Anki2")
  if plt == "Linux":
    return os.path.join(home, ".local/share/Anki2")
  if plt == "Darwin":
    return os.path.join(home, "Library/Application Support/Anki2")
  raise RuntimeError("❌ Failed to detect your OS. Only Windows/Linux/MacOS are supported.")


def get_anki_command() -> str:
  plt = platform.system()
  if plt == "Windows":
    return r'"C:\Program Files\Anki\anki.exe"'
  if plt == "Linux":
    return "anki"
  if plt == "Darwin":
    return "open /Applications/Anki.app --args"
  raise RuntimeError("❌ Failed to detect your OS. Only Windows/Linux/MacOS are supported.")


def _confirm(prompt: str, *, assume_yes: bool) -> bool:
  if assume_yes:
    return True
  if not sys.stdin.isatty():
    log.error("❌ %s (refusing to prompt; pass --yes to auto-confirm)", prompt)
    return False
  return input(prompt + " (yes/no): ").strip().lower() == "yes"


def _build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog="anki-cli-unofficial")
  parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output (DEBUG level)")
  parser.add_argument("--quiet", "-q", action="store_true", help="Quiet output (warnings and errors only)")

  subparsers = parser.add_subparsers(dest="command", title="subcommands")

  load = subparsers.add_parser("load", help="Load flashcards from a YAML file into Anki")
  load.add_argument("--anki-dir", default=None, help="Anki user directory (default: a fresh temp directory)")
  load.add_argument("--media-dir", default=".", help="Local directory containing medias referenced in input_file")
  load.add_argument(
    "--deck",
    default=None,
    help="Deck name to load cards into. Created if it doesn't exist. Defaults to the input file's stem.",
  )
  load.add_argument("--yes", "-y", action="store_true", help="Assume yes to all confirmation prompts")
  load.add_argument("--force", action="store_true", help="Overwrite the output archive if it already exists")
  load.add_argument(
    "--allow-default-anki-dir",
    action="store_true",
    help="Permit writing to the user's default Anki directory (dangerous)",
  )
  load.add_argument("input_file", help="YAML file containing the flashcards to create")
  load.add_argument("output_file", help="Anki generated archive filepath (.apkg)")

  return parser


def _run_load(args) -> int:
  # Validate input file.
  if not os.path.isfile(args.input_file):
    log.error("❌ Input file %s doesn't exist.", args.input_file)
    return EXIT_BAD_INPUT

  try:
    cards = parse_cards(args.input_file)
  except CardSchemaError as exc:
    log.error("❌ Invalid input YAML: %s", exc)
    return EXIT_BAD_INPUT

  # Validate media dir.
  media_dir = os.path.normpath(os.path.expanduser(args.media_dir))
  if not os.path.isdir(media_dir):
    log.error("❌ Media directory %s doesn't exist.", args.media_dir)
    return EXIT_BAD_INPUT

  # Resolve Anki home: temp sandbox by default, or user-supplied directory.
  anki_dir_new = args.anki_dir is None
  if anki_dir_new:
    anki_dir_root = tempfile.mkdtemp()
    anki_dir = os.path.join(anki_dir_root, "User 1")
    os.mkdir(anki_dir, 0o755)
  else:
    anki_dir = os.path.normpath(os.path.expanduser(args.anki_dir))
    if not os.path.isdir(anki_dir):
      log.error("❌ Anki directory %s doesn't exist.", anki_dir)
      return EXIT_BAD_INPUT
    if not os.path.isfile(os.path.join(anki_dir, "collection.anki2")):
      log.error("❌ Anki collection file not found in %s", anki_dir)
      return EXIT_BAD_INPUT

    default_dir = os.path.realpath(get_anki_dir_default())
    if anki_dir.startswith(default_dir) and not args.allow_default_anki_dir:
      log.error(
        "🔥 Refusing to write to your real Anki directory at %s. "
        "Pass --allow-default-anki-dir to override (back up first!).",
        anki_dir,
      )
      return EXIT_USER_ABORT

  # Default the deck name to the input file's stem if not given.
  deck_name = args.deck or Path(args.input_file).stem

  # Load.
  try:
    loader = Loader(anki_dir, media_dir)
    loader.load(cards, deck_name)
  except (UnknownNoteTypeError, UnknownFieldError) as exc:
    log.error("❌ %s", exc)
    return EXIT_BAD_INPUT
  except Exception as exc:  # noqa: BLE001 — anki raises plain Exception subclasses
    log.error("❌ Anki error while loading cards: %s", exc)
    return EXIT_ANKI_ERROR

  log.info("👍 Done")
  log.info(
    "👉 Anki collection can be opened using the following command:\n\t%s -b %s",
    get_anki_command(),
    Path(anki_dir).parent,
  )

  if not anki_dir_new:
    if not _confirm(
      "🔥 You are working on an existing collection. Exporting it could take a long time. Continue?",
      assume_yes=args.yes,
    ):
      log.info("🙊 Skipped the archive file generation")
      return EXIT_OK

  archive_file = os.path.join(os.getcwd(), args.output_file)
  if os.path.isfile(archive_file) and not args.force:
    if not _confirm("🧨 Archive file %s already exists. Overwrite?" % archive_file, assume_yes=args.yes):
      log.info("🙊 Skipped the archive file generation")
      return EXIT_USER_ABORT

  try:
    loader.export(archive_file)
  except Exception as exc:  # noqa: BLE001
    log.error("❌ Anki error while exporting archive: %s", exc)
    return EXIT_ANKI_ERROR

  log.info("👉 Anki Archive is available here: %s", archive_file)
  return EXIT_OK


def main(argv=None) -> int:
  parser = _build_parser()
  args = parser.parse_args(argv)
  _setup_logging(verbose=args.verbose, quiet=args.quiet)

  if args.command == "load":
    return _run_load(args)
  parser.print_help()
  return EXIT_BAD_INPUT


if __name__ == "__main__":
  sys.exit(main())
