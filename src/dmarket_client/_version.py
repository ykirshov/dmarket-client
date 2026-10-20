"""Distribution metadata is the single runtime version source."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dmarket-client")
except PackageNotFoundError:
    __version__ = "0.1.0.dev0"
