"""video-inbox v2: WSL-native acquisition core.

Single-command pipeline: resolve -> probe -> subtitles/audio -> ASR -> manifest -> report.
The LLM agent stays responsible for summarization and the final Obsidian note;
this package produces verified evidence and a machine-readable report fast.
"""
__version__ = "2.0.0-alpha1"
