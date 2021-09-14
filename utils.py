import math
import datetime as dt
from dateutil import parser


def convert_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return "%s %s" % (s, size_name[i])


def format_date(timestamp) -> str:
    fmt = "%Y-%m-%d %H:%M"
    if isinstance(timestamp, str):
        return parser.parse(timestamp).strftime(fmt)
    return dt.datetime.fromtimestamp(timestamp).strftime(fmt)


def determine_root_fs_usage(client):
    du = client.containers.run("alpine", "df", remove=True)
    lines = du.decode("utf-8").splitlines()
    if len(lines) > 1:
        cols = lines[1].split()
        if len(cols) > 2:
            total = int(cols[1]) * 1024
            used = int(cols[2]) * 1024
            available = int(cols[3]) * 1024
            return (used, total, available)
    return (0, 0, 0)


def progress_bar(width: int, progress: float) -> str:
    """
    Borrowed from https://mike42.me/blog/tag/python
    """
    progress = min(1, max(0, progress))
    whole_width = math.floor(progress * width)
    remainder_width = (progress * width) % 1
    part_width = math.floor(remainder_width * 8)
    part_char = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"][part_width]
    if (width - whole_width - 1) < 0:
        part_char = ""
    line = "[" + "█" * whole_width + part_char + " " * (width - whole_width - 1) + "]"
    return line
