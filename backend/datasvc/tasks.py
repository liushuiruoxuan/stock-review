"""
后台任务注册表：长任务（行情全量同步、回测等）在独立线程执行，
进程内记录进度，供前端轮询。进程重启后任务状态丢失（回测结果另存 MySQL）。
"""
import threading
import time
import uuid

TASKS = {}  # id -> dict
_LOCK = threading.Lock()


def snapshot():
    with _LOCK:
        return sorted(TASKS.values(), key=lambda t: t["started_at"], reverse=True)


def get(task_id):
    with _LOCK:
        return TASKS.get(task_id)


def _new_task(kind, note=""):
    task_id = uuid.uuid4().hex[:12]
    with _LOCK:
        TASKS[task_id] = {
            "id": task_id,
            "kind": kind,
            "note": note,
            "status": "running",
            "progress": 0,       # 0-100
            "total": 0,
            "current": 0,
            "detail": "",
            "error": None,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
        }
    return TASKS[task_id]


def _update(task_id, **fields):
    with _LOCK:
        t = TASKS.get(task_id)
        if t:
            t.update(fields)


def run_task(kind, fn, note=""):
    """在后台线程执行 fn(task_id)。返回 task_id。"""
    task_id_holder = {}

    def wrapper():
        tid = task_id_holder["id"]
        try:
            fn(tid)
            _update(tid, status="done", progress=100,
                    finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print("[task:%s] %s 失败：" % (tid, kind), e)
            _update(tid, status="failed", error=str(e)[:500],
                    finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))

    # 注意：_new_task 内部已持有 _LOCK（threading.Lock 非重入），
    # 此处不能再包一层 with _LOCK，否则会与 _new_task 自锁死锁。
    t = _new_task(kind, note)
    task_id_holder["id"] = t["id"]
    th = threading.Thread(target=wrapper, daemon=True)
    th.start()
    return t["id"]


def set_progress(task_id, current, total, detail=""):
    pct = int(current * 100 / total) if total else 0
    _update(task_id, current=current, total=total, progress=min(pct, 99), detail=detail)
