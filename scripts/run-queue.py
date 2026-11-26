#!/usr/bin/env python3
"""Run long trainings on the GPU workstation, one queue per GPU, and tell the phone how they go.

    run-queue add QUEUE NAME [options] -- command [args...]   a run at the end of a queue
    run-queue list                                             the queues and their runs
    run-queue remove NAME                                      a run that has not started, out of its queue
    run-queue retry NAME [--resume]                            a failed run, back at the front of its queue
    run-queue cancel NAME                                      end the run that is running, and hold its queue
    run-queue hold QUEUE                                       start nothing there until it is released
    run-queue release QUEUE                                    start runs there again
    run-queue watch NAME [--gpu QUEUE] [options] -- command    run a command now, in this terminal, watched
    run-queue serve QUEUE                                      what the queue's service runs

A queue is named after its GPU's model, as nvidia-smi names it: 5080 or 4070. Its systemd user
service, run-queue@QUEUE, runs its runs one after another without a session. A run that ends with
an error holds its queue. A training that was interrupted, by a stop, a reboot or a power cut,
resumes from its last checkpoint with --c when its queue starts again, up to three times.

The runs are watched from outside: the command writes its output to a log, and this script reads
it, takes the numbers from nnU-Net's lines and sends notices through ntfy, with the values of
~/.config/research-platform/ntfy.env, the file that notify reads (ADR-014). A notice carries the
run's name, a status, numbers and the GPU's model, never paths, study identifiers or patient
data, so a failure names only the class of the error. Next to the log, platform.json records what
only the platform knows: this repository's commit, the GPU and its power limit, and each start,
interruption, resume and end of the run (docs/guides/operate-long-runs.md).

It uses only Python's standard library, so it runs with Ubuntu's python3.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import queue as queue_module
import re
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PROGRAM = "run-queue"
MAX_RESUMES = 3
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}")
QUEUE_NAME = re.compile(r"[A-Za-z0-9]{1,20}")
STATES = ("pending", "running", "done", "failed")
# nnU-Net 2.8.1 prints its own lines after a timestamp (nnUNetTrainer.print_to_log_file).
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d+)?: ")
# A number that is not part of a name, so that np.float32(0.108) gives 0.108 and not 32.
NUMBER = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
# The last line of a traceback starts with the error's class, dotted or not.
ERROR_CLASS = re.compile(r"^((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)(?::|$)")
# Variables of the session that a run must not take with it into its queue's service.
SESSION_VARIABLE = re.compile(
    r"^(SSH_\w*|XDG_SESSION_\w*|XDG_SEAT|XDG_VTNR|DBUS_\w*|WAYLAND_\w*|DISPLAY|XAUTHORITY|TERM|TERM_\w*|"
    r"COLORTERM|TMUX\w*|STY|WINDOWID|SHLVL|OLDPWD|PWD|_|GPG_AGENT_INFO|SESSION_MANAGER|GNOME_\w*|VTE_\w*|"
    r"DESKTOP_SESSION|INVOCATION_ID|JOURNAL_STREAM|MANAGERPID|NOTIFY_SOCKET|LS_COLORS|CUDA_VISIBLE_DEVICES)$")


def seconds_from_environment(name: str, default: float) -> float:
    """The intervals below, which a test can shorten; a run never needs to."""
    try:
        return float(os.environ.get(f"RUN_QUEUE_{name}", default))
    except ValueError:
        return default


POLL = seconds_from_environment("POLL_SECONDS", 0.5)            # how often the log is read
SAMPLE = seconds_from_environment("SAMPLE_SECONDS", 30)          # how often the GPU is read
IDLE = seconds_from_environment("IDLE_SECONDS", 15)              # how often an idle queue looks for runs
FIRST_EPOCH = seconds_from_environment("FIRST_EPOCH_SECONDS", 3600)  # silence before a first epoch
STALL_FLOOR = seconds_from_environment("STALL_SECONDS", 1200)    # the least silence that counts as a stall


def xdg(variable: str, default: str) -> Path:
    value = os.environ.get(variable)
    return Path(value) if value and os.path.isabs(value) else Path.home() / default


CONFIG = xdg("XDG_CONFIG_HOME", ".config") / "research-platform"
DATA = xdg("XDG_DATA_HOME", ".local/share") / "research-platform"
STATE = xdg("XDG_STATE_HOME", ".local/state") / "research-platform"
QUEUES = DATA / "queues"
COMMIT_FILE = DATA / "installed-commit"


def say(text: str) -> None:
    """A line for the terminal, or for the journal under systemd. Once the terminal is gone, nothing."""
    try:
        print(f"{PROGRAM}: {text}", file=sys.stderr, flush=True)
    except OSError:
        pass


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, value: dict) -> None:
    """Writes the whole file or nothing, readable by its owner only."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


# --- ntfy -------------------------------------------------------------------------------------


def read_config(path: Path) -> dict[str, str] | None:
    """The three values, read as notify reads them: the first line of each, without spaces or quotes."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    values = {}
    for key in ("NTFY_URL", "NTFY_TOPIC", "NTFY_TOKEN"):
        value = next((line[len(key) + 1:] for line in lines if line.startswith(key + "=")), "")
        values[key] = re.sub(r"[\s\"']", "", value)
        if not values[key]:
            return None
    return values


class Sender:
    """Sends the notices one at a time, from a thread of its own, so that reading the log never waits
    for the network. The token goes in a header, never on a command line."""

    def __init__(self, config: dict[str, str]):
        url = config["NTFY_URL"].rstrip("/")
        if "://" not in url:  # curl, which notify uses, takes a bare address as http
            url = "http://" + url
        self.url = url + "/" + config["NTFY_TOPIC"]
        self.token = config["NTFY_TOKEN"]
        self.queue: queue_module.Queue = queue_module.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def send(self, title: str, text: str, priority: str = "default") -> None:
        self.queue.put((title, text, priority))

    def close(self, timeout: float = 60) -> None:
        """Waits for the notices already queued, up to timeout seconds."""
        self.queue.put(None)
        self.thread.join(timeout)

    def _run(self) -> None:
        while (item := self.queue.get()) is not None:
            title, text, priority = item
            error = None
            for attempt in range(3):
                if attempt:
                    time.sleep(2)
                request = urllib.request.Request(self.url, data=text.encode(), method="POST", headers={
                    "Authorization": f"Bearer {self.token}", "Title": title, "Priority": priority})
                try:
                    with urllib.request.urlopen(request, timeout=10):
                        pass
                    error = None
                    break
                except urllib.error.HTTPError as e:
                    error = f"HTTP {e.code}"
                    if e.code in (400, 401, 403):  # a request ntfy refuses does not improve by repeating it
                        break
                except (urllib.error.URLError, OSError) as e:
                    error = str(getattr(e, "reason", e))
                except Exception as e:  # noqa: BLE001 - a notice that cannot be sent must not stop the others
                    error = type(e).__name__
                    break
            say(f"not sent ({error}): {title}" if error else f"sent: {title}")


def open_sender() -> Sender | None:
    config = read_config(CONFIG / "ntfy.env")
    if config is None:
        say(f"NTFY_URL, NTFY_TOPIC and NTFY_TOKEN must be set in {CONFIG / 'ntfy.env'}")
        return None
    return Sender(config)


# --- What nnU-Net's lines say -----------------------------------------------------------------


def number(text: str) -> float | None:
    found = NUMBER.search(text)
    return float(found.group()) if found else None


class Training:
    """What nnU-Net's lines have said so far."""

    def __init__(self, every: int, total: int | None, mode: str = "training"):
        self.every, self.total, self.mode = every, total, mode
        self.epoch: int | None = None  # nnU-Net's index of the epoch that runs, from 0
        self.first: int | None = None  # the index of the first epoch this run saw: a resume starts later
        self.done = 0                  # epochs finished
        self.dice: float | None = None
        self.train_loss: float | None = None
        self.val_loss: float | None = None
        self.times: list[float] = []
        self.best: float | None = None
        self.training_done = False
        self.error: str | None = None
        self.progress = time.monotonic()  # when an epoch last began or ended
        self._due = False                 # an epoch whose notice waits for the epoch's last line
        self._traceback = False

    def read(self, line: str) -> str | None:
        """Takes one line of output; returns "epoch" or "training done" when a notice is due."""
        if line.startswith("Traceback (most recent call last):"):
            self._traceback = True
            return None
        if self._traceback:
            if not line.strip() or line[0] in " \t":
                return None
            self._traceback = False
            found = ERROR_CLASS.match(line)
            self.error = found.group(1)[:60] if found else "an error"
            return None
        stamp = STAMP.match(line)
        if not stamp:
            return None
        text = line[stamp.end():].strip()
        if text.startswith("Epoch time:"):
            if (seconds := number(text[len("Epoch time:"):])) is not None:
                self.times.append(seconds)
            if self.epoch is not None:
                self.done = self.epoch + 1
                self._due = self.every > 0 and self.done % self.every == 0
            self.progress = time.monotonic()
        elif text.startswith("Epoch "):
            due, self._due = self._due, False
            if (index := number(text[len("Epoch "):])) is not None:
                self.epoch = int(index)
                self.done = max(self.done, self.epoch)
                if self.first is None:
                    self.first = self.epoch
            self.progress = time.monotonic()
            return "epoch" if due else None
        elif text.startswith("train_loss"):
            self.train_loss = number(text[len("train_loss"):])
        elif text.startswith("val_loss"):
            self.val_loss = number(text[len("val_loss"):])
        elif text.startswith("Pseudo dice"):
            values = [float(v) for v in NUMBER.findall(text[len("Pseudo dice"):])]
            self.dice = sum(values) / len(values) if values else None
        elif text.startswith("Yayy! New best EMA pseudo Dice:"):
            self.best = number(text[len("Yayy! New best EMA pseudo Dice:"):])
        elif text.startswith("Training done."):
            self._due = False
            self.training_done = True
            return "training done"
        return None

    def stall_limit(self) -> float:
        """How long without a new epoch counts as a stall: an hour before the first, then five times
        a recent epoch, and never less than twenty minutes."""
        if self.epoch is None:
            return FIRST_EPOCH
        recent = (self.times[1:] or self.times)[-10:]
        return max(STALL_FLOOR, 5 * statistics.median(recent)) if recent else FIRST_EPOCH

    def time_left(self) -> str | None:
        """Training time left at the pace of the last epochs; the first carries torch.compile."""
        if not self.total or not self.times:
            return None
        recent = (self.times[1:] or self.times)[-10:]
        seconds = max(0, self.total - self.done) * sum(recent) / len(recent)
        if seconds >= 3600:
            return f"about {seconds / 3600:.1f} h of training left"
        if seconds >= 60:
            return f"about {round(seconds / 60)} min of training left"
        return "less than a minute of training left"

    def where(self) -> str:
        if self.training_done:
            return "after the training, in the final validation"
        if self.epoch is None:
            return "before the first epoch"
        return f"in epoch {self.epoch + 1}" + (f" of {self.total}" if self.total else "")

    def numbers(self) -> str:
        if self.mode != "training":
            return ""
        parts = []
        if self.dice is not None:
            parts.append(f"Pseudo Dice {self.dice:.4f}")
        if self.best is not None:
            parts.append(f"best EMA {self.best:.4f}")
        return ", ".join(parts) + "." if parts else ""


def read_log_tail(log: Path, total: int | None = None, size: int = 1 << 18) -> Training:
    """What the last part of a log says: where an interrupted run was."""
    training = Training(0, total)
    try:
        with open(log, "rb") as f:
            f.seek(max(0, f.seek(0, os.SEEK_END) - size))
            for raw in f.read().split(b"\n"):
                training.read(raw.decode("utf-8", "replace").rstrip("\r"))
    except OSError:
        pass
    return training


# --- The GPU ----------------------------------------------------------------------------------


def nvidia_smi(*arguments: str) -> list[str] | None:
    try:
        result = subprocess.run(["nvidia-smi", *arguments], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class GPU:
    """A GPU named by its model, as nvidia-smi names it, and reached by its UUID, so that nothing
    depends on how the cards are numbered. The UUID never goes in a notice or a record."""

    THERMAL = "clocks_event_reasons.sw_thermal_slowdown,clocks_event_reasons.hw_thermal_slowdown"

    def __init__(self, uuid: str, name: str):
        self.uuid, self.name = uuid, name
        self.short = re.sub(r"^NVIDIA (GeForce )?", "", name)
        self._thermal = True

    @classmethod
    def find(cls, model: str) -> GPU | None:
        lines = nvidia_smi("--query-gpu=uuid,name", "--format=csv,noheader")
        if not lines:
            return None
        found = []
        for line in lines:
            uuid, _, name = line.partition(", ")
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(model)}(?![A-Za-z0-9])", name):
                found.append(cls(uuid, name))
        return found[0] if len(found) == 1 else None

    def power_limit(self) -> float | None:
        lines = nvidia_smi("--query-gpu=power.limit", "--format=csv,noheader,nounits", "-i", self.uuid)
        try:
            return float(lines[0]) if lines else None
        except ValueError:
            return None

    def sample(self) -> tuple[int | None, bool]:
        """The temperature now, and whether the clocks are held back by heat."""
        fields = "temperature.gpu," + self.THERMAL if self._thermal else "temperature.gpu"
        lines = nvidia_smi(f"--query-gpu={fields}", "--format=csv,noheader,nounits", "-i", self.uuid)
        if lines is None and self._thermal:
            self._thermal = False  # a driver that lacks the fields: the temperature alone
            return self.sample()
        if not lines:
            return None, False
        values = [v.strip() for v in lines[0].split(",")]
        try:
            temperature = int(float(values[0]))
        except ValueError:
            temperature = None
        return temperature, any(v == "Active" for v in values[1:])


class Heat:
    """The highest temperature, and whether heat held the clocks back, since the last notice."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.highest: int | None = None
        self.slowed = False

    def add(self, temperature: int | None, slowed: bool) -> None:
        if temperature is not None and (self.highest is None or temperature > self.highest):
            self.highest = temperature
        self.slowed = self.slowed or slowed

    def text(self, gpu: GPU) -> str:
        if self.highest is None:
            return ""
        how = "slowed down by heat" if self.slowed else "no thermal slowdown"
        return f"{gpu.short} up to {self.highest} °C, {how}."


def disk_free(path: Path) -> int:
    while not path.exists() and path != path.parent:
        path = path.parent
    return shutil.disk_usage(path).free


def amount(size: float) -> str:
    return f"{size / 1e12:.1f} TB" if size >= 1e12 else f"{size / 1e9:.0f} GB"


# --- The record next to the log ---------------------------------------------------------------


def installed_commit() -> str:
    try:
        commit = COMMIT_FILE.read_text().split()[0]
    except (OSError, IndexError):
        return "unknown"
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else "unknown"


class Record:
    """platform.json, next to the run's log: what only the platform knows about the run. The project
    records its own environment, and can cite this file."""

    def __init__(self, path: Path, run: str, queue: str | None, program: str):
        self.path = path
        try:
            self.value = read_json(path)
        except (OSError, ValueError):
            self.value = {"format": 1, "run": run, "queue": queue, "program": program, "events": []}

    def last(self) -> dict | None:
        events = self.value.get("events") or []
        return events[-1] if events else None

    def add(self, event: str, **fields) -> dict:
        entry = {"utc": utc_now(), "event": event, **fields}
        self.value.setdefault("events", []).append(entry)
        self.save()
        return entry

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.path, self.value)
        except OSError as e:
            say(f"the record could not be written: {e.strerror}")


def gpu_fields(gpu: GPU | None) -> dict:
    if gpu is None:
        return {"research_platform_commit": installed_commit()}
    return {"research_platform_commit": installed_commit(), "gpu": gpu.name, "power_limit_w": gpu.power_limit()}


# --- Notices ----------------------------------------------------------------------------------


def took(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}h {s % 3600 // 60:02d}m {s % 60:02d}s"


def plain(*parts: str) -> str:
    return " ".join(part for part in parts if part).replace("  ", " ")


def of_total(epoch: int, total: int | None) -> str:
    return f"epoch {epoch}" + (f" of {total}" if total else "")


def epoch_notice(name: str, t: Training, heat: Heat, gpu: GPU | None, free: int) -> tuple[str, str, str]:
    losses = ""
    if t.mode == "training" and t.train_loss is not None and t.val_loss is not None:
        losses = f"Losses: train {t.train_loss:.4f}, val {t.val_loss:.4f}."
    timing = ""
    if t.times:
        left = t.time_left()
        timing = f"Last epoch {t.times[-1]:.1f} s" + (f"; {left}." if left else ".")
    return (f"{name}: {of_total(t.done, t.total)}",
            plain(t.numbers(), losses, timing, heat.text(gpu) if gpu else "", f"{amount(free)} free."), "default")


def done_notice(name: str, t: Training) -> tuple[str, str, str]:
    return (f"{name}: training done",
            plain(f"{t.done} epochs.", t.numbers(), "The final validation comes next, unless the trainer skips it."),
            "default")


def end_notice(name: str, t: Training, how: str, status: int, seconds: float, signal_name: str | None,
               after: str = "") -> tuple[str, str, str]:
    if how == "finished":
        summary = plain(f"{t.done} epochs.", t.numbers()) if t.done else ""
        return f"{name} finished", plain(f"It took {took(seconds)}.", summary), "default"
    if how == "stopped":
        return f"{name} stopped", f"Ended by {signal_name} after {took(seconds)}, {t.where()}.", "high"
    if how == "cancelled":
        return f"{name} cancelled", plain(f"Ended by hand after {took(seconds)}, {t.where()}.", after), "default"
    killed = status < 0
    text = f"{'Killed by ' + signal.Signals(-status).name if killed else f'Exit status {status}'} " \
           f"after {took(seconds)}, {t.where()}."
    if t.error and not killed:
        text += f" Error: {t.error}."
    return f"{name} failed", plain(text, after), "high"


# --- Running one command ----------------------------------------------------------------------


class Stop:
    """A signal that asks this script to stop: it goes on to the run, and the run ends."""

    def __init__(self) -> None:
        self.name: str | None = None
        self.process: subprocess.Popen | None = None
        self.event = threading.Event()
        for each in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(each, self._caught)

    def _caught(self, signum: int, frame) -> None:  # noqa: ARG002 - the signal module's signature
        if self.name is None:
            self.name = signal.Signals(signum).name
        self.event.set()
        self.forward(signum)

    def forward(self, signum: int) -> None:
        if self.process is not None and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signum)
            except OSError:
                pass


def run_command(command: list[str], env: dict[str, str], cwd: str | None, log: Path, name: str,
                training: Training, sender: Sender, gpu: GPU | None, stop: Stop, mirror: bool,
                cancel_file: Path | None = None, on_first_epoch=None) -> tuple[int, bool]:
    """Runs the command with its output in the log, reads the log until the command ends, and sends
    the notices that the log calls for. Returns the command's status, and whether it was cancelled."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        offset = out.tell()
        # A session of its own, so that a signal reaches it only through this script, which then
        # knows why the run ended.
        process = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, env=env, cwd=cwd,
                                   start_new_session=True)
    stop.process = process
    if stop.name is not None:  # a signal that came while the run was starting
        stop.forward(signal.SIGTERM)
    heat, cancelled, stalled = Heat(), False, False
    stalled_at = training.epoch
    sampled = checked = 0.0
    pending = b""

    def take(raw: bytes) -> None:
        nonlocal stalled
        first = training.first
        notice = training.read(raw.decode("utf-8", "replace").rstrip("\r"))
        if first is None and training.first is not None and on_first_epoch is not None:
            on_first_epoch(training.first)
        if notice == "epoch":
            sender.send(*epoch_notice(name, training, heat, gpu, disk_free(log.parent)))
            heat.reset()
        elif notice == "training done":
            sender.send(*done_notice(name, training))
        if stalled and training.epoch is not None and training.epoch != stalled_at:
            stalled = False
            sender.send(f"{name}: advancing again", f"In {of_total(training.epoch + 1, training.total)}.")

    with open(log, "rb") as f:
        f.seek(offset)
        while True:
            ended = process.poll() is not None
            chunk = f.read(1 << 16)
            if chunk:
                if mirror:
                    try:
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.buffer.flush()
                    except OSError:
                        mirror = False
                *lines, pending = (pending + chunk).split(b"\n")
                for raw in lines:
                    take(raw)
            elif ended:
                break
            now = time.monotonic()
            if gpu is not None and now - sampled >= SAMPLE:
                sampled = now
                heat.add(*gpu.sample())
            if now - checked >= 2:
                checked = now
                if cancel_file is not None and not cancelled and cancel_file.exists():
                    if cancel_file.read_text().strip() == name:
                        cancelled = True
                        cancel_file.unlink(missing_ok=True)
                        stop.forward(signal.SIGTERM)
                if (training.mode != "generic" and not training.training_done and not stalled
                        and now - training.progress > training.stall_limit()):
                    stalled, stalled_at = True, training.epoch
                    minutes = round((now - training.progress) / 60)
                    where = f"in {of_total(training.done + 1, training.total)}" if training.epoch is not None \
                        else "before its first epoch"
                    sender.send(f"{name}: no progress", f"No new epoch for {minutes} min, {where}. "
                                "The training still runs: look at its log.", "high")
            if not chunk:
                time.sleep(POLL)
    if pending:
        take(pending)
    status = process.wait()
    stop.process = None
    return status, cancelled


def training_env(env: dict[str, str], gpu: GPU | None) -> dict[str, str]:
    env = {**env, "PYTHONUNBUFFERED": "1"}  # each line reaches the log when nnU-Net prints it
    if gpu is not None:
        env["CUDA_VISIBLE_DEVICES"] = gpu.uuid
    return env


def started_text(program: str, gpu: GPU | None, every: int, total: int | None, mode: str) -> str:
    where = f" on the {gpu.short}" if gpu else ""
    if mode == "generic":
        return f"{program}{where}."
    notices = "no notice per epoch" if every == 0 else \
        "a notice every epoch" if every == 1 else f"a notice every {every} epochs"
    planned = f", {total} epochs planned" if total else ""
    progress = ", progress only" if mode == "progress" else ""
    return f"{program}{where}, with {notices}{progress}{planned}."


# --- Queues -----------------------------------------------------------------------------------


class Queue:
    """A folder per queue, with one file per run in pending, running, done or failed."""

    def __init__(self, name: str):
        self.name = name
        self.dir = QUEUES / name

    def create(self) -> None:
        for state in STATES:
            (self.dir / state).mkdir(mode=0o700, parents=True, exist_ok=True)

    def runs(self, state: str) -> list[Path]:
        return sorted((self.dir / state).glob("*.json"))

    @property
    def held(self) -> str | None:
        try:
            return (self.dir / "held").read_text().strip() or "held"
        except OSError:
            return None

    def hold(self, reason: str) -> None:
        descriptor = os.open(self.dir / "held", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as f:
            f.write(reason + "\n")

    def release(self) -> None:
        (self.dir / "held").unlink(missing_ok=True)

    def move(self, path: Path, state: str) -> Path:
        target = self.dir / state / path.name
        os.replace(path, target)
        return target


def all_queues() -> list[Queue]:
    if not QUEUES.is_dir():
        return []
    return [Queue(p.name) for p in sorted(QUEUES.iterdir()) if p.is_dir()]


def run_name(path: Path) -> str:
    return path.stem.split("-", 1)[1]


def find_run(name: str) -> tuple[Queue, str, Path] | None:
    for q in all_queues():
        for state in STATES:
            for path in q.runs(state):
                if run_name(path) == name:
                    return q, state, path
    return None


def service_active(queue: str) -> bool:
    try:
        result = subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"run-queue@{queue}"],
                                timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def progress_of(job: dict) -> str:
    t = read_log_tail(Path(job["log"]), job.get("epochs"))
    if t.epoch is None:
        return ""
    return f", {t.where()}"


# --- Commands ---------------------------------------------------------------------------------


def split_command(argv: list[str], parser: argparse.ArgumentParser) -> tuple[list[str], list[str]]:
    if "--" not in argv:
        parser.error("the command goes after --")
    split = argv.index("--")
    command = argv[split + 1:]
    if not command:
        parser.error("no command after --")
    return argv[:split], command


def check_name(name: str, parser: argparse.ArgumentParser) -> None:
    if not NAME.fullmatch(name):
        parser.error("NAME takes letters, digits, dots, dashes and underscores, up to 40, and starts with a "
                     "letter or a digit: it goes in every notice and in file names, and a path must not")


def add_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--epochs", type=int, help="the epochs the training will run, for the time left")
    parser.add_argument("--every", type=int, default=50,
                        help="a notice every N epochs (default 50, when nnU-Net saves checkpoint_latest; 0, none)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--progress-only", action="store_true",
                      help="notices without the pseudo Dice or the losses: only how far the training is")
    mode.add_argument("--generic", action="store_true",
                      help="a job that is not an nnU-Net training: a notice when it starts and when it ends")
    parser.add_argument("--log", type=Path, help="where the command's output goes; platform.json goes next to it")


def mode_of(args: argparse.Namespace) -> str:
    return "generic" if args.generic else "progress" if args.progress_only else "training"


def check_run_options(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.every < 0 or (args.epochs is not None and args.epochs < 1):
        parser.error("--every takes a whole number from 0, and --epochs one from 1")


def cmd_add(args: argparse.Namespace, command: list[str], parser: argparse.ArgumentParser) -> int:
    if not QUEUE_NAME.fullmatch(args.queue):
        parser.error("QUEUE is the GPU's model, as nvidia-smi names it: 5080 or 4070")
    check_name(args.name, parser)
    check_run_options(args, parser)
    gpu = GPU.find(args.queue)
    if gpu is None:
        say(f"nvidia-smi lists no single GPU named {args.queue}")
        return 1
    if find_run(args.name):
        say(f"a run named {args.name} is already in a queue: a run's name is its own")
        return 1
    env = {k: v for k, v in os.environ.items() if not SESSION_VARIABLE.match(k)}
    if shutil.which(command[0], path=env.get("PATH")) is None:
        say(f"{command[0]} is not a command that this environment can run")
        return 1
    log = (args.log or STATE / "runs" / args.name / "output.log").expanduser().absolute()
    record = log.parent / "platform.json"
    if record.exists():
        try:
            other = read_json(record).get("run")
        except (OSError, ValueError):
            other = None
        if other != args.name:
            say(f"{record} belongs to another run: give this one a folder of its own with --log")
            return 1
    q = Queue(args.queue)
    q.create()
    log.parent.mkdir(parents=True, exist_ok=True)
    job = {"format": 1, "name": args.name, "queue": args.queue, "command": command, "cwd": os.getcwd(),
           "env": env, "epochs": args.epochs, "every": args.every, "mode": mode_of(args), "log": str(log),
           "min_free_gb": args.min_free_gb, "resumes": 0, "added_utc": utc_now()}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(q.dir / "pending" / f"{stamp}-{args.name}.json", job)
    ahead = len(q.runs("running")) + len(q.runs("pending")) - 1
    print(f"{args.name} waits in queue {args.queue}, the {gpu.short}, behind {ahead} other run(s); its log: {log}")
    if q.held:
        print(f"queue {args.queue} holds ({q.held}): run-queue release {args.queue} lets it start")
    if not service_active(args.queue):
        print(f"queue {args.queue}'s service is not running: systemctl --user start run-queue@{args.queue}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:  # noqa: ARG001 - every command takes its arguments
    queues = all_queues()
    if not queues:
        print("no queues yet: run-queue add QUEUE NAME -- command")
        return 0
    for q in queues:
        running = q.runs("running")
        state = f"holds ({q.held})" if q.held else "running" if running else "idle"
        if not service_active(q.name):
            state += ", its service is not running"
        print(f"queue {q.name}: {state}")
        for status in ("running", "pending", "failed"):
            for path in q.runs(status):
                job = read_json(path)
                extra = progress_of(job) if status == "running" else ""
                resumes = f", resumed {job['resumes']} time(s)" if job.get("resumes") else ""
                print(f"  {status:8} {job['name']}{extra}{resumes}")
        if done := q.runs("done"):
            print(f"  done     {len(done)} run(s), the last {run_name(done[-1])}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    found = find_run(args.name)
    if not found or found[1] != "pending":
        say(f"no run named {args.name} waits in a queue" + (f": it is {found[1]}" if found else ""))
        return 1
    found[2].unlink()
    print(f"{args.name} left queue {found[0].name}")
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    found = find_run(args.name)
    if not found or found[1] != "failed":
        say(f"no run named {args.name} has failed" + (f": it is {found[1]}" if found else ""))
        return 1
    q, _, path = found
    job = read_json(path)
    job["resumes"] = 0
    job["resume_next"] = args.resume
    write_json(path, job)
    q.move(path, "pending")
    how = "from its last checkpoint, with --c" if args.resume else "from the start, as it was added"
    print(f"{args.name} is first in queue {q.name} again, and starts {how}")
    if q.held and args.name in q.held.split():
        q.release()
        print(f"queue {q.name} no longer holds")
    elif q.held:
        print(f"queue {q.name} still holds ({q.held}): run-queue release {q.name}")
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    found = find_run(args.name)
    if not found or found[1] != "running":
        say(f"no run named {args.name} is running" + (f": it is {found[1]}" + (
            f"; run-queue remove {args.name} takes it out" if found[1] == "pending" else "") if found else ""))
        return 1
    q = found[0]
    descriptor = os.open(q.dir / "cancel", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as f:
        f.write(args.name + "\n")
    print(f"queue {q.name} ends {args.name} within seconds, and then holds; "
          f"run-queue retry {args.name} puts it back")
    return 0


def cmd_hold(args: argparse.Namespace) -> int:
    q = Queue(args.queue)
    if not q.dir.is_dir():
        say(f"there is no queue {args.queue}")
        return 1
    q.hold("by hand")
    print(f"queue {args.queue} starts nothing until run-queue release {args.queue}; a run already running goes on")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    q = Queue(args.queue)
    if not q.held:
        print(f"queue {args.queue} does not hold")
        return 0
    q.release()
    print(f"queue {args.queue} starts runs again")
    return 0


def cmd_watch(args: argparse.Namespace, command: list[str], parser: argparse.ArgumentParser) -> int:
    check_name(args.name, parser)
    check_run_options(args, parser)
    gpu = None
    if args.gpu:
        gpu = GPU.find(args.gpu)
        if gpu is None:
            say(f"nvidia-smi lists no single GPU named {args.gpu}")
            return 1
    sender = open_sender()
    if sender is None:
        return 2
    utc = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log = (args.log or STATE / "runs" / f"{args.name}-{utc}" / "output.log").expanduser().absolute()
    program = os.path.basename(command[0])
    mode = mode_of(args)
    record = Record(log.parent / "platform.json", args.name, None, program)
    stop = Stop()
    training = Training(args.every, args.epochs, mode)
    sender.send(f"{args.name} started", started_text(program, gpu, args.every, args.epochs, mode))
    say(f"the output of {program} goes to {log}")
    start = time.monotonic()
    record.add("started", **gpu_fields(gpu))
    try:
        status, _ = run_command(command, training_env(dict(os.environ), gpu), None, log, args.name, training,
                                sender, gpu, stop, mirror=True)
    except OSError as e:
        say(f"{program} did not start: {e.strerror}")
        record.add("ended", how="failed", status=127, error=type(e).__name__)
        sender.send(f"{args.name} failed", f"{program} did not start: {type(e).__name__}.", "high")
        sender.close()
        return 127
    how = "finished" if status == 0 else "stopped" if stop.name else "failed"
    record.add("ended", how=how, status=status, epochs_done=training.done,
               **({"error": training.error} if training.error and how == "failed" else {}))
    sender.send(*end_notice(args.name, training, how, status, time.monotonic() - start, stop.name))
    sender.close()
    return 128 - status if status < 0 else status


# --- The service of a queue -------------------------------------------------------------------


class Server:
    """Runs a queue's runs one after another, for its service."""

    def __init__(self, q: Queue, sender: Sender, stop: Stop):
        self.q, self.sender, self.stop = q, sender, stop
        self.gpu: GPU | None = None

    def wait_for_gpu(self) -> bool:
        told = False
        while not self.stop.event.is_set():
            self.gpu = GPU.find(self.q.name)
            if self.gpu is not None:
                return True
            if not told:
                told = True
                say(f"nvidia-smi lists no single GPU named {self.q.name}; looking again every minute")
                self.sender.send(f"Queue {self.q.name} has no GPU", f"nvidia-smi lists no single GPU named "
                                 f"{self.q.name}. The queue waits, and looks again every minute.", "high")
            self.stop.event.wait(60)
        return False

    def fail(self, path: Path, job: dict, reason: str, title: str, text: str) -> None:
        self.q.move(path, "failed")
        self.q.hold(f"{reason} {job['name']}")
        self.sender.send(title, plain(text, self.hold_text(job["name"])), "high")

    def hold_text(self, name: str) -> str:
        return (f"Queue {self.q.name} holds: run-queue retry {name} runs it again, "
                f"or run-queue release {self.q.name} goes on with the next run.")

    def next_run(self) -> Path | None:
        if self.q.held:
            return None
        running = self.q.runs("running")
        if running:
            return running[0]
        pending = self.q.runs("pending")
        return pending[0] if pending else None

    def serve(self) -> int:
        if not self.wait_for_gpu():
            return 0
        say(f"queue {self.q.name}: the {self.gpu.short}, waiting for runs")
        busy = False
        while not self.stop.event.is_set():
            path = self.next_run()
            if path is None:
                if busy and not self.q.held and not self.q.runs("pending"):
                    self.sender.send(f"Queue {self.q.name} is empty", f"No run waits on the {self.gpu.short}.")
                busy = False
                self.stop.event.wait(IDLE)
                continue
            busy = True
            try:
                if self.run(path) == "interrupted":
                    break
            except Exception as e:  # noqa: BLE001 - a broken run file must not stop the queue for good
                say(f"{path.name}: {type(e).__name__}: {e}")
                if path.exists():
                    self.q.move(path, "failed")
                self.q.hold(f"broken {run_name(path)}")
                self.sender.send(f"Queue {self.q.name} holds", f"The file of {run_name(path)} could not be "
                                 f"run ({type(e).__name__}). {self.hold_text(run_name(path))}", "high")
        return 0

    def run(self, path: Path) -> str:
        job = read_json(path)
        name, mode, total = job["name"], job.get("mode", "training"), job.get("epochs")
        log = Path(job["log"])
        program = os.path.basename(job["command"][0])
        record = Record(log.parent / "platform.json", name, self.q.name, program)
        interrupted = path.parent.name == "running"
        resuming = interrupted or job.get("resume_next", False)
        if interrupted:
            last = record.last()
            if last and last["event"] == "ended":  # it ended, and the power went before its file moved
                self.q.move(path, "done" if last.get("how") == "finished" else "failed")
                if last.get("how") != "finished":
                    self.q.hold(f"failed {name}")
                return last.get("how", "failed")
            where = read_log_tail(log, total)
            if not (last and last["event"] == "interrupted"):
                try:
                    stopped = datetime.fromtimestamp(log.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                except OSError:
                    stopped = None
                record.add("interrupted", epochs_done=where.done, last_output_utc=stopped, clean=False)
            if mode == "generic":
                self.fail(path, job, "interrupted", f"{name} interrupted",
                          f"{name} was interrupted, and a job that is not a training does not resume by itself.")
                return "failed"
            if job.get("resumes", 0) >= MAX_RESUMES:
                self.fail(path, job, "failed", f"{name} failed",
                          f"Interrupted {MAX_RESUMES + 1} times, {where.where()}: it does not resume again.")
                return "failed"
        needed = job.get("min_free_gb", 50) * 1e9
        free = disk_free(log.parent)
        if free < needed:
            self.q.hold(f"disk {name}")
            self.sender.send(f"Queue {self.q.name} holds", f"{name} needs {amount(needed)} free to start, and "
                             f"the disk has {amount(free)}. run-queue release {self.q.name} tries again.", "high")
            return "held"
        command = list(job["command"])
        if resuming:
            job["resumes"] = job.get("resumes", 0) + 1
            if "--c" not in command:
                command.append("--c")
        job.pop("resume_next", None)
        write_json(path, job)
        if path.parent.name == "pending":
            path = self.q.move(path, "running")
        training = Training(job.get("every", 50), total, mode)
        resumed: dict | None = None
        if resuming:
            last = record.last() or {}
            at = last.get("epochs_done") if last.get("event") == "interrupted" else None
            if isinstance(at, int):
                after = f"After an interruption in epoch {at + 1}" + (f" of {total}" if total else "")
            else:
                after = {"failed": "After it failed", "cancelled": "After it was cancelled"}.get(
                    last.get("how"), "After it ended")
            resumed = record.add("resumed", resume=job["resumes"], **gpu_fields(self.gpu))
            self.sender.send(f"{name} resumed", f"{after}, from its last checkpoint, on the {self.gpu.short} "
                             f"(resume {job['resumes']} of {MAX_RESUMES}).")
        else:
            record.add("started", **gpu_fields(self.gpu))
            self.sender.send(f"{name} started", started_text(program, self.gpu, training.every, total, mode))

        def first_epoch(index: int) -> None:
            if resumed is not None:  # where the resume went on from: the epochs its checkpoint had done
                resumed["epochs_done"] = index
                record.save()

        cancel_file = self.q.dir / "cancel"
        try:
            if cancel_file.read_text().strip() != name:  # a request for a run that is no longer running
                cancel_file.unlink(missing_ok=True)
        except OSError:
            pass
        start = time.monotonic()
        try:
            status, cancelled = run_command(command, training_env(job["env"], self.gpu), job.get("cwd"), log,
                                            name, training, self.sender, self.gpu, self.stop, mirror=False,
                                            cancel_file=cancel_file, on_first_epoch=first_epoch)
        except OSError as e:
            record.add("ended", how="failed", status=127, error=type(e).__name__)
            self.fail(path, job, "failed", f"{name} failed", f"{program} did not start: {type(e).__name__}.")
            return "failed"
        seconds = time.monotonic() - start
        if cancelled:
            record.add("ended", how="cancelled", status=status, epochs_done=training.done)
            self.q.move(path, "failed")
            self.q.hold(f"cancelled {name}")
            self.sender.send(*end_notice(name, training, "cancelled", status, seconds, None,
                                         self.hold_text(name)))
            return "cancelled"
        if status == 0:
            record.add("ended", how="finished", status=0, epochs_done=training.done)
            self.q.move(path, "done")
            self.sender.send(*end_notice(name, training, "finished", 0, seconds, None))
            return "finished"
        if self.stop.name:
            record.add("interrupted", epochs_done=training.done, signal=self.stop.name, clean=True)
            self.sender.send(f"{name} interrupted", f"Stopped {training.where()} by {self.stop.name}. It resumes "
                             f"from its last checkpoint when queue {self.q.name} starts again.")
            return "interrupted"
        record.add("ended", how="failed", status=status, epochs_done=training.done,
                   **({"error": training.error} if training.error else {}))
        self.q.move(path, "failed")
        self.q.hold(f"failed {name}")
        self.sender.send(*end_notice(name, training, "failed", status, seconds, None, self.hold_text(name)))
        return "failed"

def cmd_serve(args: argparse.Namespace) -> int:
    if not QUEUE_NAME.fullmatch(args.queue):
        say("QUEUE is the GPU's model, as nvidia-smi names it: 5080 or 4070")
        return 2
    q = Queue(args.queue)
    q.create()
    lock = open(q.dir / "lock", "w")  # noqa: SIM115 - held for as long as the queue is served
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        say(f"queue {args.queue} is served already: systemctl --user status run-queue@{args.queue}")
        return 1
    sender = open_sender()
    if sender is None:
        return 2
    stop = Stop()
    try:
        return Server(q, sender, stop).serve()
    finally:
        sender.close()


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str], argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="action", required=True, metavar="ACTION")

    add = commands.add_parser("add", help="put a run at the end of a queue",
                              usage="%(prog)s QUEUE NAME [options] -- command [args...]")
    add.add_argument("queue", help="the GPU's model, as nvidia-smi names it: 5080 or 4070")
    add.add_argument("name", help="the run's name in every notice: letters, digits, dots, dashes, underscores")
    add_run_options(add)
    add.add_argument("--min-free-gb", type=float, default=50,
                     help="the free disk the run needs to start (default 50 GB)")

    commands.add_parser("list", help="the queues and their runs")
    for action, text in (("remove", "take a run that has not started out of its queue"),
                         ("cancel", "end the run that is running, and hold its queue")):
        commands.add_parser(action, help=text).add_argument("name")
    retry = commands.add_parser("retry", help="put a failed run back at the front of its queue")
    retry.add_argument("name")
    retry.add_argument("--resume", action="store_true", help="from its last checkpoint, with --c")
    for action, text in (("hold", "start nothing in a queue until it is released"),
                         ("release", "start runs in a queue again"),
                         ("serve", "run a queue's runs, as its service does")):
        commands.add_parser(action, help=text).add_argument("queue")

    watch = commands.add_parser("watch", help="run a command now, in this terminal, watched",
                                usage="%(prog)s NAME [--gpu QUEUE] [options] -- command [args...]")
    watch.add_argument("name", help="the run's name in every notice")
    watch.add_argument("--gpu", help="the GPU to run on, by its model: 5080 or 4070")
    add_run_options(watch)

    action = next((a for a in argv if not a.startswith("-")), None)
    command: list[str] = []
    asks_for_help = "--" not in argv and ("-h" in argv or "--help" in argv)
    if action in ("add", "watch") and not asks_for_help:
        argv, command = split_command(argv, commands.choices[action])
    return parser.parse_args(argv), command, commands.choices.get(action, parser)


def main(argv: list[str] | None = None) -> int:
    args, command, parser = parse(sys.argv[1:] if argv is None else argv)
    if args.action == "add":
        return cmd_add(args, command, parser)
    if args.action == "watch":
        return cmd_watch(args, command, parser)
    return {"list": cmd_list, "remove": cmd_remove, "retry": cmd_retry, "cancel": cmd_cancel,
            "hold": cmd_hold, "release": cmd_release, "serve": cmd_serve}[args.action](args)


if __name__ == "__main__":
    sys.exit(main())
