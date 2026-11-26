"""Real-time DSP SSE bridge server for MotorLab V9 (Python stdlib only)."""

from __future__ import annotations

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import queue
import random
import threading
import time

HTML_PATH = Path(__file__).with_name("dsp_live.html")


class StateHub:
    """Thread-safe state store and SSE fan-out hub."""

    def __init__(self, max_samples: int = 300) -> None:
        self._lock = threading.Lock()
        self._samples: deque[dict] = deque(maxlen=max_samples)
        self._stage: dict = {
            "filter_name": "En espera de telemetría",
            "phase": "ESPERA",
            "note": "Servidor SSE activo en 127.0.0.1:8090. Esperando muestras o demo.",
        }
        self._results: dict[str, dict] = {}
        self._clients: set[queue.Queue[tuple[str, str]]] = set()
        self._demo_running = False

    def subscribe(self) -> tuple[queue.Queue[tuple[str, str]], dict]:
        q: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=512)
        with self._lock:
            self._clients.add(q)
            snap = {
                "stage": dict(self._stage),
                "samples": list(self._samples),
                "results": list(self._results.values()),
            }
        return q, snap

    def unsubscribe(self, q: queue.Queue[tuple[str, str]]) -> None:
        with self._lock:
            self._clients.discard(q)

    def _broadcast_locked(self, event_type: str, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        for q in list(self._clients):
            try:
                q.put_nowait((event_type, encoded))
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait((event_type, encoded))
                except queue.Empty:
                    pass

    def push_sample(self, sample: dict) -> None:
        with self._lock:
            self._samples.append(sample)
            self._broadcast_locked("sample", sample)

    def set_stage(self, stage: dict) -> None:
        with self._lock:
            self._stage = {
                "filter_name": str(stage.get("filter_name", self._stage["filter_name"])),
                "phase": str(stage.get("phase", self._stage["phase"])).upper(),
                "note": str(stage.get("note", "")),
            }
            self._broadcast_locked("stage", self._stage)

    def upsert_result(self, result: dict) -> None:
        name = str(result.get("filter_name", "Filtro"))
        with self._lock:
            if result.get("winner"):
                for existing in self._results.values():
                    existing["winner"] = False
            self._results[name] = dict(result)
            self._broadcast_locked("result", {"results": list(self._results.values())})

    def reset(self, clear_results: bool = False) -> None:
        with self._lock:
            self._samples.clear()
            if clear_results:
                self._results.clear()
            self._broadcast_locked("reset", {"clear_results": clear_results})

    def trigger_demo(self, duration_s: float = 6.0) -> bool:
        with self._lock:
            if self._demo_running:
                return False
            self._demo_running = True
        thread = threading.Thread(
            target=self._run_demo, args=(duration_s,), daemon=True
        )
        thread.start()
        return True

    def _run_demo(self, duration_s: float) -> None:
        try:
            self.reset(clear_results=False)
            self.set_stage(
                {
                    "filter_name": "DEMO · Median3 + EMA (α=0.30)",
                    "phase": "DEMO",
                    "note": "Ráfaga sintética 6 s: onda senoidal 0.35 Hz + picos impulsivos ±10 mm.",
                }
            )
            rng = random.Random(42)
            win = deque(maxlen=3)
            filt_h = 100.0
            filt_a = 0.0
            dt = 0.05
            steps = max(1, int(duration_s / dt))
            errs: list[float] = []
            noise_est: list[float] = []
            t0 = time.monotonic()
            for i in range(steps):
                t = i * dt
                ref_h = 100.0 + 60.0 * math.sin(2.0 * math.pi * 0.35 * t)
                true_h = 100.0 + 57.0 * math.sin(2.0 * math.pi * 0.35 * (t - 0.12))
                spike = rng.choice((-10.0, 10.0)) if rng.random() < 0.10 else 0.0
                raw_h = true_h + rng.gauss(0.0, 1.4) + spike
                win.append(raw_h)
                med = sorted(win)[len(win) // 2]
                filt_h = 0.30 * med + 0.70 * filt_h
                raw_a = 2.0 * math.sin(2.0 * math.pi * 0.6 * t) + rng.gauss(0.0, 0.35)
                filt_a = 0.70 * raw_a + 0.30 * filt_a
                common = 58.0 + max(-25.0, min(25.0, 0.24 * (ref_h - filt_h)))
                diff = max(-8.0, min(8.0, 0.35 * (-filt_a)))
                self.push_sample(
                    {
                        "t": round(t, 3),
                        "raw_h": round(raw_h, 2),
                        "filt_h": round(filt_h, 2),
                        "ref_h": round(ref_h, 2),
                        "raw_a": round(raw_a, 2),
                        "filt_a": round(filt_a, 2),
                        "pwm_l": round(max(0.0, min(99.0, common - diff)), 2),
                        "pwm_r": round(max(0.0, min(99.0, common + diff)), 2),
                    }
                )
                errs.append(filt_h - ref_h)
                noise_est.append(filt_h - true_h)
                target_time = t0 + (i + 1) * dt
                sleep_s = target_time - time.monotonic()
                if sleep_s > 0:
                    time.sleep(sleep_s)

            mean_n = sum(noise_est) / len(noise_est)
            std_mm = math.sqrt(sum((x - mean_n) ** 2 for x in noise_est) / len(noise_est))
            p2p_mm = max(noise_est) - min(noise_est)
            rmse_mm = math.sqrt(sum(e * e for e in errs) / len(errs))
            self.upsert_result(
                {
                    "filter_name": "DEMO · Median3+EMA",
                    "order": 1,
                    "fc_hz": 1.36,
                    "std_mm": round(std_mm, 3),
                    "p2p_mm": round(p2p_mm, 3),
                    "lag_ms": 120.0,
                    "rmse_mm": round(rmse_mm, 3),
                    "smoothness_score": round(max(0.0, 100.0 - std_mm * 12.0), 1),
                    "winner": True,
                }
            )
            self.set_stage(
                {
                    "filter_name": "DEMO · Median3 + EMA (α=0.30)",
                    "phase": "COMPLETADO",
                    "note": "Demo finalizada. Listo para telemetría real del ESP32.",
                }
            )
        finally:
            with self._lock:
                self._demo_running = False


HUB = StateHub(max_samples=300)


class DspRequestHandler(BaseHTTPRequestHandler):
    """HTTP + SSE handler for the live DSP dashboard."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/dsp_live.html"):
            if not HTML_PATH.exists():
                self._send_json(404, {"error": "dsp_live.html not found"})
                return
            body = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/events":
            q, snapshot = HUB.subscribe()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                snap_json = json.dumps(snapshot, ensure_ascii=False)
                self.wfile.write(f"event: snapshot\ndata: {snap_json}\n\n".encode("utf-8"))
                self.wfile.flush()
                while True:
                    try:
                        ev, data = q.get(timeout=15.0)
                        self.wfile.write(f"event: {ev}\ndata: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                HUB.unsubscribe(q)
            return

        self._send_json(404, {"error": f"Unknown GET path: {path}"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            payload = self._read_json()
        except Exception as exc:
            self._send_json(400, {"error": f"Invalid JSON: {exc}"})
            return

        if path == "/api/sample":
            HUB.push_sample(payload)
            self._send_json(200, {"ok": True})
        elif path == "/api/stage":
            HUB.set_stage(payload)
            self._send_json(200, {"ok": True})
        elif path == "/api/result":
            HUB.upsert_result(payload)
            self._send_json(200, {"ok": True})
        elif path == "/api/reset":
            HUB.reset(clear_results=bool(payload.get("clear_results", False)))
            self._send_json(200, {"ok": True})
        elif path == "/api/demo":
            duration_s = float(payload.get("duration_s", 6.0))
            started = HUB.trigger_demo(duration_s=max(1.0, min(30.0, duration_s)))
            self._send_json(200, {"ok": True, "started": started})
        else:
            self._send_json(404, {"error": f"Unknown POST path: {path}"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Live DSP SSE server for MotorLab V9")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--demo", action="store_true", help="Run a 6 s synthetic demo on startup")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DspRequestHandler)
    if args.demo:
        threading.Timer(0.5, lambda: HUB.trigger_demo(6.0)).start()
    print(f"DSP Live SSE server listening on http://{args.host}:{args.port}/dsp_live.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
