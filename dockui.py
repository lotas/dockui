import docker
import curses
from utils import convert_size, format_date, determine_root_fs_usage


def init_docker():
    client = docker.from_env()
    return client


class DockUI:
    VIEW_MODE_SYSTEM_INFO = 0
    VIEW_MODE_IMAGES = 1
    VIEW_MODE_CONTAINERS = 2
    VIEW_MODE_VOLUMES = 3
    VIEW_MODE_BUILD_CACHE = 4

    MENU_COLOR_ON = 10
    MENU_COLOR_OFF = 11
    MENU_COLOR_SIZES = 12

    LINE_HIGHLIGHT = 20

    def __init__(self, w, docker_info, docker_df, docker_root_fs):
        self.w = w
        self.docker_info = docker_info
        self.docker_df = docker_df
        self.docker_root_fs = docker_root_fs

        self.k = 0
        self.width = 0
        self.height = 0
        self.cursor_x = 0
        self.cursor_y = 0

        self.view_mode = self.VIEW_MODE_SYSTEM_INFO

        self.lines = []

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

        self.loop()


    def process_input(self):
        mode_map = {
            ord('s'): self.VIEW_MODE_SYSTEM_INFO,
            ord('i'): self.VIEW_MODE_IMAGES,
            ord('c'): self.VIEW_MODE_CONTAINERS,
            ord('v'): self.VIEW_MODE_VOLUMES,
            ord('b'): self.VIEW_MODE_BUILD_CACHE,
        }

        old_mode = self.view_mode

        if self.k in mode_map:
            self.view_mode = mode_map[self.k]
        elif self.k == curses.KEY_BTAB:
            self.view_mode = max(0, self.view_mode - 1)
        elif self.k == ord('\t'):
            self.view_mode = (self.view_mode + 1) % 5
        
        if old_mode != self.view_mode:
            self.cursor_y = 0

        if self.k == curses.KEY_DOWN or self.k == ord('j'):
            self.cursor_y = self.cursor_y + 1
        elif self.k == curses.KEY_UP or self.k == ord('k'):
            self.cursor_y = self.cursor_y - 1
        elif self.k == curses.KEY_RIGHT or self.k == ord('l'):
            self.cursor_x = self.cursor_x + 1
        elif self.k == curses.KEY_LEFT or self.k == ord('h'):
            self.cursor_x = self.cursor_x - 1

        self.cursor_x = min(self.width - 1, max(0, self.cursor_x))
        self.cursor_y = min(len(self.lines) - 1, max(0, self.cursor_y))


    def loop(self):
        while (self.k != ord('q')):
            self.w.clear()
            self.height, self.width = self.w.getmaxyx()

            self.process_input()

            self.draw()

            # Refresh the screen
            self.w.refresh()

            # Wait for next input
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
        self.draw_lines()

        self.draw_statusbar()
        # self.w.move(self.cursor_y, self.cursor_x)

    def draw_header(self):
        menu_items = {
            "[S]ystem info": self.VIEW_MODE_SYSTEM_INFO,
            f"[I]mages {self.docker_info['Images']}": self.VIEW_MODE_IMAGES,
            f"[C]ontainers {self.docker_info['Containers']}": self.VIEW_MODE_CONTAINERS,
            f"[V]olumes {len(self.docker_df['Volumes'])}": self.VIEW_MODE_VOLUMES,
            "[B]uildCache": self.VIEW_MODE_BUILD_CACHE,
        }

        offset = 1
        for text, mode in menu_items.items():
            color = self.MENU_COLOR_OFF
            if mode == self.view_mode:
                color = self.MENU_COLOR_ON

            self.w.attron(curses.color_pair(color))
            self.w.addstr(1, offset, text)
            self.w.attroff(curses.color_pair(color))
            offset = offset + len(text) + 2

        infostr = (f'Disk: {convert_size(self.docker_root_fs[0])} / {convert_size(self.docker_root_fs[1])} | '
                   f'Layers: {convert_size(self.docker_df["LayersSize"])} | '
                   f'Builder: {convert_size(self.docker_df["BuilderSize"])}')
        self.w.attron(curses.color_pair(self.MENU_COLOR_SIZES))
        self.w.attron(curses.A_BOLD)
        self.w.addstr(1, self.width - 1 - len(infostr), infostr)
        self.w.attroff(curses.A_BOLD)
        self.w.attroff(curses.color_pair(self.MENU_COLOR_SIZES))
        self.w.addstr(2, 1, "─" * (self.width - 2))

    def draw_lines(self):
        start_y = 3

        client_height = self.height - 4
        start_offset = 0
        if self.cursor_y + 4 > client_height:
            start_offset = max(0, client_height - self.cursor_y)

        end_offset = min(len(self.lines), client_height)

        # self.w.addstr(1, 1, f"s: {start_offset} end: {end_offset} cur: {self.cursor_y} height: {client_height}")

        for i in range(end_offset):

            if i == self.cursor_y:
                self.w.attron(curses.A_BOLD)
                self.w.attron(curses.color_pair(self.MENU_COLOR_SIZES))

            self.w.addstr(start_y + i, 1, self.lines[i + start_offset][0: self.width - 2])

            if i == self.cursor_y:
                self.w.attroff(curses.A_BOLD)
                self.w.attroff(curses.color_pair(self.MENU_COLOR_SIZES))

    def draw_system_info(self):

        di = self.docker_info

        self.lines = [
            f'Version: {di["ServerVersion"]}',
            f'Name: {di["Name"]}',
            f'OS: {di["OperatingSystem"]}',
            f'OS type: {di["OSType"]}',
            f'Kernel: {di["KernelVersion"]}',
            f'Containers: {di["Containers"]}',
            f'Images: {di["Images"]}',
            '-' * (self.width - 2)
        ]
        self.lines = self.lines + [f'{k}: {di[k]}' for k in di.keys()]

    def draw_images(self):
        self.lines = [(
            f'{k["RepoTags"][0][0:48]:50} '
            f' Size: {convert_size(k["Size"]):>12}'
            f' Shared: {convert_size(k["SharedSize"]):>12}'
            f' Virtual: {convert_size(k["VirtualSize"]):>12}'
        ) for k in sorted(self.docker_df['Images'], key=lambda x: x['Size'], reverse=True)]

    def draw_volumes(self):
        self.lines = [(
            f'{k["Name"][0:32]:35} '
            f'{k["Mountpoint"][0:46]:50} '
            f'Size: {convert_size(k["UsageData"]["Size"]):>12}'
        ) for k in sorted(self.docker_df['Volumes'], key=lambda x: x['UsageData']['Size'], reverse=True)]

    def draw_containers(self):
        self.lines = [(
            f'{k["Names"][0]:25} '
            f'{k["Command"]:30} '
            f'{k["Image"]:18} '
            f'{k["State"]:>10} '
            f'Size: {convert_size(k["SizeRootFs"]):>12} '
            f'{format_date(k["Created"]):>15}'
        ) for k in sorted(self.docker_df['Containers'], key=lambda x: x['Created'], reverse=True)]

    def draw_build_cache(self):
        self.lines = [(
            f'{k["Type"]:12} '
            f'{k["Description"][0:55]:60} '
            f'{convert_size(k["Size"]):>12} '
            'Shared' if k["Shared"] else 'NotShared'
            'In Use' if k["InUse"] else 'NotInUse'
            f'{k["LastUsedAt"]:>15}'
        ) for k in sorted(self.docker_df['BuildCache'], key=lambda x: x['Size'], reverse=True)[0:15]]

    def draw_statusbar(self):
        statusbarstr = "Press 'q' to exit | TAB to switch views"

        # Render status bar
        self.w.attron(curses.color_pair(3))
        self.w.addstr(self.height - 2, 1, statusbarstr)
        self.w.addstr(self.height - 2, len(statusbarstr),
                      " " * (self.width - len(statusbarstr) - 2))
        self.w.attroff(curses.color_pair(3))


def main():
    try:
        client = init_docker()
        docker_info = client.info()
        docker_df = client.df()
        docker_root_fs = determine_root_fs_usage(client)
        curses.wrapper(lambda w: DockUI(
            w, docker_info, docker_df, docker_root_fs))
    except docker.errors.DockerException as err:
        print('Cannot connect to docker')
        print(err)
        print('Is docker running?')


if __name__ == "__main__":
    main()
