"""Reading source files. Nothing here cleans or resolves anything --
each reader turns one file format into plain records, and that is all."""
from .detect import detect_format, detect_entity
from .readers import read_file, ReadResult

__all__ = ["detect_format", "detect_entity", "read_file", "ReadResult"]
