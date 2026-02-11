"""
Terminal-based visualization.

Works over SSH, in CI logs, in Docker containers — anywhere with a
terminal and a monospace font.
"""

import sys


def ascii_hist(keys, counts_map, width=50, title="", stream=None):
    """
    Render a horizontal bar chart to the terminal.

    Parameters
    ----------
    keys : list
        Ordered sequence of bucket labels.
    counts_map : dict
        Mapping from key to count.
    width : int
        Maximum bar width in characters.
    title : str
        Optional title printed above the chart.
    stream : file-like, optional
        Output stream (defaults to ``sys.stdout``).
    """
    if stream is None:
        stream = sys.stdout
    vals = [counts_map.get(k, 0) for k in keys]
    m = max(vals) if vals else 1
    stream.write("\n" + title + "\n")
    for k in keys:
        c = counts_map.get(k, 0)
        bar_len = int((c / m) * width) if m > 0 else 0
        bar = "\u2588" * bar_len
        stream.write(f"{str(k):>3} | {bar:<{width}} {c}\n")
