import math
import datetime as dt


def convert_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return "%s %s" % (s, size_name[i])


def format_date(timestamp: int) -> str:
    return dt.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')


def determine_root_fs_usage(client):
    du = client.containers.run("alpine", "df", remove=True)
    lines = du.decode('utf-8').splitlines()
    if len(lines) > 1:
        cols = lines[1].split()
        if len(cols) > 2:
            total = int(cols[3]) * 1024
            used = int(cols[2]) * 1024
            return (used, total)
    return (0, 0)
