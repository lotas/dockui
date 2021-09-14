import docker
import curses
import json
from collections.abc import Iterable
from utils import convert_size, format_date, determine_root_fs_usage, progress_bar


def init_docker():
    client = docker.from_env()
    return client


class DisplayStr:
    __slots__ = "row"

    def __init__(self, row):
        self.row = row

    def to_str(self, max_width=80):
        return self.row[0:max_width]

    def __str__(self):
        return self.row


class DisplayKeyVal(DisplayStr):
    __slots__ = "row"

    def __init__(self, key, val):
        super().__init__(f"{key:24}: {val}")


class DisplayKeyValProgress(DisplayStr):
    __slots__ = "row"

    def __init__(self, key, val, progress):
        super().__init__(
            f"{key:24}: {val:30} {progress_bar(50, progress)} {round(progress*100, 1)}%"
        )


class DisplaySeparator(DisplayStr):
    __slots__ = "row"

    def __init__(self):
        super().__init__(" ")


class DisplayTableRow:
    __slots__ = "row"

    def __init__(self, row):
        self.row = row

    def __getitem__(self, index):
        method_name = f"_get_{index.lower()}"
        if hasattr(self, method_name):
            return getattr(self, method_name)()
        if index in self.row:
            return self.row[index]
        return ""

    def _get_display_info(self):
        keys = self.row.keys()
        max_len = max([len(k) for k in keys])
        lines = []
        for k in keys:
            line = f"{k:{max_len}}: {self.__getitem__(k)}"
            i = 0
            for l in line.split("\n"):
                if i > 0:
                    # ident json
                    lines.append(" " * max_len + ": " + l)
                else:
                    lines.append(l)
                i += 1

        return lines


class DisplayTableColumn:
    __slots__ = "name", "width", "align", "callback_fn", "color_attr"

    def __init__(self, name, width=20, align="left", callback_fn=None, color_attr=None):
        self.name = name
        self.width = width
        self.align = align
        self.callback_fn = callback_fn
        self.color_attr = color_attr


class DisplayTableSummaryRow(DisplayTableRow):
    __slots__ = "row", "progress", "pct"

    def __init__(self, type, value, progress=0):
        self.progress = progress
        self.row = {
            "Type": type,
            "Value": value,
            "Progress": self.get_progress(50),
            "Percent": f"{round(progress * 100, 1)}%" if progress > 0 else "",
        }

    def get_progress(self, width):
        if self.progress == 0:
            return ""
        return progress_bar(width, self.progress)


class DisplayTableVolumeRow(DisplayTableRow):
    __slots__ = "row"

    def _get_size(self):
        return convert_size(self.row["UsageData"]["Size"])

    def _get_usagedata(self):
        return json.dumps(self.row["UsageData"], sort_keys=True, indent=2)

    def _get_labels(self):
        return json.dumps(self.row["Labels"], sort_keys=True, indent=2)


class DisplayTableContainerRow(DisplayTableRow):
    __slots__ = "row"

    def id(self):
        return self.row["Id"]

    def _get_sizerootfs(self):
        return convert_size(self.row["SizeRootFs"])

    def _get_created(self):
        return format_date(self.row["Created"])

    def _get_names(self):
        return ",".join([k[1:] for k in self.row["Names"]])

    def _get_networksettings(self):
        return json.dumps(self.row["NetworkSettings"], sort_keys=True, indent=2)


class DisplayTableImagesRow(DisplayTableRow):
    __slots__ = "row"

    def _get_repotags(self):
        if isinstance(self.row["RepoTags"], Iterable):
            return ",".join(self.row["RepoTags"])
        return self.row["RepoTags"]

    def _get_size(self):
        return convert_size(self.row["Size"])

    def _get_sharedsize(self):
        return convert_size(self.row["SharedSize"])

    def _get_virtualsize(self):
        return convert_size(self.row["VirtualSize"])

    def _get_labels(self):
        return json.dumps(self.row["Labels"], sort_keys=True, indent=2)


class DisplayTableBuildCacheRow(DisplayTableRow):
    __slots__ = "row"

    def _get_size(self):
        return convert_size(self.row["Size"])

    def _get_lastusedat(self):
        return format_date(self.row["LastUsedAt"])

    def _get_shared(self):
        return "yes" if self.row["Shared"] else "no"

    def _get_inuse(self):
        return "yes" if self.row["InUse"] else "no"


class DockUI:
    VIEW_MODE_SUMMARY = 0
    VIEW_MODE_IMAGES = 1
    VIEW_MODE_CONTAINERS = 2
    VIEW_MODE_VOLUMES = 3
    VIEW_MODE_BUILD_CACHE = 4
    VIEW_MODE_SYSTEM_INFO = 5

    RENDER_MODE_ROWS = 0
    RENDER_MODE_TABLE = 1

    INFO_MESSAGE_COLOR = 1
    STATUS_BAR_COLOR = 2
    TEXT_PANEL_COLOR = 3
    TEXT_ITEM_DETAILS = 4

    MENU_COLOR_ON = 10
    MENU_COLOR_OFF = 11
    MENU_COLOR_SIZES = 12

    LINE_HIGHLIGHT = 20
    LINE_SELECTED = 21

    PROGRESS_BAR = 30

    def __init__(self, w, docker_client):
        self.w = w
        self.docker_client = docker_client

        self.k = 0
        self.width = 0
        self.height = 0
        self.cursor_x = 0
        self.cursor_y = 0
        self.clicked_row = -1
        self.offset_y = 0

        self.view_mode = self.VIEW_MODE_SUMMARY
        self.render_mode = self.RENDER_MODE_ROWS

        self.rows = []
        self.cols = []

        curses.noecho()
        # Start colors in curses
        curses.start_color()
        curses.init_pair(self.INFO_MESSAGE_COLOR, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(self.STATUS_BAR_COLOR, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(self.TEXT_PANEL_COLOR, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(self.TEXT_ITEM_DETAILS, curses.COLOR_GREEN, curses.COLOR_BLACK)

        curses.init_pair(self.MENU_COLOR_ON, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(self.MENU_COLOR_OFF, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(self.MENU_COLOR_SIZES, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(self.LINE_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(self.LINE_SELECTED, curses.COLOR_BLACK, curses.COLOR_GREEN)

        curses.init_pair(self.PROGRESS_BAR, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        self._fetch_docker_info()
        self._prepare_content()
        self.loop()

    def show_text_panel(self, lines, close_on_keypress=False, color=None):
        height, width = self.w.getmaxyx()
        lines_count = len(lines)
        safe_width = width - 4
        maxwidth = min(safe_width, max([len(k) for k in lines]))

        win = curses.newwin(
            lines_count + 2,
            min(safe_width, maxwidth + 2),
            (height - lines_count) // 2,
            (width - min(safe_width, maxwidth)) // 2,
        )
        win.attrset(curses.color_pair(color if color else self.TEXT_PANEL_COLOR))
        win.box()

        for i in range(lines_count):
            win.addstr(i + 1, 1, lines[i][0:safe_width])

        win.touchwin()
        win.refresh()

        if close_on_keypress:
            win.getch()
            del win
            return None

        return win

    def show_info(self, message: str, close_on_keypress=False):
        return self.show_text_panel(
            [message],
            close_on_keypress=close_on_keypress,
            color=self.INFO_MESSAGE_COLOR,
        )

    def _fetch_docker_info(self):
        win = self.show_info("Fetching docker info...")
        self.docker_info = self.docker_client.info()
        self.docker_df = self.docker_client.df()
        self.docker_root_fs = determine_root_fs_usage(self.docker_client)
        del win

    def _prepare_content(self):
        mode_handlers = {
            self.VIEW_MODE_SUMMARY: self.draw_summary,
            self.VIEW_MODE_IMAGES: self.draw_images,
            self.VIEW_MODE_VOLUMES: self.draw_volumes,
            self.VIEW_MODE_CONTAINERS: self.draw_containers,
            self.VIEW_MODE_BUILD_CACHE: self.draw_build_cache,
            self.VIEW_MODE_SYSTEM_INFO: self.draw_system_info,
        }

        mode_handlers[self.view_mode]()

    def process_input(self):
        old_mode = self.view_mode

        if self.k == curses.KEY_BTAB:
            self.view_mode = max(0, self.view_mode - 1)
        elif self.k == ord("\t"):
            self.view_mode = (self.view_mode + 1) % 6

        if old_mode != self.view_mode:
            self.cursor_y = 0
            self.offset_y = 0
            self._prepare_content()

        try:
            keyname = curses.keyname(self.k).decode("utf-8")
            if keyname == "^R":
                self._fetch_docker_info()
            elif keyname == "^D":
                self._delete_selected_item()
        except ValueError:
            pass

        if self.k in [curses.KEY_DOWN, ord("j")]:
            self.cursor_y = self.cursor_y + 1
        elif self.k in [curses.KEY_UP, ord("k")]:
            self.cursor_y = self.cursor_y - 1
        elif self.k in [curses.KEY_RIGHT, ord("l")]:
            self.cursor_x = self.cursor_x + 1
        elif self.k in [curses.KEY_LEFT, ord("h")]:
            self.cursor_x = self.cursor_x - 1
        elif self.k in [curses.KEY_ENTER, 10, 13]:
            self.clicked_row = self.cursor_y
            self.open_item_info()

        self.cursor_x = min(self.width - 1, max(0, self.cursor_x))
        self.cursor_y = min(len(self.rows) - 1, max(0, self.cursor_y))

        # scrolling window when cursor close to top/bottom
        if self.cursor_y - self.offset_y + 4 > self._client_height():
            self.offset_y = self.offset_y + 1
        elif self.offset_y > 0 and self.cursor_y - self.offset_y < 4:
            self.offset_y = self.offset_y - 1

    def loop(self):
        while self.k != ord("q"):
            self.w.erase()
            self.height, self.width = self.w.getmaxyx()
            self.process_input()
            self.draw()
            self.w.refresh()
            self.k = self.w.getch()

    def draw(self):
        self.w.box()
        self.draw_header()

        if self.render_mode == self.RENDER_MODE_ROWS:
            self.draw_rows()
        elif self.render_mode == self.RENDER_MODE_TABLE:
            self.draw_table()

        self.draw_statusbar()
        # self.w.move(self.cursor_y, self.cursor_x)

    def draw_header(self):
        menu_items = {
            "Summary": self.VIEW_MODE_SUMMARY,
            f"Images {self.docker_info['Images']}": self.VIEW_MODE_IMAGES,
            f"Containers {self.docker_info['Containers']}": self.VIEW_MODE_CONTAINERS,
            f"Volumes {len(self.docker_df['Volumes'])}": self.VIEW_MODE_VOLUMES,
            "BuildCache": self.VIEW_MODE_BUILD_CACHE,
            "System info": self.VIEW_MODE_SYSTEM_INFO,
        }

        offset = 1
        for text, mode in menu_items.items():
            color = self.MENU_COLOR_OFF
            if mode == self.view_mode:
                color = self.MENU_COLOR_ON

            self.w.attron(curses.color_pair(color))
            self.w.addstr(1, offset, text)
            self.w.attroff(curses.color_pair(color))
            offset = offset + len(text) + 4

        infostr = (
            f"Disk: {convert_size(self.docker_root_fs[0])} / {convert_size(self.docker_root_fs[1])} | "
            f'Layers: {convert_size(self.docker_df["LayersSize"])} | '
            f'Builder: {convert_size(self.docker_df["BuilderSize"])}'
        )
        self.w.attron(curses.color_pair(self.MENU_COLOR_SIZES))
        self.w.attron(curses.A_BOLD)
        self.w.addstr(1, self.width - 1 - len(infostr), infostr)
        self.w.attroff(curses.A_BOLD)
        self.w.attroff(curses.color_pair(self.MENU_COLOR_SIZES))
        self.w.addstr(2, 1, "─" * (self.width - 2))

    def _client_height(self):
        return self.height - 5

    def _items_end_offset(self):
        return min(len(self.rows), self.offset_y + self._client_height())

    def draw_rows(self):
        start_y = 3

        for i in range(self.offset_y, self._items_end_offset()):

            if i == self.cursor_y:
                self.w.attron(curses.A_BOLD)
                self.w.attron(curses.color_pair(self.LINE_SELECTED))

            row = self.rows[i]
            if isinstance(row, DisplayStr):
                row = row.to_str(self.width - 2)
            elif isinstance(row, str):
                row = row[0 : self.width - 2]

            self.w.addstr(start_y + i - self.offset_y, 1, row)

            if i == self.cursor_y:
                self.w.attroff(curses.A_BOLD)
                self.w.attroff(curses.color_pair(self.LINE_SELECTED))

    def draw_table(self):
        start_y = 4
        cell_padding = 2

        def render_row(y, row):
            offset = 1
            for col in self.cols:
                cell_width = (
                    int((self.width - 2) * col.width) if col.width < 1 else col.width
                )

                if col.callback_fn and hasattr(row, col.callback_fn):
                    fn = getattr(row, col.callback_fn)
                    txt = fn(cell_width - 1)
                else:
                    txt = str(row[col.name])[0 : cell_width - 1]

                if col.align == "right":
                    txt = txt.rjust(int(cell_width + 1))
                else:
                    txt = txt.ljust(int(cell_width + 1))

                if col.color_attr is not None:
                    self.w.attron(curses.color_pair(col.color_attr))

                self.w.addstr(y, offset, txt)

                if col.color_attr is not None:
                    self.w.attroff(curses.color_pair(col.color_attr))

                offset = offset + cell_width + cell_padding

        # draw header
        self.w.attron(curses.A_BOLD)
        render_row(3, {k.name: k.name for k in self.cols})
        self.w.attroff(curses.A_BOLD)

        for i in range(self.offset_y, self._items_end_offset()):

            if i == self.cursor_y:
                self.w.attron(curses.A_BOLD)
                self.w.attron(curses.color_pair(self.LINE_SELECTED))

            render_row(start_y + i - self.offset_y, self.rows[i])

            if i == self.cursor_y:
                self.w.attroff(curses.A_BOLD)
                self.w.attroff(curses.color_pair(self.LINE_SELECTED))

    def draw_summary(self):
        di = self.docker_info
        df = self.docker_df
        fs = self.docker_root_fs

        rows = []

        if len(fs) > 0:
            rows = rows + [
                DisplayTableSummaryRow("Root fs total", convert_size(fs[1])),
                DisplayTableSummaryRow(
                    "Root fs used", f"{convert_size(fs[0])}", fs[0] / fs[1]
                ),
                DisplayTableSummaryRow(
                    "Root fs available:", f"{convert_size(fs[2])}", fs[2] / fs[1]
                ),
            ]

        if "LayersSize" in df and "BuilderSize" in df:
            rows = rows + [
                DisplayTableSummaryRow(
                    "Layers size",
                    convert_size(df["LayersSize"]),
                    df["LayersSize"] / fs[1],
                ),
                DisplayTableSummaryRow(
                    "Builder size",
                    convert_size(df["BuilderSize"]),
                    df["BuilderSize"] / fs[1],
                ),
            ]

        if "Images" in df:
            images_size = sum([k["Size"] for k in df["Images"]])
            images_shared_size = sum([k["SharedSize"] for k in df["Images"]])

            rows += [
                DisplayTableSummaryRow("Images count", len(df["Images"])),
                DisplayTableSummaryRow(
                    "Total images size", convert_size(images_size), images_size / fs[1]
                ),
                DisplayTableSummaryRow(
                    "Total images shared size", convert_size(images_shared_size)
                ),
            ]

        if "Volumes" in df:
            volumes_size = sum([k["UsageData"]["Size"] for k in df["Volumes"]])
            rows += [
                DisplayTableSummaryRow("Volumes count", len(df["Volumes"])),
                DisplayTableSummaryRow(
                    "Total volumes size",
                    convert_size(volumes_size),
                    volumes_size / fs[1],
                ),
            ]

        if "Containers" in df:
            containers_size = sum([k["SizeRootFs"] for k in df["Containers"]])
            rows += [
                DisplayTableSummaryRow("Containers count", len(df["Containers"])),
                DisplayTableSummaryRow(
                    "Total containers size",
                    convert_size(containers_size),
                    containers_size / fs[1],
                ),
            ]

        if "BuildCache" in df:
            buildcache_size = sum([k["Size"] for k in df["BuildCache"]])
            rows += [
                DisplayTableSummaryRow("Build caches count", len(df["BuildCache"])),
                DisplayTableSummaryRow(
                    "Total build caches size",
                    convert_size(buildcache_size),
                    buildcache_size / fs[1],
                ),
            ]

        self.rows = rows
        self.cols = [
            DisplayTableColumn("Type", 25),
            DisplayTableColumn("Value", 14, "left"),
            DisplayTableColumn("Percent", 10, "right"),
            DisplayTableColumn(
                "Progress", 0.5, "right", "get_progress", self.PROGRESS_BAR
            ),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_system_info(self):
        di = self.docker_info

        main_keys = [
            "ServerVersion",
            "Name",
            "OperatingSystem",
            "OSType",
            "KernelVersion",
            "Containers",
            "Images",
        ]

        self.rows = [DisplayKeyVal(k, di[k]) for k in main_keys] + [
            DisplayKeyVal(k, di[k]) for k in di.keys()
        ]
        self.render_mode = self.RENDER_MODE_ROWS

    def draw_images(self):
        if "Images" in self.docker_df:
            self.rows = [
                DisplayTableImagesRow(k)
                for k in sorted(
                    self.docker_df["Images"], key=lambda x: x["Size"], reverse=True
                )
            ]
        else:
            self.rows = []

        self.cols = [
            DisplayTableColumn("RepoTags", 0.5),
            DisplayTableColumn("Size", 12, "right"),
            DisplayTableColumn("SharedSize", 12, "right"),
            DisplayTableColumn("VirtualSize", 12, "right"),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_volumes(self):
        if "Volumes" in self.docker_df:
            self.rows = [
                DisplayTableVolumeRow(k)
                for k in sorted(
                    self.docker_df["Volumes"],
                    key=lambda x: x["UsageData"]["Size"],
                    reverse=True,
                )
            ]
        else:
            self.rows = []

        self.cols = [
            DisplayTableColumn("Name", 0.3),
            DisplayTableColumn("Mountpoint", 0.5),
            DisplayTableColumn("Size", 12, "right"),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_containers(self):
        if "Containers" in self.docker_df:
            self.rows = [
                DisplayTableContainerRow(k)
                for k in sorted(
                    self.docker_df["Containers"],
                    key=lambda x: x["Created"],
                    reverse=True,
                )
            ]
        else:
            self.rows = []

        self.cols = [
            DisplayTableColumn("Names", 35),
            DisplayTableColumn("Command", 0.25),
            DisplayTableColumn("Image", 0.15),
            DisplayTableColumn("State", 15),
            DisplayTableColumn("SizeRootFs", 12, "right"),
            DisplayTableColumn("Created", 18, "right"),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_build_cache(self):
        if "BuildCache" in self.docker_df:
            self.rows = [
                DisplayTableBuildCacheRow(k)
                for k in sorted(
                    self.docker_df["BuildCache"], key=lambda x: x["Size"], reverse=True
                )
            ]
        else:
            self.rows = []

        self.cols = [
            DisplayTableColumn("Type", 20),
            DisplayTableColumn("Description", 0.40),
            DisplayTableColumn("Size", 12, "right"),
            DisplayTableColumn("Shared", 10, "right"),
            DisplayTableColumn("InUse", 10, "right"),
            DisplayTableColumn("LastUsedAt", 18, "right"),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_statusbar(self):
        items = [
            "Press 'q' to exit",
            "TAB to switch views",
            "'CTRL+R' to refresh values",
        ]

        if self.view_mode in [self.VIEW_MODE_CONTAINERS]:
            items.append("'CTRL+D' to delete selected item")

        statusbarstr = " | ".join(items)
        statusbarstr = statusbarstr + f"{self.cursor_y + 1}/{len(self.rows)}".rjust(
            self.width - 2 - len(statusbarstr)
        )

        # Render status bar
        self.w.attron(curses.color_pair(self.STATUS_BAR_COLOR))
        self.w.addstr(self.height - 2, 1, statusbarstr)
        self.w.addstr(
            self.height - 2,
            len(statusbarstr),
            " " * (self.width - len(statusbarstr) - 2),
        )
        self.w.attroff(curses.color_pair(self.STATUS_BAR_COLOR))

    """
    actions
    """

    def open_item_info(self):
        item = self.rows[self.cursor_y]
        if isinstance(item, str):
            content = [item]
        elif isinstance(item, DisplayTableRow):
            content = item._get_display_info()
        else:
            content = [str(item)]
        self.show_text_panel(
            content, color=self.TEXT_ITEM_DETAILS, close_on_keypress=True
        )

    def _delete_selected_item(self):
        item = self.rows[self.cursor_y]

        if isinstance(item, DisplayTableContainerRow):
            id = item.id()
            w = self.show_info(f"Deleting container {id}", close_on_keypress=True)
            container = self.docker_client.containers.get(id)
            container.remove(v=True)  # with volumes
            del w

        self._fetch_docker_info()


def main():
    try:
        client = init_docker()
        curses.wrapper(lambda w: DockUI(w, client))
    except docker.errors.DockerException as err:
        print("Cannot connect to docker")
        print(err)
        print("Is docker running?")


if __name__ == "__main__":
    main()
