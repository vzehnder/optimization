"""Trusted OCI client used by the separate worker, never to execute inside HTTP."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import threading
import time

SDK_VERSION = "reg-005.1"
POLICY_VERSION = "reg-001.1"


class RuntimeUnavailable(RuntimeError):
    pass


class OCIExecutor:
    def __init__(self, command, image, *, timeout=5.0):
        if not re.fullmatch(r"(?:[\w./:-]+@)?sha256:[a-f0-9]{64}", image):
            raise RuntimeUnavailable("La imagen debe estar fijada por digest SHA-256")
        self.command, self.image, self.timeout = list(command), image, timeout

    @classmethod
    def from_env(cls):
        return cls(json.loads(os.environ.get("RULE_RUNTIME_COMMAND", '["docker"]')),
                   os.environ.get("RULE_RUNTIME_IMAGE", ""))

    def control(self, *args):
        try:
            result = subprocess.run([*self.command, *args], capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeUnavailable("No se puede contactar al runtime OCI") from error
        if result.returncode:
            raise RuntimeUnavailable("El runtime OCI rechazó la operación")
        return result.stdout.decode("utf-8").strip()

    def describe(self):
        info = json.loads(self.control("info", "--format", "{{json .}}"))
        if info.get("OSType") != "linux" or not any("seccomp" in str(x) for x in info.get("SecurityOptions", [])):
            raise RuntimeUnavailable("Se requiere Linux con seccomp")
        self.control("image", "inspect", self.image)
        return {"image": self.image, "sdk": SDK_VERSION, "policy": POLICY_VERSION}

    def remove(self, job_id):
        name = self.name(job_id)
        ids = self.control("ps", "-aq", "--filter", f"name=^/{name}$")
        if ids:
            self.control("rm", "-f", name)

    @staticmethod
    def name(job_id):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("Invalid job identity")
        return f"component-rule-{job_id}"

    def execute(self, payload, job_id, cancel):
        raw = json.dumps(payload, allow_nan=False).encode()
        if len(raw) > 64 * 1024 * 1024:
            return {"status": "failed", "error": {"code": "RULE_INPUT_LIMIT", "message": "Entrada excesiva"}}
        name = self.name(job_id)
        process = None
        try:
            self.control(
                "create", "-i", "--name", name, "--label", "component-rules=reg-001",
                "--network=none", "--read-only", "--user=65532:65532", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--cpus=1", "--memory=512m", "--memory-swap=512m",
                "--pids-limit=32", "--ulimit=nofile=64:64", "--ulimit=core=0:0",
                "--log-driver=none", "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m",
                self.image,
            )
            if cancel.is_set():
                return {"status": "cancelled"}
            process = subprocess.Popen([*self.command, "start", "-a", "-i", name],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, stderr = bytearray(), bytearray()
            overflow = threading.Event()

            def read(stream, target, limit):
                while chunk := stream.read(4096):
                    if len(target) + len(chunk) > limit:
                        overflow.set()
                        break
                    target.extend(chunk)

            def write():
                try:
                    process.stdin.write(raw)
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            readers = [threading.Thread(target=read, args=(process.stdout, output, 64 * 1024 * 1024)),
                       threading.Thread(target=read, args=(process.stderr, stderr, 65536))]
            writer = threading.Thread(target=write)
            for thread in [*readers, writer]:
                thread.start()
            deadline = time.monotonic() + self.timeout
            failure = None
            while process.poll() is None:
                if cancel.is_set():
                    failure = {"status": "cancelled"}
                elif overflow.is_set():
                    failure = {"status": "failed", "error": {"code": "RULE_OUTPUT_LIMIT", "message": "Salida excesiva"}}
                elif time.monotonic() >= deadline:
                    failure = {"status": "failed", "error": {"code": "RULE_TIMEOUT", "message": "Tiempo de ejecución excedido"}}
                if failure:
                    self.remove(job_id)
                    break
                time.sleep(0.02)
            process.wait(timeout=15)
            for thread in [*readers, writer]:
                thread.join(timeout=2)
            if failure:
                return failure
            state = json.loads(self.control("inspect", "--format", "{{json .State}}", name))
            if state.get("OOMKilled"):
                return {"status": "failed", "error": {"code": "RULE_MEMORY_LIMIT", "message": "Memoria del sandbox excedida"}}
            try:
                result = json.loads(output)
                if result["status"] not in {"succeeded", "failed"}:
                    raise ValueError()
                runtime = result["runtime"]
                if runtime["sdk"] != SDK_VERSION or not re.fullmatch(r"3\.12\.\d+", runtime["python"]):
                    raise ValueError()
                if result["status"] == "succeeded":
                    if "grid" in payload:
                        from app.rule_ir import validate_ir, validate_outputs, validate_bounds, validate_model_bounds, RuleBoundsError
                        value = {"ir": validate_ir(result["ir"], payload["object"]["id"], len(payload["grid"]), payload.get("objects")),
                                 "outputs": validate_outputs(result["outputs"], len(payload["grid"]))}
                        if payload.get("temporal"):
                            value["temporal"] = {**payload["temporal"], "omitted_periods": [0] if payload["temporal"]["first_period"] == "omit" else []}
                        if "compilation" in payload:
                            compilation = payload["compilation"]
                            unit = next(u for u in compilation["system_case"]["hydraulic_network"]["units"] if u["id"] == compilation["unit_key"])
                            try:
                                if payload.get("objects"):
                                    validate_model_bounds(value["ir"]["rows"], payload["objects"], compilation["system_case"])
                                flow_rows = [r for r in value["ir"]["rows"] if r["unit"] == "m3_per_s" and all(
                                    t["object_id"] == payload["object"]["id"] and t["variable"] == "caudal" for t in r["terms"])]
                                value["bounds"] = validate_bounds(flow_rows, unit, len(payload["grid"])) if flow_rows and not payload.get("temporal") else []
                            except RuleBoundsError as error:
                                error.problem["alias"] = next((a["alias"] for a in payload.get("aliases", []) if a["object_id"] == error.problem.get("object_id")), "objeto")
                                return {"status": "failed", "error": error.problem, "runtime": runtime}
                    else:
                        output_value = result["output"]
                        if output_value["unit"] != "m3_per_s" or type(output_value["value"]) not in {int, float} or not math.isfinite(output_value["value"]):
                            raise ValueError()
                        value = {"output": output_value}
                    logs = result.get("logs", "")
                    if not isinstance(logs, str) or len(logs.encode()) > 65536:
                        raise ValueError()
                    return {"status": "succeeded", **value, "logs": logs, "runtime": {**runtime, "image": self.image, "policy": POLICY_VERSION}}
                error = result["error"]
                code = error.get("code") if error.get("code") in {"RULE_LOG_LIMIT", "RULE_CODE_ERROR"} else "RULE_CODE_ERROR"
                return {"status": "failed", "error": {"code": code, "message": str(error["message"])[:1000],
                        "line": error.get("line") if type(error.get("line")) is int else None,
                        **({"period": error["period"]} if type(error.get("period")) is int else {}),
                        "alias": error.get("alias", "")[:1000] if isinstance(error.get("alias", ""), str) else ""}, "runtime": runtime}
            except (ValueError, KeyError, TypeError):
                return {"status": "failed", "error": {"code": "RULE_INVALID_OUTPUT", "message": "Salida del sandbox inválida"}}
        finally:
            try:
                self.remove(job_id)
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=15)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()
