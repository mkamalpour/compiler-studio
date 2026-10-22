"""Process isolation keeps editable regular expressions off the GUI thread."""

import multiprocessing as mp
from queue import Empty
import time

TIMEOUT = 12


def _work(queue, source, profile_data, mode):
    try:
        from .engine import analyze
        from .profiles import Profile
        queue.put(analyze(source, Profile.from_dict(profile_data), mode))
    except Exception as exc:
        queue.put(f"{type(exc).__name__}: {exc}")


class Job:
    def __init__(self, source, profile, mode, timeout=TIMEOUT):
        context = mp.get_context("spawn")
        self.queue = context.Queue()
        self.process = context.Process(target=_work, args=(self.queue, source, profile.to_dict(), mode), daemon=True)
        self.started = time.monotonic()
        self.timeout = timeout
        self.process.start()

    def poll(self):
        try:
            result = self.queue.get_nowait()
        except Empty:
            if time.monotonic() - self.started > self.timeout:
                self.close()
                raise TimeoutError("Analysis timed out. Simplify the source, grammar or regex patterns.")
            if not self.process.is_alive():
                self.close()
                raise RuntimeError("Analysis worker exited without a result.")
            return None
        self.close()
        if isinstance(result, str):
            raise RuntimeError(result)
        return result

    def close(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=0.5)
        self.queue.close()


def run_isolated(source, profile, mode="pipeline", timeout=TIMEOUT):
    job = Job(source, profile, mode, timeout)
    try:
        while True:
            result = job.poll()
            if result is not None:
                return result
            time.sleep(0.02)
    finally:
        if job.process.is_alive():
            job.close()
