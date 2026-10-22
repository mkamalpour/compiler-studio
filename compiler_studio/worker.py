"""Reusable process isolation, parser caching, cancellation and hard timeouts."""

import multiprocessing as mp
from queue import Empty
import time

TIMEOUT = 12


def _serve(requests, responses):
    from .engine import analyze
    from .profiles import Profile
    while True:
        request_id, source, profile_data, mode = requests.get()
        try:
            result = analyze(source, Profile.from_dict(profile_data), mode)
        except Exception as exc:
            result = f"{type(exc).__name__}: {exc}"
        responses.put((request_id, result))
        del source, profile_data, result


class AnalysisWorker:
    """Keep the parser cache between jobs; discard the process on cancellation."""

    def __init__(self):
        self.process = None
        self.requests = None
        self.responses = None
        self.active = None
        self.serial = 0

    def submit(self, source, profile, mode="pipeline", timeout=TIMEOUT):
        if self.active is not None:
            raise RuntimeError("Cancel the active analysis before starting another.")
        if self.process is None or not self.process.is_alive():
            self.close()
            context = mp.get_context("spawn")
            self.requests, self.responses = context.Queue(), context.Queue()
            self.process = context.Process(target=_serve, args=(self.requests, self.responses), daemon=True)
            self.process.start()
        self.serial += 1
        job = RunningJob(self, self.serial, timeout)
        self.active = job
        self.requests.put((job.request_id, source, profile.to_dict(), mode))
        return job

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=0.5)
        for queue in (self.requests, self.responses):
            if queue is not None:
                queue.cancel_join_thread()
                queue.close()
        self.process = self.requests = self.responses = self.active = None


class RunningJob:
    def __init__(self, owner, request_id, timeout):
        self.owner = owner
        self.request_id = request_id
        self.started = time.monotonic()
        self.timeout = timeout
        self.process = owner.process
        self.completed = False

    def poll(self):
        if self.completed or self.owner.active is not self:
            raise RuntimeError("This analysis job is no longer active.")
        try:
            request_id, result = self.owner.responses.get_nowait()
        except Empty:
            if time.monotonic() - self.started > self.timeout:
                self.close()
                raise TimeoutError("Analysis timed out. Simplify the source, grammar or regex patterns.")
            if not self.process.is_alive():
                self.close()
                raise RuntimeError("Analysis worker exited without a result. Check the Python dependencies.")
            return None
        if request_id != self.request_id:
            self.close()
            raise RuntimeError("Unexpected analysis response; worker restarted.")
        self.completed = True
        self.owner.active = None
        if isinstance(result, str):
            self.owner.close()
            raise RuntimeError(result)
        return result

    def close(self):
        if self.owner.active is self:
            self.owner.close()


class Job(RunningJob):
    """Single-use interface retained for CLI and external callers."""

    def __init__(self, source, profile, mode, timeout=TIMEOUT):
        owner = AnalysisWorker()
        handle = owner.submit(source, profile, mode, timeout)
        self.__dict__.update(handle.__dict__)
        owner.active = self

    def poll(self):
        try:
            result = super().poll()
        except Exception:
            self.owner.close()
            raise
        if result is not None:
            self.owner.close()
        return result

    def close(self):
        self.owner.close()


def run_isolated(source, profile, mode="pipeline", timeout=TIMEOUT):
    job = Job(source, profile, mode, timeout)
    try:
        while True:
            result = job.poll()
            if result is not None:
                return result
            time.sleep(0.02)
    finally:
        job.close()
