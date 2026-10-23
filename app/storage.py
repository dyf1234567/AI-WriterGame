"""存档读写：data/state.json，原子写入。"""
import json
import os
import tempfile
import shutil
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re

from . import memory
from .config import DATA_DIR, STATE_FILE, STORY_ARCHIVE_FILE, NPC_ARCHIVE_FILE
from .models import normalize_state

_lock = threading.RLock()


class StorageBusy(RuntimeError):
    pass


class RollbackFailed(RuntimeError):
    """事务回滚自身失败——此时存档可能不一致，必须与普通读写失败区分开。"""


@contextmanager
def transaction():
    """覆盖整个读取、计算、保存过程；同时保护同目录的多个服务实例。"""
    if not _lock.acquire(timeout=3):
        raise StorageBusy("另一个操作正在进行，请稍后重试。")
    handle = None
    locked = False
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        handle = (DATA_DIR / ".state.lock").open("a+b")
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + 3
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise StorageBusy("另一个游戏实例正在操作此存档，请稍后重试。")
                time.sleep(.05)
        paths = (STATE_FILE, STORY_ARCHIVE_FILE, NPC_ARCHIVE_FILE)
        original = {p: p.read_bytes() if p.exists() else None for p in paths}
        try:
            yield
        except Exception as inner:
            # 归档可能在压缩/人物淘汰时先发生变化，异常时必须与主存档一起回滚。
            # 回滚自身失败要单独暴露——它意味着存档可能不一致，
            # 不能让上层误报"原进度已保留"。
            try:
                for path, content in original.items():
                    if content is None:
                        path.unlink(missing_ok=True)
                    elif not path.exists() or path.read_bytes() != content:
                        fd, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".rollback")
                        try:
                            with os.fdopen(fd, "wb") as output:
                                output.write(content)
                            os.replace(temporary, path)
                        finally:
                            if os.path.exists(temporary):
                                os.unlink(temporary)
            except OSError as rb_err:
                raise RollbackFailed(f"事务回滚失败，存档可能不一致：{rb_err}") from inner
            raise
    finally:
        if handle:
            if locked:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
        _lock.release()


def snapshot(paths=None) -> str | None:
    """在覆盖前保留可恢复快照；新周目同时备份两份归档。"""
    paths = list(paths or [STATE_FILE, STORY_ARCHIVE_FILE, NPC_ARCHIVE_FILE])
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    folder = DATA_DIR / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    folder.mkdir(parents=True)
    for path in existing:
        shutil.copy2(path, folder / path.name)
    (folder / "complete").write_text("ok", encoding="ascii")
    # 仅清理本程序生成、且完整落盘的旧备份；保留最近50个操作检查点。
    generated = sorted(p for p in folder.parent.iterdir()
                       if p.is_dir() and (p / "complete").exists()
                       and re.fullmatch(r"\d{8}T\d{12}", p.name))
    for old in generated[:-50]:
        for filename in (STATE_FILE.name, STORY_ARCHIVE_FILE.name, NPC_ARCHIVE_FILE.name):
            (old / filename).unlink(missing_ok=True)
        (old / "complete").unlink(missing_ok=True)
        try:
            old.rmdir()
        except OSError:
            pass
    return str(folder)


def load() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        return normalize_state(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, KeyError, AttributeError) as e:
        raise OSError("存档损坏，请从备份恢复，不能覆盖原文件。") from e


def save(state: dict, *, backup: bool = True) -> None:
    from . import media
    media.bind_history(state)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if backup and STATE_FILE.exists():
        snapshot()
    state["revision"] = int(state.get("revision", 0)) + 1
    fd, tmp = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    # 存档成功后刷新人可读的记忆手册；导出失败不影响游戏
    try:
        memory.export_manual(state)
    except Exception:
        pass


def replace_game(state: dict, archives) -> None:
    """新开局已生成且校验通过后才替换；中途失败则恢复原文件。"""
    paths = [STATE_FILE, *archives]
    backup = snapshot(paths)
    existed = {p for p in paths if p.exists()}
    current = load()
    state["revision"] = current.get("revision", 0) if current else 0
    try:
        for p in archives:
            p.unlink(missing_ok=True)
        save(state, backup=False)
    except Exception:
        for path in paths:
            if path in existed and backup:
                shutil.copy2(Path(backup) / path.name, path)
            elif path.exists():
                path.unlink()
        raise


def backups() -> list[dict]:
    root = DATA_DIR / "backups"
    result = []
    if root.exists():
        for folder in sorted(root.iterdir(), reverse=True):
            if not folder.is_dir() or not (folder / "complete").exists() or not re.fullmatch(r"\d{8}T\d{12}", folder.name):
                continue
            try:
                state = json.loads((folder / STATE_FILE.name).read_text(encoding="utf-8"))
                result.append({"id": folder.name, "name": state["player"]["name"],
                               "turn": state["turn"]})
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return result


def restore(backup_id: str) -> dict:
    if not re.fullmatch(r"\d{8}T\d{12}", backup_id):
        raise ValueError("无效的备份编号")
    folder = DATA_DIR / "backups" / backup_id
    if not (folder / "complete").exists():
        raise ValueError("备份不完整")
    state = normalize_state(json.loads((folder / STATE_FILE.name).read_text(encoding="utf-8")))
    paths = (STORY_ARCHIVE_FILE, NPC_ARCHIVE_FILE)
    archive_bytes = {p: (folder / p.name).read_bytes() if (folder / p.name).exists() else None
                     for p in paths}
    # 恢复操作本身也有完整备份；归档一起回滚，避免未来剧情串进过去。
    current_backup = snapshot()
    try:
        current = load()
    except OSError:
        current = None
    state["revision"] = current.get("revision", 0) if current else int(time.time() * 1000)
    try:
        for path in paths:
            content = archive_bytes[path]
            if content is not None:
                path.write_bytes(content)
            else:
                path.unlink(missing_ok=True)
        save(state, backup=False)
    except Exception:
        if current_backup:
            for path in (STATE_FILE, *paths):
                source = Path(current_backup) / path.name
                if source.exists():
                    shutil.copy2(source, path)
                else:
                    path.unlink(missing_ok=True)
        raise
    return state
