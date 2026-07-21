# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from mewcode.agent import AgentControl, AgentOptions, stream_agent_reply
from mewcode.conversation import Conversation
from mewcode.permissions import (
    PermissionManager,
    PermissionMode,
    PermissionScope,
    next_permission_mode,
)
from mewcode.providers.base import ChatProvider, ProviderConfig
from mewcode.tools.base import ToolContext
from mewcode.tools.registry import ToolRegistry, create_default_registry

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]

_ESC = chr(27)
R  = _ESC + "[0m"
B  = _ESC + "[1m"
D  = _ESC + "[2m"
GY = _ESC + "[90m"
BL = _ESC + "[34m"
GN = _ESC + "[32m"
YW = _ESC + "[33m"
MG = _ESC + "[35m"
CY = _ESC + "[36m"
RD = _ESC + "[31m"

_TL, _TR, _BLb, _BR, _H, _V, _SP = [chr(c) for c in (0x256d, 0x256e, 0x2570, 0x256f, 0x2500, 0x2502, 0x00a0)]

_C1 = "      /\\_/\\"
_C2 = "     " + chr(0xff08) + "o.o" + chr(0xff09)
_C3 = "      > ^ <"
_CAT = _C1 + "\n" + _C2 + "\n" + _C3

MODE_COLORS = {"def": BL, "edit": GN, "plan": YW, "bypass": MG}
MODE_SHORT  = {"default": "def", "acceptEdits": "edit", "plan": "plan", "bypassPermissions": "bypass"}

_SPINNER = [chr(0x25d0), chr(0x25d1), chr(0x25d3), chr(0x25d2)]

def _ms(m: str) -> str:
    return MODE_SHORT.get(m, m[:6])

def _box(lines: list[str], w: int = 38, color: str = "") -> str:
    c = color or ""
    top = c + _TL + _H * (w + 2) + _TR + R
    mid = "\n".join(c + _V + _SP + s.ljust(w) + _SP + _V + R for s in lines)
    bot = c + _BLb + _H * (w + 2) + _BR + R
    return top + "\n" + mid + "\n" + bot

def _shorten(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + chr(0x2026)

_SPINNER_THREADS: dict[str, threading.Thread] = {}
_SPINNER_STOP: dict[str, threading.Event] = {}
_LAST_LINE_LEN = 0

def _start_spinner(ou, name: str, tid: str) -> None:
    if tid in _SPINNER_THREADS:
        return
    ev = threading.Event()
    _SPINNER_STOP[tid] = ev
    mc = CY

    def _spin():
        global _LAST_LINE_LEN
        idx = 0
        while not ev.is_set():
            ch = _SPINNER[idx % len(_SPINNER)]
            elapsed = time.monotonic() - _tool_starts.get(tid, time.monotonic())
            text = "  " + mc + chr(0x250c) + R + " 工具 " + mc + name + R + GY + " " + ch + " " + format(elapsed, ".0f") + "s" + R
            if idx == 0:
                _wl(ou, text)
            else:
                raw = chr(13) + " " * _LAST_LINE_LEN + chr(13) + text
                _LAST_LINE_LEN = len(text)
                if ou is print:
                    try: print(raw, end="", flush=True)
                    except UnicodeEncodeError: pass
                else: ou(raw)
            idx += 1
            ev.wait(0.3)

    t = threading.Thread(target=_spin, daemon=True)
    _SPINNER_THREADS[tid] = t
    t.start()

def _stop_spinner(ou, tid: str) -> None:
    ev = _SPINNER_STOP.pop(tid, None)
    if ev:
        ev.set()
    _SPINNER_THREADS.pop(tid, None)
    _SPINNER_STOP.pop(tid, None)

_tool_starts: dict[str, float] = {}
_tid_for_tool: dict[str, str] = {}

def run_chat_loop(config, provider, input_func=input, output_func=print, registry=None, workspace=None, options=None):
    global _tool_starts
    conv = Conversation()
    reg = registry or create_default_registry()
    wd = workspace or Path.cwd()
    opts = options or AgentOptions()
    pm = PermissionManager.from_files(wd, callback=_ask(input_func, output_func), mode_override=opts.permission_mode)
    ctx = ToolContext(workspace=wd, permission_manager=pm)
    _banner(output_func, config, reg, pm, provider)

    while True:
        mode_key = _ms(pm.mode.value)
        mc = MODE_COLORS.get(mode_key, "")
        try:
            inp = input_func(mc + B + "你" + R + GY + " ? " + R).strip()
        except (EOFError, KeyboardInterrupt):
            _wl(output_func, mc + " 再见")
            return 0
        if not inp: continue
        if inp in ("/exit", "/quit"):
            _wl(output_func, mc + " 再见")
            return 0
        if inp == "/mode":
            pm.mode = next_permission_mode(pm.mode)
            opts = _wm(opts, pm.mode)
            mk = _ms(pm.mode.value)
            _wl(output_func, MODE_COLORS.get(mk, "") + " " + mk.upper())
            continue
        if inp == "/plan":
            pm.mode = PermissionMode.PLAN
            opts = _wm(opts, pm.mode)
            _wl(output_func, YW + " plan")
            continue
        if inp == "/do":
            pm.mode = PermissionMode.DEFAULT
            opts = _wm(opts, pm.mode)
            inp = "请根据上文计划开始执行。"
            _wl(output_func, BL + " 开始执行")

        conv.add_user_message(inp)
        ctrl = AgentControl()
        _tool_starts.clear()
        _shown_prefix = False

        for ev in stream_agent_reply(conv, config, provider, reg, ctx, options=opts, control=ctrl):
            if ev.type == "text":
                if not _shown_prefix:
                    _wl(output_func, CY + chr(0x250c) + " MewCode " + chr(0x2500) + " " + R)
                    _shown_prefix = True
                _w(output_func, ev.content)

            elif ev.type == "thinking":
                _wl(output_func, GY + " " + D + ev.content + R)

            elif ev.type == "tool_start":
                tid = ev.tool_call_id or ""
                _tool_starts[tid] = time.monotonic()
                _tid_for_tool[ev.tool_name or ""] = tid
                _start_spinner(output_func, ev.tool_name or "", tid)

            elif ev.type == "tool_result":
                tid = ev.tool_call_id or ""
                t0 = _tool_starts.pop(tid, None)
                elapsed = time.monotonic() - t0 if t0 else 0.0
                _stop_spinner(output_func, tid)
                _tid_for_tool.pop(ev.tool_name or "", None)
                summary = _shorten(ev.content or "", 60)
                is_err = any(kw in (ev.content or "") for kw in ["失败", "错误", "拒绝", "拦截", "超时"])
                result_color = RD if is_err else GN
                indent = "  " if _shown_prefix else ""
                _wl(output_func, indent + GY + chr(0x2514) + R + " " + result_color + "结果" + R + GY + " " + summary + R)
                _wl(output_func, indent + "  " + GY + chr(0x23f1) + " " + format(elapsed, ".1f") + "s" + R)

            elif ev.type == "error":
                _wl(output_func, RD + " " + RD + "错误" + R + " " + ev.content)

            elif ev.type == "cancelled":
                _wl(output_func, YW + " " + YW + "已取消" + R)

            elif ev.type == "done":
                break

        output_func("")

def _banner(ou, config, reg, pm, provider):
    names = reg.names()
    mcps = [n for n in names if n.startswith("mcp__")]
    bc = len(names) - len(mcps)
    seen: set[str] = set()
    servers: list[str] = []
    for n in mcps:
        p = n.split("__", 2)
        if len(p) >= 2 and p[1] not in seen:
            seen.add(p[1])
            servers.append(p[1])
    mk = _ms(pm.mode.value)
    mc = MODE_COLORS.get(mk, BL)

    provider_line = "提供方  " + config.name + " / " + config.model
    tool_line = "工具 " + str(bc)
    if mcps:
        tool_line += " + " + str(len(mcps)) + " MCP"
    mode_line = "模式    " + B + mc + mk.upper() + R
    lines = [provider_line, tool_line, mode_line]
    if servers:
        lines.append("MCP      " + ", ".join(servers))
    lines.append("帮助    /exit /mode /plan /do")
    _wl(ou, _CAT)
    _wl(ou, _box(lines, color=mc))

def _w(ou, t):
    if ou is print:
        try:
            print(t, end="", flush=True)
        except UnicodeEncodeError:
            e = sys.stdout.encoding or "utf-8"
            print(t.encode(e, errors="replace").decode(e), end="", flush=True)
    else:
        ou(t)

def _wl(ou, t):
    if ou is print:
        try:
            print(t, flush=True)
        except UnicodeEncodeError:
            e = sys.stdout.encoding or "utf-8"
            print(t.encode(e, errors="replace").decode(e), flush=True)
    else:
        ou(t)

def _stop_all_spinners(ou) -> None:
    for tid in list(_SPINNER_STOP.keys()):
        _stop_spinner(ou, tid)
    global _LAST_LINE_LEN
    if _LAST_LINE_LEN > 0:
        raw = chr(13) + " " * _LAST_LINE_LEN + chr(13)
        if ou is print:
            try: print(raw, end="", flush=True)
            except UnicodeEncodeError: pass
        else: ou(raw)
        _LAST_LINE_LEN = 0

def _ask(inp, ou):
    def fn(r):
        _stop_all_spinners(ou)
        _wl(ou, "")
        _wl(ou, YW + chr(0x250c) + chr(0x2500) * 4 + "权限" + chr(0x2500) * 4 + R)
        _wl(ou, YW + _V + R + " " + r.tool_name + "  " + GY + _pt(r) + R)
        _wl(ou, YW + _V + R + GY + "  1=" + R + "允许本次" + "  " + GY + "2=" + R + "永久允许" + "  " + GY + "3=" + R + "拒绝")
        _wl(ou, YW + chr(0x2514) + chr(0x2500) * 40 + R)
        while True:
            try:
                c = inp(YW + " 权限?" + R + " ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False, PermissionScope.ONCE
            if c in ("1", "y", "yes"):
                tid = _tid_for_tool.get(r.tool_name, "")
                if tid:
                    _tool_starts[tid] = time.monotonic()
                    _start_spinner(ou, r.tool_name, tid)
                return True, PermissionScope.ONCE
            if c in ("2", "p", "permanent"):
                tid = _tid_for_tool.get(r.tool_name, "")
                if tid:
                    _tool_starts[tid] = time.monotonic()
                    _start_spinner(ou, r.tool_name, tid)
                return True, PermissionScope.PERMANENT
            if c in ("3", "n", "no", ""):
                return False, PermissionScope.ONCE
            _wl(ou, GY + " " + chr(0x2502) + R + GY + " 请输入 1/2/3" + R)
    return fn

def _pt(r):
    if r.tool_name == "run_command":
        return str(r.arguments.get("command") or "")
    if r.tool_name in ("read_file", "write_file", "replace_in_file"):
        return str(r.arguments.get("path") or "")
    if r.tool_name == "find_files":
        return str(r.arguments.get("pattern") or "")
    if r.tool_name == "search_code":
        return str(r.arguments.get("query") or r.arguments.get("pattern") or "")
    return str(r.arguments)

def _wm(opts, mode):
    return AgentOptions(
        max_rounds=opts.max_rounds,
        plan_only=opts.plan_only,
        permission_mode=mode.value,
        overall_timeout_seconds=opts.overall_timeout_seconds,
        per_round_timeout_seconds=opts.per_round_timeout_seconds,
    )
