import logging
import os
import platform
import sys
from collections import namedtuple


class Enum:
    @classmethod
    def values(cls):
        return [value for name, value in vars(cls).items() if not name.startswith("_")]


class System(Enum):
    linux = "linux"
    android = "android"
    darwin = "darwin"
    windows = "windows"


class Arch(Enum):
    x64 = "x64"
    x86 = "x86"
    arm = "arm"
    arm64 = "arm64"
    armv7 = "armv7"


Platform = namedtuple("Platform", [
    "system",  # type:str
    "version",  # type:str
    "arch",  # type:str
])

SHARED_LIB_EXTENSION = {System.linux: ".so", System.android: ".so", System.darwin: ".dylib", System.windows: ".dll"}
EXECUTABLE_EXTENSION = {System.linux: "", System.android: "", System.darwin: "", System.windows: ".exe"}


def get_platform():
    system = platform.system().lower()
    version = platform.release()
    arch = Arch.x64 if sys.maxsize > 2 ** 32 else Arch.x86
    machine = platform.machine().lower()
    is_arch64 = "64" in machine and arch == Arch.x64

    logging.debug("Resolving platform - system=%s, version=%s, arch=%s, machine=%s", system, version, arch, machine)

    if "ANDROID_STORAGE" in os.environ:
        system = System.android
        if "arm" in machine or "aarch" in machine:
            arch = Arch.arm64 if is_arch64 else Arch.arm
    elif system == System.linux:
        if "armv7" in machine:
            arch = Arch.armv7
        elif "aarch" in machine:
            arch = Arch.arm64 if is_arch64 else Arch.armv7
        elif "arm" in machine:
            arch = Arch.arm64 if is_arch64 else Arch.arm
    elif system == System.windows:
        if machine.endswith("64"):
            arch = Arch.x64
    elif system == System.darwin:
        arch = Arch.x64

    if system not in System.values() or arch not in Arch.values():
        logging.warning("Unknown system (%s) and/or arch (%s) values", system, arch)

    return Platform(system, version, arch)


def dump_platform():
    return "system: {}\nrelease: {}\nmachine: {}\narchitecture: {}\nmax_size: {}".format(
        platform.system(), platform.release(), platform.machine(), platform.architecture(), sys.maxsize)


try:
    PLATFORM = get_platform()
except Exception as _e:
    logging.fatal(_e, exc_info=True)
    logging.fatal(dump_platform())
    raise _e


def get_platform_arch(sep="_"):
    return PLATFORM.system + sep + PLATFORM.arch


def get_shared_lib_extension():
    return SHARED_LIB_EXTENSION.get(PLATFORM.system, "")


def get_executable_extension():
    return EXECUTABLE_EXTENSION.get(PLATFORM.system, "")
