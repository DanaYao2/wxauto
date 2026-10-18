#!/usr/bin/python3
# -*- coding:utf-8 -*-
# -------------------------------
# @author: dana
# @contact: dana2777@163.com
# @file: activate_ui.py
# @time: 2026/10/18 16:07
# @desc: 
# -------------------------------
import os
import ctypes
import ctypes.wintypes as wt
import struct
import time

from wxauto.uia import uiautomation as auto
import win32api
import win32con
import win32process
import win32gui
from wxauto.exceptions import *

_HAS_WIN32 = True
try:
    import pefile
except Exception:
    pefile = None

# ---------------------------------------------------------------------------
# 企业微信 DuiLib UIA Provider 热激活（内聚自 WeWorkUIA-Universal.py）
ONGET_EXPORT = "?OnGetObject@CWindowWnd@DuiLib@@MAEJIIJAA_N@Z"
HANDLEMSG_SLOTS_BACK = 5
WM_GETOBJECT = 0x3D
OBJID_CLIENT = -4

_K32 = ctypes.windll.kernel32
_PSAPI = ctypes.windll.psapi
_USER32 = ctypes.windll.user32

_K32.OpenProcess.restype = wt.HANDLE
_K32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_K32.ReadProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
_K32.WriteProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
_K32.VirtualProtectEx.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD,
    ctypes.POINTER(wt.DWORD),
]
_K32.VirtualAllocEx.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD,
]
_K32.VirtualAllocEx.restype = ctypes.c_void_p
_K32.VirtualFreeEx.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD,
]
_K32.FlushInstructionCache.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t]
_K32.CloseHandle.argtypes = [wt.HANDLE]
_PSAPI.EnumProcessModulesEx.argtypes = [
    wt.HANDLE, ctypes.POINTER(ctypes.c_void_p), wt.DWORD,
    ctypes.POINTER(wt.DWORD), wt.DWORD,
]
_PSAPI.GetModuleFileNameExW.argtypes = [
    wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD,
]
_USER32.SendMessageW.restype = ctypes.c_ssize_t
_USER32.WaitForInputIdle.argtypes = [wt.HANDLE, wt.DWORD]
_USER32.WaitForInputIdle.restype = wt.DWORD


class _RemoteProcess(object):
    def __init__(self, pid):
        self.handle = _K32.OpenProcess(0x1F0FFF, False, int(pid))
        if not self.handle:
            raise UIAActivationError(
                "OpenProcess({}) 失败 err={}".format(pid, ctypes.GetLastError())
            )

    def read(self, address, size):
        buffer_ = (ctypes.c_char * size)()
        read_size = ctypes.c_size_t(0)
        ok = _K32.ReadProcessMemory(
            self.handle, address, buffer_, size, ctypes.byref(read_size)
        )
        if not ok or read_size.value != size:
            raise UIAActivationError(
                "ReadProcessMemory 失败 @0x{:x} err={}".format(
                    address, ctypes.GetLastError()
                )
            )
        return buffer_.raw

    def read_u32(self, address):
        return struct.unpack("<I", self.read(address, 4))[0]

    def write(self, address, data):
        data = bytes(data)
        written = ctypes.c_size_t(0)
        ok = _K32.WriteProcessMemory(
            self.handle, address, data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise UIAActivationError(
                "WriteProcessMemory 失败 @0x{:x} err={}".format(
                    address, ctypes.GetLastError()
                )
            )

    def protect(self, address, size, protection):
        old = wt.DWORD()
        if not _K32.VirtualProtectEx(
                self.handle, address, size, protection, ctypes.byref(old)
        ):
            raise UIAActivationError(
                "VirtualProtectEx 失败 @0x{:x}".format(address)
            )
        return old.value

    def close(self):
        if self.handle:
            _K32.CloseHandle(self.handle)
            self.handle = None

    def allocate(self, size):
        # MEM_COMMIT | MEM_RESERVE，先写入，再切换为只读可执行。
        address = _K32.VirtualAllocEx(self.handle, None, size, 0x3000, 0x04)
        if not address:
            raise UIAActivationError(
                "无可用代码洞穴，VirtualAllocEx 分配 UIA 补丁内存失败 err={}".format(
                    ctypes.GetLastError()
                )
            )
        return address

    def free(self, address):
        if not _K32.VirtualFreeEx(self.handle, address, 0, 0x8000):
            raise UIAActivationError(
                "VirtualFreeEx 失败 @0x{:x} err={}".format(
                    address, ctypes.GetLastError()
                )
            )

    def flush(self, address, size):
        if not _K32.FlushInstructionCache(self.handle, address, size):
            raise UIAActivationError(
                "FlushInstructionCache 失败 @0x{:x}".format(address)
            )


class _UIAActivator(object):
    """仅负责激活 Provider，不参与任何元素操作。"""

    @staticmethod
    def find_main_window():
        """
        获取企业微信窗口和pid
        """
        if not _HAS_WIN32:
            return None, None
        candidates = []
        visible_shadow_owners = set()

        def collect(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "WeWorkWindow":
                    candidates.append(hwnd)
                elif class_name == "PerryShadowWnd":
                    owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
                    if owner:
                        visible_shadow_owners.add(owner)
            except Exception:
                pass

        win32gui.EnumWindows(collect, None)
        if not candidates:
            return None, None

        def score(item):
            try:
                left, top, right, bottom = win32gui.GetWindowRect(item)
                area = max(0, right - left) * max(0, bottom - top)
                return item in visible_shadow_owners, not win32gui.IsIconic(item), area
            except Exception:
                return False, False, 0

        hwnd = max(candidates, key=score)
        return hwnd, win32process.GetWindowThreadProcessId(hwnd)[1]

    @staticmethod
    def wait_input_idle(pid, timeout=5.0) -> bool:
        """
        等待指定 PID 的 Windows 进程完成初始化，进入输入空闲状态
        Args:
            pid: 进程 ID
            timeout: 最长等待时间，单位秒
        Returns:
        """
        handle = _K32.OpenProcess(0x00100000, False, int(pid))
        if not handle:
            return False
        try:
            return _USER32.WaitForInputIdle(handle, max(1, int(float(timeout) * 1000))) == 0
        finally:
            _K32.CloseHandle(handle)

    @staticmethod
    def wake_window(hwnd):
        return bool(_USER32.SendMessageW(hwnd, WM_GETOBJECT, 1, OBJID_CLIENT & 0xFFFFFFFF))

    @staticmethod
    def _module_map(handle):
        """
        获取指定 Windows 进程加载的模块（DLL、EXE 等）
        Args:
            handle:
        Returns:
        """
        modules = (ctypes.c_void_p * 2048)()
        needed = wt.DWORD()
        if not _PSAPI.EnumProcessModulesEx(
                handle, modules, ctypes.sizeof(modules), ctypes.byref(needed), 3
        ):
            raise UIAActivationError("EnumProcessModulesEx 失败")
        result = {}
        count = needed.value // ctypes.sizeof(ctypes.c_void_p)
        for index in range(count):
            path = ctypes.create_unicode_buffer(520)
            _PSAPI.GetModuleFileNameExW(handle, modules[index], path, 520)
            base = int(modules[index] or 0)
            result[os.path.basename(path.value).lower()] = (base, path.value)
        return result

    @classmethod
    def _find_flag_rvas(cls, pe):
        text = next(section for section in pe.sections if b".text" in section.Name)
        data_sections = [
            section for section in pe.sections
            if section is not text and section.Characteristics & 0x80000000
        ]
        image_base = pe.OPTIONAL_HEADER.ImageBase
        data = text.get_data()
        hits = []
        offset = 0
        while True:
            offset = data.find(b"\x80\x3d", offset)
            if offset < 0:
                break
            if offset + 7 <= len(data) and data[offset + 6] == 0:
                immediate = struct.unpack("<I", data[offset + 2:offset + 6])[0]
                rva = immediate - image_base
                if any(
                        section.VirtualAddress <= rva <
                        section.VirtualAddress + section.Misc_VirtualSize
                        for section in data_sections
                ):
                    hits.append((offset, rva))
            offset += 1
        for first in range(len(hits)):
            for second in range(first + 1, len(hits)):
                if hits[second][0] - hits[first][0] > 0x100:
                    break
                for third in range(second + 1, len(hits)):
                    if hits[third][0] - hits[first][0] > 0x100:
                        break
                    rvas = sorted(hits[index][1] for index in (first, second, third))
                    if len(set(rvas)) == 3 and rvas[2] - rvas[0] <= 4:
                        return rvas
        # 5.0.10 及部分低版本没有三门控标志。相邻 .data 字节可能是无关
        # 调试开关，只有确认 OnGetObject 为无门控旧 ABI 时才跳过写入。
        try:
            onget_rva = cls._find_onget_rva(pe)
            code = pe.get_data(onget_rva, 0x80)
            compares_client = (
                    b"\x83\x7d\x10\xfc" in code[:0x30]
                    or b"\x81\x7d\x10\xfc\xff\xff\xff" in code[:0x30]
            )
            if (
                    code[:3] == b"\x55\x8b\xec"
                    and compares_client
                    and b"\xc2\x10\x00" in code
            ):
                return []
        except Exception:
            pass
        raise UIAActivationError("未找到 DuiLib UIA 门控标志签名簇")

    @staticmethod
    def _find_onget_rva(pe):
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]]
        )
        for export in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            name = export.name.decode("ascii", "ignore") if export.name else ""
            if name == ONGET_EXPORT or name.startswith(
                    "?OnGetObject@CWindowWnd@DuiLib@@"
            ):
                return export.address
        raise UIAActivationError("DuiLib 导出表中未找到 OnGetObject")

    @staticmethod
    def _find_cave_rva(pe, min_length=65, remote=None, image_base=0):
        text = next(section for section in pe.sections if b".text" in section.Name)
        data = text.get_data()
        pattern = b"\xCC" * min_length
        offset = 0
        while True:
            start = data.find(pattern, offset)
            if start < 0:
                break
            end = start + min_length
            while end < len(data) and data[end] == 0xCC:
                end += 1
            reserve = 4 if end - start >= min_length + 4 else 0
            rva = text.VirtualAddress + start + reserve
            if remote is None or remote.read(image_base + rva, min_length) == pattern:
                return rva
            offset = end
        # 5.0.12 可能仅有一处洞穴，主窗口使用后，搜索等窗口需独立分配。
        return None

    @staticmethod
    def _resolves_to(remote, address, target, exe_base, exe_size):
        if address == target:
            return True
        if not exe_base <= address < exe_base + exe_size:
            return False
        try:
            code = remote.read(address, 6)
        except UIAActivationError:
            return False
        if code[:2] == b"\xff\x25":
            try:
                return remote.read_u32(struct.unpack("<I", code[2:6])[0]) == target
            except UIAActivationError:
                return False
        if code[0] == 0xE9:
            return address + 5 + struct.unpack("<i", code[1:5])[0] == target
        return struct.unpack("<I", code[:4])[0] == target

    @classmethod
    def _resolve_handle_message(
            cls, remote, hwnd, onget_va, exe_base, exe_size, exe_text
    ):
        this_ptr = _USER32.GetWindowLongW(hwnd, -21) & 0xFFFFFFFF
        if not this_ptr:
            raise UIAActivationError("企业微信 GWLP_USERDATA 为空")
        vtable = remote.read_u32(this_ptr)
        entries = struct.unpack("<20I", remote.read(vtable, 80))
        slot = None
        for index, entry in enumerate(entries):
            if cls._resolves_to(remote, entry, onget_va, exe_base, exe_size):
                slot = index
                break
        if slot is None or slot < HANDLEMSG_SLOTS_BACK:
            raise UIAActivationError("无法从 DuiLib 虚表定位 HandleMessage")
        address = entries[slot - HANDLEMSG_SLOTS_BACK]
        if not exe_text[0] <= address - exe_base < exe_text[1]:
            raise UIAActivationError("HandleMessage 不在 WXWork.exe .text 内")
        head = remote.read(address, 6)
        if head[0] == 0xE9:
            destination = (address + 5 + struct.unpack("<i", head[1:5])[0]) & 0xFFFFFFFF
            expected = cls._build_stub(address, destination, slot * 4)
            # 补丁既可能位于 EXE 洞穴，也可能位于 VirtualAllocEx 分配的区域。
            if remote.read(destination, len(expected)) != expected:
                raise UIAActivationError("HandleMessage 已被未知补丁修改，取消覆盖")
            return address, True, slot
        body = head[2:] if head[:2] == b"\x66\x90" else head
        if body[:3] != b"\x55\x8b\xec":
            raise UIAActivationError("HandleMessage 序言异常：{}".format(head.hex()))
        return address, False, slot

    @staticmethod
    def _build_stub(entry_va, cave_va, call_offset):
        back = entry_va + 5
        stub = bytearray()
        stub += bytes.fromhex("837c24043d")
        jump1 = len(stub);
        stub += b"\x75\x00"
        stub += bytes.fromhex("837c240cfc")
        jump2 = len(stub);
        stub += b"\x75\x00"
        stub += bytes.fromhex("83ec08c60424008d042450")
        stub += bytes.fromhex("8b44241850")
        stub += bytes.fromhex("8b442418506a008b01")
        stub += b"\xff\x50" + bytes([call_offset])
        stub += bytes.fromhex("803c2400")
        jump3 = len(stub);
        stub += b"\x75\x00"
        stub += bytes.fromhex("83c408")
        fallthrough = len(stub)
        stub += b"\x55\x8b\xec"
        # x86 rel32 按 32 位回绕，独立分配的地址可能相距超过 2GB。
        stub += b"\xe9" + struct.pack(
            "<I", (back - (cave_va + len(stub) + 5)) & 0xFFFFFFFF
        )
        handled = len(stub)
        stub += bytes.fromhex("83c408c20c00")
        stub[jump1 + 1] = (fallthrough - (jump1 + 2)) & 0xFF
        stub[jump2 + 1] = (fallthrough - (jump2 + 2)) & 0xFF
        stub[jump3 + 1] = (handled - (jump3 + 2)) & 0xFF
        return bytes(stub)

    @classmethod
    def _install_stub(cls, remote, entry_va, cave_va, call_offset):
        allocated = cave_va is None
        if allocated:
            cave_va = remote.allocate(len(cls._build_stub(entry_va, 0, call_offset)))
        entry_touched = False
        old_cave = None
        try:
            stub = cls._build_stub(entry_va, cave_va, call_offset)
            original = remote.read(entry_va, 5)
            if not allocated:
                old_cave = remote.protect(cave_va, len(stub), 0x40)
            remote.write(cave_va, stub)
            if allocated:
                remote.protect(cave_va, len(stub), 0x20)  # PAGE_EXECUTE_READ
            remote.flush(cave_va, len(stub))
            jump = b"\xe9" + struct.pack(
                "<I", (cave_va - (entry_va + 5)) & 0xFFFFFFFF
            )
            old_entry = remote.protect(entry_va, len(jump), 0x40)
            try:
                # 写入可能部分成功；只有完整回滚后才能释放补丁内存。
                entry_touched = True
                try:
                    remote.write(entry_va, jump)
                    remote.flush(entry_va, len(jump))
                except Exception:
                    remote.write(entry_va, original)
                    remote.flush(entry_va, len(original))
                    entry_touched = False
                    raise
            finally:
                remote.protect(entry_va, len(jump), old_entry)
        finally:
            if old_cave is not None:
                remote.protect(cave_va, len(stub), old_cave)
            if allocated and not entry_touched:
                remote.free(cave_va)
        # 安装成功的独立内存保留到目标进程退出，重复调用复用入口跳转。

    @classmethod
    def patch_once(cls, dry_run=False, hwnd=None):
        """
        激活企业微信
        Args:
            dry_run:
            hwnd: 窗口句柄

        Returns:

        """
        if pefile is None:
            raise UIAActivationError("缺少 pefile，无法解析企业微信注入偏移")
        if hwnd:
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        else:
            hwnd, pid = cls.find_main_window()
        if not hwnd:
            raise WindowNotFound("未找到企业微信目标窗口")
        remote = _RemoteProcess(pid)
        try:
            modules = cls._module_map(remote.handle)
            if "duilib.dll" not in modules or "wxwork.exe" not in modules:
                raise UIAActivationError("目标进程中未找到 DuiLib.dll/WXWork.exe")
            duilib_base, duilib_path = modules["duilib.dll"]
            exe_base, exe_path = modules["wxwork.exe"]
            duilib_pe = pefile.PE(duilib_path, fast_load=True)
            exe_pe = pefile.PE(exe_path, fast_load=True)
            if any(pe.FILE_HEADER.Machine != 0x14C for pe in (duilib_pe, exe_pe)):
                raise UIAActivationError("当前 UIA 补丁仅支持 x86 企业微信，取消注入")
            text = next(section for section in exe_pe.sections if b".text" in section.Name)
            exe_text = (
                text.VirtualAddress,
                text.VirtualAddress + text.Misc_VirtualSize,
            )
            flag_rvas = cls._find_flag_rvas(duilib_pe)
            onget_va = duilib_base + cls._find_onget_rva(duilib_pe)
            handle_message, already, slot = cls._resolve_handle_message(
                remote, hwnd, onget_va, exe_base,
                exe_pe.OPTIONAL_HEADER.SizeOfImage, exe_text,
            )
            cave_va = None
            if not already:
                stub_length = len(cls._build_stub(0x1000, 0x2000, 0))
                cave_rva = cls._find_cave_rva(
                    exe_pe, stub_length, remote, exe_base
                )
                if cave_rva is not None:
                    cave_va = exe_base + cave_rva
            if dry_run:
                return pid

            current = b"".join(remote.read(duilib_base + rva, 1) for rva in flag_rvas)
            if current != b"\x01" * len(flag_rvas):
                for rva in flag_rvas:
                    remote.write(duilib_base + rva, b"\x01")
            if not already:
                cls._install_stub(remote, handle_message, cave_va, slot * 4)
        finally:
            remote.close()
        if not cls.wake_window(hwnd):
            raise UIAActivationError("WM_GETOBJECT 未返回企业微信 UIA Provider")
        return pid


def _main_content_ready(window):
    try:
        children = window.GetChildren()
    except Exception:
        return False
    for child in children:
        if getattr(child, "ClassName", "") in ("TitleBarWindow", "PerryShadowWnd"):
            continue
        try:
            if getattr(child, "Name", "") or child.GetChildren():
                return True
        except Exception:
            pass
    return False


def _activate_uia_tree(dry_run=False, timeout=25.0, hwnd=None):
    if not hwnd:
        hwnd, pid = _UIAActivator.find_main_window()
    else:
        # 根据 窗口获取pid
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    if not hwnd:
        raise WindowNotFound("未找到企业微信，请先启动并登录客户端")

    _UIAActivator.wait_input_idle(pid, min(float(timeout), 10.0))
    time.sleep(0.2)
    pid = _UIAActivator.patch_once(dry_run=dry_run, hwnd=hwnd)
    if dry_run:
        return pid
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        current_hwnd, current_pid = _UIAActivator.find_main_window()
        if current_hwnd and current_pid == pid:
            try:
                window = auto.ControlFromHandle(current_hwnd)
                if win32gui.IsIconic(current_hwnd):
                    win32gui.ShowWindow(current_hwnd, win32con.SW_RESTORE)
                try:
                    win32gui.SetForegroundWindow(current_hwnd)
                except Exception:
                    pass
                try:
                    window.SetActive()
                except Exception:
                    pass
                _UIAActivator.wake_window(current_hwnd)
                if _main_content_ready(window):
                    return window
            except Exception:
                pass
        time.sleep(0.2)
    raise UIAActivationError("注入完成，但企业微信 UIA 内容树未就绪")
