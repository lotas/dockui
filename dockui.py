import docker
import curses
from utils import convert_size, format_date, determine_root_fs_usage


def init_docker():
    client = docker.from_env()
    return client


class DisplayStr:
    def __init__(self, row):
        self.row = row

    def to_str(self, max_width=80):
        return self.row[0:max_width]

    def __str__(self):
        return self.row


class DisplayKeyVal(DisplayStr):
    def __init__(self, key, val):
        super().__init__(f"{key:24}: {val}")


class DisplayTableRow:
    def __init__(self, row):
        self.row = row

    def __getitem__(self, index):
        method_name = f'_get_{index.lower()}'
        if hasattr(self, method_name):
            return getattr(self, method_name)()
        if index in self.row:
            return self.row[index]
        return ""


class DisplayTableColumn:
    def __init__(self, name, width=20, align='left'):
        self.name = name
        self.width = width
        self.align = align


class DisplayTableVolumeRow(DisplayTableRow):
    def _get_size(self):
        return convert_size(self.row['UsageData']['Size'])


class DisplayTableContainerRow(DisplayTableRow):
    def _get_size(self):
        return convert_size(self.row['SizeRootFs'])

    def _get_created(self):
        return format_date(self.row['Created'])

    def _get_names(self):
        return ",".join(self.row['Names'])


class DisplayTableImagesRow(DisplayTableRow):
    def _get_tags(self):
        return ",".join(self.row['RepoTags'])

    def _get_size(self):
        return convert_size(self.row['Size'])

    def _get_shared(self):
        return convert_size(self.row['SharedSize'])

    def _get_virtual(self):
        return convert_size(self.row['VirtualSize'])


class DockUI:
    VIEW_MODE_SYSTEM_INFO = 0
    VIEW_MODE_IMAGES = 1
    VIEW_MODE_CONTAINERS = 2
    VIEW_MODE_VOLUMES = 3
    VIEW_MODE_BUILD_CACHE = 4

    RENDER_MODE_ROWS = 0
    RENDER_MODE_TABLE = 1

    MENU_COLOR_ON = 10
    MENU_COLOR_OFF = 11
    MENU_COLOR_SIZES = 12

    LINE_HIGHLIGHT = 20
    LINE_SELECTED = 21

    def __init__(self, w, docker_client):
        self.w = w
        self.docker_client = docker_client
        self._fetch_docker_info()

        self.k = 0
        self.width = 0
        self.height = 0
        self.cursor_x = 0
        self.cursor_y = 0
        self.clicked_row = -1
        self.offset_y = 0

        self.view_mode = self.VIEW_MODE_SYSTEM_INFO
        self.render_mode = self.RENDER_MODE_ROWS

        self.rows = []
        self.cols = []

        # Clear and refresh the screen for a blank canvas
        w.clear()

        # Start colors in curses
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

        curses.init_pair(self.MENU_COLOR_ON,
                         curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(self.MENU_COLOR_OFF,
                         curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(self.MENU_COLOR_SIZES,
                         curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(self.LINE_HIGHLIGHT,
                         curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(self.LINE_SELECTED,
                         curses.COLOR_BLACK, curses.COLOR_RED)

        self.loop()

    def _fetch_docker_info(self):
        self.docker_info = self.docker_client.info()
        self.docker_df = self.docker_client.df()
        self.docker_root_fs = determine_root_fs_usage(self.docker_client)

    def process_input(self):
        old_mode = self.view_mode

        if self.k == curses.KEY_BTAB:
            self.view_mode = max(0, self.view_mode - 1)
        elif self.k == ord('\t'):
            self.view_mode = (self.view_mode + 1) % 5

        if old_mode != self.view_mode:
            self.cursor_y = 0
            self.offset_y = 0

        if self.k == ord('r'):
            self._fetch_docker_info()

        if self.k == curses.KEY_DOWN or self.k == ord('j'):
            self.cursor_y = self.cursor_y + 1
        elif self.k == curses.KEY_UP or self.k == ord('k'):
            self.cursor_y = self.cursor_y - 1
        elif self.k == curses.KEY_RIGHT or self.k == ord('l'):
            self.cursor_x = self.cursor_x + 1
        elif self.k == curses.KEY_LEFT or self.k == ord('h'):
            self.cursor_x = self.cursor_x - 1
        elif self.k == curses.KEY_ENTER:
            self.clicked_row = self.cursor_y

        self.cursor_x = min(self.width - 1, max(0, self.cursor_x))
        self.cursor_y = min(len(self.rows) - 1, max(0, self.cursor_y))

        # scrolling window when cursor close to top/bottom
        if self.cursor_y - self.offset_y + 4 > self._client_height():
            self.offset_y = self.offset_y + 1
        elif self.offset_y > 0 and self.cursor_y - self.offset_y < 4:
            self.offset_y = self.offset_y - 1

    def loop(self):
        while (self.k != ord('q')):
            self.w.clear()
            self.height, self.width = self.w.getmaxyx()

            self.process_input()
            self.draw()
            self.w.refresh()
            self.k = self.w.getch()

    def draw(self):
        self.w.box()
        self.draw_header()

        mode_handlers = {
            self.VIEW_MODE_SYSTEM_INFO: self.draw_system_info,
            self.VIEW_MODE_IMAGES: self.draw_images,
            self.VIEW_MODE_VOLUMES: self.draw_volumes,
            self.VIEW_MODE_CONTAINERS: self.draw_containers,
            self.VIEW_MODE_BUILD_CACHE: self.draw_build_cache,
        }

        mode_handlers[self.view_mode]()
        if self.render_mode == self.RENDER_MODE_ROWS:
            self.draw_rows()
        elif self.render_mode == self.RENDER_MODE_TABLE:
            self.draw_table()

        self.draw_statusbar()
        # self.w.move(self.cursor_y, self.cursor_x)

    def draw_header(self):
        menu_items = {
            "System info": self.VIEW_MODE_SYSTEM_INFO,
            f"Images {self.docker_info['Images']}": self.VIEW_MODE_IMAGES,
            f"Containers {self.docker_info['Containers']}": self.VIEW_MODE_CONTAINERS,
            f"Volumes {len(self.docker_df['Volumes'])}": self.VIEW_MODE_VOLUMES,
            "BuildCache": self.VIEW_MODE_BUILD_CACHE,
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

        infostr = (f'Disk: {convert_size(self.docker_root_fs[0])} / {convert_size(self.docker_root_fs[1])} | '
                   f'Layers: {convert_size(self.docker_df["LayersSize"])} | '
                   f'Builder: {convert_size(self.docker_df["BuilderSize"])}')
        self.w.attron(curses.color_pair(self.MENU_COLOR_SIZES))
        self.w.attron(curses.A_BOLD)
        self.w.addstr(1, self.width - 1 - len(infostr), infostr)
        self.w.attroff(curses.A_BOLD)
        self.w.attroff(curses.color_pair(self.MENU_COLOR_SIZES))
        self.w.addstr(2, 1, "─" * (self.width - 2))

    def _client_height(self):
        return self.height - 4

    def _items_end_offset(self):
        return min(len(self.rows), self.offset_y + self._client_height())

    def draw_rows(self):
        start_y = 3

        for i in range(self.offset_y, self._items_end_offset()):

            if i == self.cursor_y:
                self.w.attron(curses.A_BOLD)
                self.w.attron(curses.color_pair(self.MENU_COLOR_SIZES))

            row = self.rows[i]
            if isinstance(row, DisplayStr):
                row = row.to_str(self.width - 2)
            elif isinstance(row, str):
                row = row[0:self.width - 2]

            self.w.addstr(start_y + i - self.offset_y, 1, row)

            if i == self.cursor_y:
                self.w.attroff(curses.A_BOLD)
                self.w.attroff(curses.color_pair(self.MENU_COLOR_SIZES))

    def draw_table(self):
        start_y = 4

        def render_row(y, items):
            offset = 1
            for col in self.cols:
                cell_width = int((self.width - 2) *
                                 col.width) if col.width < 1 else col.width
                txt = str(items[col.name])[0:cell_width-1]
                if col.align == 'right':
                    txt = txt.rjust(int(cell_width + 1))
                else:
                    txt = txt.ljust(int(cell_width + 1))

                self.w.addstr(y, offset, txt)
                offset = offset + cell_width + 1

        # draw header
        self.w.attron(curses.A_BOLD)
        render_row(3, {k.name: k.name for k in self.cols})
        self.w.attroff(curses.A_BOLD)

        for i in range(self.offset_y, self._items_end_offset()):

            if i == self.cursor_y:
                self.w.attron(curses.A_BOLD)
                self.w.attron(curses.color_pair(self.MENU_COLOR_SIZES))

            render_row(start_y + i, self.rows[i])

            if i == self.cursor_y:
                self.w.attroff(curses.A_BOLD)
                self.w.attroff(curses.color_pair(self.MENU_COLOR_SIZES))

    def draw_system_info(self):
        di = self.docker_info

        main_keys = ['ServerVersion', 'Name', 'OperatingSystem',
                     'OSType', 'KernelVersion', 'Containers', 'Images']

        self.rows = [DisplayKeyVal(
            k, di[k]) for k in main_keys] + [DisplayKeyVal(k, di[k]) for k in di.keys()]
        self.render_mode = self.RENDER_MODE_ROWS

    def draw_images(self):
        self.rows = [DisplayTableImagesRow(k) for k in sorted(
            self.docker_df['Images'], key=lambda x: x['Size'], reverse=True)]
        self.cols = [
            DisplayTableColumn('Tags', 0.5),
            DisplayTableColumn('Size', 12, 'right'),
            DisplayTableColumn('Shared', 12, 'right'),
            DisplayTableColumn('Virtual', 12, 'right')
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_volumes(self):
        self.rows = [DisplayTableVolumeRow(k) for k in sorted(
            self.docker_df['Volumes'], key=lambda x: x['UsageData']['Size'], reverse=True)]
        self.cols = [
            DisplayTableColumn('Name', 0.3),
            DisplayTableColumn('Mountpoint', 0.5),
            DisplayTableColumn('Size', 12, 'right'),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_containers(self):
        self.rows = [DisplayTableContainerRow(k) for k in sorted(
            self.docker_df['Containers'], key=lambda x: x['Created'], reverse=True)]
        self.cols = [
            DisplayTableColumn('Names', 0.25),
            DisplayTableColumn('Command', 0.25),
            DisplayTableColumn('Image', 0.15),
            DisplayTableColumn('State', 15),
            DisplayTableColumn('Size', 12, 'right'),
            DisplayTableColumn('Created', 18, 'right'),
        ]
        self.render_mode = self.RENDER_MODE_TABLE

    def draw_build_cache(self):
        self.rows = [(
            f'{k["Type"]:12} '
            f'{k["Description"][0:55]:60} '
            f'{convert_size(k["Size"]):>12} '
            'Shared' if k["Shared"] else 'NotShared'
            'In Use' if k["InUse"] else 'NotInUse'
            f'{k["LastUsedAt"]:>15}'
        ) for k in sorted(self.docker_df['BuildCache'], key=lambda x: x['Size'], reverse=True)[0:15]]
        self.render_mode = self.RENDER_MODE_ROWS

    def draw_statusbar(self):
        statusbarstr = "Press 'q' to exit | TAB to switch views | 'r' to refresh values | 'd' to delete active item"
        statusbarstr = statusbarstr + \
            f"({self.offset_y}) {self.cursor_y + 1}/{len(self.rows)}".rjust(
                self.width - 2 - len(statusbarstr))

        # Render status bar
        self.w.attron(curses.color_pair(3))
        self.w.addstr(self.height - 2, 1, statusbarstr)
        self.w.addstr(self.height - 2, len(statusbarstr),
                      " " * (self.width - len(statusbarstr) - 2))
        self.w.attroff(curses.color_pair(3))


def main():
    try:
        client = init_docker()
        curses.wrapper(lambda w: DockUI(w, client))
    except docker.errors.DockerException as err:
        print('Cannot connect to docker')
        print(err)
        print('Is docker running?')


if __name__ == "__main__":
    main()
