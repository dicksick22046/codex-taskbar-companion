"""Codex app-server client; does not start or resume agent turns."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


class CodexApi:
    def __init__(self):
        candidates = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI/Codex/bin").glob("*/codex.exe"))
        if not candidates:
            raise RuntimeError("未找到 Codex 桌面运行程序")
        executable = max(candidates, key=lambda p: p.stat().st_mtime)
        self.process = subprocess.Popen(
            [str(executable), "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=0x08000000,
        )
        self.messages = queue.Queue()
        self.sequence = 0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call("initialize", {
                "clientInfo": {"name": "codex_taskbar_status", "version": "0.1"},
                "capabilities": {"experimentalApi": True, "requestAttestation": False},
            })
        except Exception:
            self.close()
            raise
        self.process.stdin.write('{"method":"initialized"}\n')
        self.process.stdin.flush()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    item = json.loads(line)
                    if "id" in item:
                        self.messages.put(item)
                except ValueError:
                    pass
        finally:
            self.messages.put({"disconnected": True})

    def call(self, method, params=None):
        self.sequence += 1
        request = {"id": self.sequence, "method": method}
        if params is not None:
            request["params"] = params
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:item = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as exc:raise TimeoutError(f'{method}: response timed out') from exc
            if item.get("disconnected"):
                raise ConnectionError("Codex 数据连接已关闭")
            if item.get("id") == self.sequence:
                if "error" in item:
                    raise RuntimeError(item["error"].get("message", "Codex 数据读取失败"))
                return item["result"]
        raise TimeoutError(method)

    def catalog(self):
        projects = self.call("project/list", {})["data"]
        threads = {}
        cursor = None
        while True:
            params = {"limit": 100, "sortKey": "updated_at", "useStateDbOnly": True,
                      "sourceKinds": ["cli", "vscode", "appServer", "exec"]}
            if cursor:
                params["cursor"] = cursor
            page = self.call("thread/list", params)
            for thread in page['data']:
                if not thread.get('parentThreadId'):threads.setdefault(thread['id'],thread)
            cursor = page.get("nextCursor")
            if not cursor:
                return projects, list(threads.values())

    def latest_turn(self,thread_id):
        result=self.call('thread/turns/list',{'threadId':thread_id,'limit':1,
                         'sortDirection':'desc','itemsView':'notLoaded'})
        turn=next(iter(result.get('data',[])),None)
        if not turn:return None
        return {key:turn.get(key) for key in ('id','status','error','completedAt')}

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()


def project_name(thread, projects):
    for project in projects:
        if project["id"] == thread.get("projectId"):
            return project["name"]
    cwd = os.path.normcase(os.path.normpath(thread.get("cwd", "")))
    matches = []
    for project in projects:
        for root in project.get("roots", []):
            path = os.path.normcase(os.path.normpath(root["path"]))
            if cwd == path or cwd.startswith(path + os.sep):
                matches.append((len(path), project["name"]))
    return max(matches)[1] if matches else ""
