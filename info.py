import docker
from pprint import pprint
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
    return dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def print_title(title: str):
    print("-" * 120)
    print(title)
    print("=" * len(title))


client = docker.from_env()

# get root fs disk size
# determine disk size
du = client.containers.run("alpine", "df", remove=True)
lines = du.decode("utf-8").splitlines()
if len(lines) > 1:
    cols = lines[1].split()
    if len(cols) > 2:
        total = int(cols[3]) * 1024
        used = int(cols[2]) * 1024
        print(f"Docker  disk: {convert_size(used):>12} / {convert_size(total):>6}")

client_info = client.info()
# pprint(client_info)
# info().keys()
# dict_keys(['ID', 'Containers', 'ContainersRunning', 'ContainersPaused', 'ContainersStopped', 'Images', 'Driver', 'DriverStatus', 'Plugins', 'MemoryLimit', 'SwapLimit', 'KernelMemory', 'KernelMemoryTCP', 'CpuCfsPeriod', 'CpuCfsQuota', 'CPUShares', 'CPUSet', 'PidsLimit', 'IPv4Forwa rding', 'BridgeNfIptables', 'BridgeNfIp6tables', 'Debug', 'NFd', 'OomKillDisable', 'NGoroutines', 'SystemTime', 'LoggingDriver', 'CgroupDriv er', 'CgroupVersion', 'NEventsListener', 'KernelVersion', 'OperatingSystem', 'OSVersion', 'OSType', 'Architecture', 'IndexServerAddress', 'R egistryConfig', 'NCPU', 'MemTotal', 'GenericResources', 'DockerRootDir', 'HttpProxy', 'HttpsProxy', 'NoProxy', 'Name', 'Labels', 'Experiment alBuild', 'ServerVersion', 'Runtimes', 'DefaultRuntime', 'Swarm', 'LiveRestoreEnabled', 'Isolation', 'InitBinary', 'ContainerdCommit', 'Runc Commit', 'InitCommit', 'SecurityOptions', 'Warnings'])

df = client.df()
# ['LayersSize', 'Images', 'Containers', 'Volumes', 'BuildCache', 'BuilderSize']

print(f'Layers  size: {convert_size(df["LayersSize"]):>12}')
print(f'Builder size: {convert_size(df["BuilderSize"]):>12}')


print_title(f'Images {len(df["Images"])}')

for k in sorted(df["Images"], key=lambda x: x["Size"], reverse=True):
    print(
        f'{k["RepoTags"][0][0:48]:50} ',
        f' Size: {convert_size(k["Size"]):>12}',
        f' Shared: {convert_size(k["SharedSize"]):>12}',
        f' Virtual: {convert_size(k["VirtualSize"]):>12}',
    )


print_title(f'Containers {len(df["Containers"])}')

for k in sorted(df["Containers"], key=lambda x: x["Created"], reverse=True):
    print(
        f'{k["Names"][0]:25} ',
        f'{k["Command"]:30} ',
        f'{k["Image"]:18} ',
        f'{k["State"]:>10} ',
        f'Size: {convert_size(k["SizeRootFs"]):>12} ',
        f'{format_date(k["Created"]):>15}',
    )

print_title(f'Volumes {len(df["Volumes"])}')

for k in sorted(df["Volumes"], key=lambda x: x["UsageData"]["Size"], reverse=True):
    print(
        f'{k["Name"][0:32]:35} ',
        f'{k["Mountpoint"][0:46]:50} ',
        f'Size: {convert_size(k["UsageData"]["Size"]):>12}',
    )

print_title(f'BuildCache {len(df["BuildCache"])}')
for k in sorted(df["BuildCache"], key=lambda x: x["Size"], reverse=True)[0:15]:
    print(
        f'{k["Type"]:12} ',
        f'{k["Description"][0:48]:50} ',
        f'{convert_size(k["Size"]):>12} ',
        "Shared" if k["Shared"] else " ",
        "In Use" if k["InUse"] else " ",
        f'{k["LastUsedAt"]:>15}',
    )
