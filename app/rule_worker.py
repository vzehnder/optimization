"""Run with python -m app.rule_worker on the trusted Linux executor host."""
from __future__ import annotations

import json
import signal
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.component_rules import RuleRepository, encode, timestamp
from app.persistence import AnalystStore
from app.rule_runtime import OCIExecutor, RuntimeUnavailable


class RuleWorker:
    def __init__(self, store, executor, *, queue_timeout=30.0):
        self.store, self.executor = store, executor
        self.repository = RuleRepository(store)
        self.owner = uuid.uuid4().hex
        self.queue_timeout = queue_timeout
        self.stopping = threading.Event()
        self.active = {}
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="component-rule")
        self.thread = None

    def __enter__(self):
        runtime = self.executor.describe()
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute(
                "INSERT INTO component_rule_worker VALUES (1, '', 0, '{}') ON CONFLICT (id) DO NOTHING"
            )
            self.store.connection.execute("UPDATE component_rule_worker SET heartbeat = heartbeat WHERE id = 1")
            row = self.store.connection.execute("SELECT * FROM component_rule_worker WHERE id = 1").fetchone()
            if time.time() - row["heartbeat"] <= 10:
                raise RuntimeUnavailable("Ya hay un worker activo")
            self.store.connection.execute(
                "UPDATE component_rule_worker SET owner = ?, heartbeat = ?, runtime = '{}' WHERE id = 1",
                # Recovery may need two bounded daemon operations per orphan.
                (self.owner, time.time() + 60),
            )
            interrupted = self.store.connection.execute(
                "SELECT id FROM component_rule_jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
        for job in interrupted:
            self.executor.remove(job["id"])
            self.finish(job["id"], {"status": "failed", "error": {"code": "RULE_INTERRUPTED", "message": "Prueba interrumpida por reinicio"}}, recovery=True)
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute(
                "UPDATE component_rule_worker SET runtime = ?, heartbeat = ? WHERE id = 1 AND owner = ?",
                (encode(runtime), time.time(), self.owner),
            )
        self.thread = threading.Thread(target=self.run, name="component-rule-worker", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=30)
        self.pool.shutdown(wait=True)
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute("UPDATE component_rule_worker SET heartbeat = 0, runtime = '{}' WHERE owner = ?", (self.owner,))

    def finish(self, job_id, result, *, recovery=False):
        with self.store._lock, self.store._database_transaction():
            self.store.connection.execute(
                "UPDATE component_rule_jobs SET status = ?, result = ?, updated_at = ? "
                "WHERE id = ? AND status IN ('queued', 'running')" + ("" if recovery else " AND worker_owner = ?"),
                (result["status"], encode(result), timestamp(), job_id, *(() if recovery else (self.owner,))),
            )

    def execute(self, job_id, payload, cancel):
        try:
            result = self.executor.execute(payload, job_id, cancel)
        except Exception:
            # If cleanup cannot be confirmed, retain the running job for recovery.
            # Stop advertising availability; never lose track of its container.
            self.stopping.set()
            with self.store._lock, self.store._database_transaction():
                self.store.connection.execute(
                    "UPDATE component_rule_worker SET runtime = '{}' WHERE owner = ?", (self.owner,)
                )
            return
        self.finish(job_id, result)

    def run(self):
        try:
            while not self.stopping.is_set():
                with self.store._lock, self.store._database_transaction():
                    updated = self.store.connection.execute(
                        "UPDATE component_rule_worker SET heartbeat = ? WHERE id = 1 AND owner = ?",
                        (time.time(), self.owner),
                    ).rowcount
                    if updated != 1:
                        break
                    expired = self.store.connection.execute(
                        "SELECT id FROM component_rule_jobs WHERE status = 'queued' AND queued_at < ?",
                        (time.time() - self.queue_timeout,),
                    ).fetchall()
                    for job in expired:
                        result = {"status": "failed", "error": {"code": "RULE_QUEUE_TIMEOUT", "message": "Tiempo máximo de espera en cola excedido"}}
                        self.store.connection.execute(
                            "UPDATE component_rule_jobs SET status = 'failed', result = ?, updated_at = ? WHERE id = ?",
                            (encode(result), timestamp(), job["id"]),
                        )
                    for job_id, (future, cancel) in list(self.active.items()):
                        if future.done():
                            del self.active[job_id]
                            continue
                        row = self.store.connection.execute("SELECT cancel_requested FROM component_rule_jobs WHERE id = ?", (job_id,)).fetchone()
                        if row["cancel_requested"]:
                            cancel.set()
                    jobs = self.store.connection.execute(
                        "SELECT j.id, j.queued_at, s.payload FROM component_rule_jobs j "
                        "JOIN component_rule_snapshots s ON s.id = j.id "
                        "WHERE j.status = 'queued' ORDER BY queued_at LIMIT ?", (2 - len(self.active),),
                    ).fetchall()
                    for job in jobs:
                        self.store.connection.execute("UPDATE component_rule_jobs SET status = 'running', worker_owner = ?, updated_at = ? WHERE id = ?", (self.owner, timestamp(), job["id"]))
                        cancel = threading.Event()
                        future = self.pool.submit(self.execute, job["id"], json.loads(job["payload"]), cancel)
                        self.active[job["id"]] = (future, cancel)
                self.stopping.wait(0.1)
        finally:
            for _, cancel in self.active.values():
                cancel.set()


def main():
    store = AnalystStore()
    worker = RuleWorker(store, OCIExecutor.from_env())
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: worker.stopping.set())
    try:
        with worker:
            while not worker.stopping.wait(0.5):
                if not worker.thread.is_alive():
                    raise RuntimeError("El worker se detuvo")
    finally:
        store.close()


if __name__ == "__main__":
    main()
