# Validate the GPU workstation before it trains for real

> **Scope:** the GPU workstation once
> [install-ubuntu-gpu-workstation.md](install-ubuntu-gpu-workstation.md) is done:
> Ubuntu Desktop on its internal SSD, the 580 driver loaded, both GPUs visible.
> Nothing here changes the installation. The only changes are packages; uv,
> whose installer puts it in `~/.local/bin`, adds that folder to the shell's
> startup files, and keeps its cache in `~/.cache`; files under `~/bench`; and
> GPU power limits that last until the next restart.

> **Status:** run on 2026-10-22, sections 1 to 9 and 11. Section 10 waits for a
> plug-in energy meter. That run's memory stress covered 5 GiB, not 40, because
> of how Ubuntu 24.04's stress-ng counts `--vm-bytes`; section 3 now asks for
> 40 GiB in total, and the repeat over 40 GiB passed. Revised from that run on
> 2026-10-23: the summary script, the order of the windows in each run, the
> power sweep, the extra runs that keep the RTX 5080 busy in section 9, and
> the log searches.

This guide answers four questions before any project depends on the machine:

- Are the CPU, the memory and the SSD stable? Faults there look like software
  bugs later: a loss that turns into NaN, a crash after hours, a corrupted file.
- What does each GPU deliver with nnU-Net ResEnc M, and are the 12 GB of the RTX
  4070 enough?
- Where is each GPU's power sweet spot, and what does the whole PC draw from the
  wall?
- Do two trainings at once add up, and does the machine hold them for hours?

How to follow it:

- Run the sections in order; each ends with a **Check:**.
- Copy the results sheet (section 12) into your private note and fill it as you
  go. The tools print identifiers that never enter this repository: GPU UUIDs,
  serial numbers, and the hostname, which nnU-Net writes into its benchmark
  files. The appendix prints them all at once, for the note.
- Commands carry no identifiers to replace. Section 6 writes each GPU's
  identifier into `~/bench/nnunet/env.sh`, and section 4 finds the Ubuntu SSD
  from the root filesystem. The only values you type are the power limits of
  section 8.
- Measure on a quiet machine: no downloads, no video in the browser, no other
  training.
- Runs go inside tmux (section 7), so that closing a terminal does not stop
  them.
- Before pasting a block that has `sudo` after its first line, run `sudo -v`
  alone and type your password. Ubuntu's terminal shows a pasted block
  highlighted and runs it when you press Enter, but terminals that run each
  line as it arrives let a password prompt take the lines that follow it.

### 1. Tools and folders

```bash
sudo apt install stress-ng memtester smartmontools lm-sensors sysstat fio htop tmux build-essential curl
mkdir -p ~/bench/logs
```

`build-essential` is the C compiler that `torch.compile` needs at runtime; `curl`
fetches uv and the dataset in section 6.

**Check:** the packages are installed.

### 2. Baseline: the machine as it is

Read-only:

```bash
lscpu | grep -E '^(Model name|Thread\(s\) per core|Core\(s\) per socket)'
sudo dmidecode -s baseboard-product-name
sudo dmidecode -s bios-version
sudo dmidecode -s bios-release-date
free -h
sudo dmidecode -t memory | grep -E '^\s+(Size|Type|Speed|Configured Memory Speed|Part Number):' | grep -v 'No Module Installed'
lsblk -d -o NAME,SIZE,MODEL,TRAN
lsb_release -ds; uname -r; mokutil --sb-state
nvidia-smi --query-gpu=name,driver_version,vbios_version,pci.bus_id,memory.total --format=csv
nvidia-smi -q | grep -A3 'BAR1 Memory Usage'
```

How the CPU picks its clocks:

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver                 # amd-pstate-epp
cat /sys/devices/system/cpu/amd_pstate/status                           # active
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor               # powersave
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference  # balance_performance
powerprofilesctl get                                                    # balanced
```

Then leave the machine idle for ten minutes, with only a terminal open, and read
the idle state:

```bash
sensors 2>/dev/null
nvidia-smi --query-gpu=name,temperature.gpu,power.draw,memory.used,pstate --format=csv
```

How to read it:

- *Configured Memory Speed* of 6000 MT/s or similar means the memory runs its
  EXPO profile; 4800 to 5600 MT/s means the JEDEC defaults. EXPO is the most
  frequent cause of memory errors, which makes section 3 matter more.
- With the `amd-pstate-epp` driver in `active` mode, the CPU chooses its own
  clocks, and the `powersave` governor does not hold it back: the *energy
  performance preference* (EPP) sets the bias, and the power profile sets the
  EPP. On this machine, `balanced` showed `balance_performance`, and the cores
  still boosted above 5 GHz under load (`grep MHz /proc/cpuinfo` while section
  3 runs).
- The *BAR1 Memory Usage* total of each GPU close to its memory size means
  Resizable BAR is on.
- In `sensors`, `k10temp` reports the CPU (`Tctl`), each `spd5118` entry one
  memory module, and each `nvme` entry an SSD (`Composite`). `2>/dev/null`
  hides the *I/O error* lines that some SSDs print for temperature thresholds
  they do not report.
- At idle the RTX 5080 holds some memory for the desktop, which runs on it; the
  RTX 4070 should hold almost none.

**Check:** the baseline table of the results sheet is filled.

### 3. CPU and memory stability

Watch the temperatures in a second terminal while the tests run:

```bash
watch -n 5 'sensors 2>/dev/null'
```

The CPU, 30 minutes on all 24 threads, verifying every result:

```bash
cd ~/bench/logs
stress-ng --cpu 24 --cpu-method all --verify --timeout 30m --metrics-brief 2>&1 | tee stress-cpu.log
```

The memory, 60 minutes, 40 GiB in eight workers of 5 GiB, verifying what is
read back. 40 of the 64 GiB leaves room for the desktop, so neither swap nor
systemd-oomd takes part:

```bash
stress-ng --vm 8 --vm-bytes 40g --vm-method all --verify --timeout 60m --metrics-brief 2>&1 | tee stress-vm.log
```

`--vm-bytes` is the total for all the workers: the stress-ng of Ubuntu 24.04
(0.17) divides it among them, although its manual says "per vm worker". While
it runs, `free -h` in another terminal shows about 40 GiB more in use.

Afterwards:

```bash
grep -E 'failed|successful run' ~/bench/logs/stress-*.log                  # failed: 0, and successful run completed, in both
journalctl -k -b | grep -iE 'machine check|hardware error'                 # nothing
journalctl -u systemd-oomd -b --no-pager | grep -i killed                  # nothing
```

The searches are that precise on purpose: every start logs
`MCE: In-kernel MCE decoding enabled.`, and systemd-oomd introduces itself as
the *Out-Of-Memory (OOM) Killer*; neither is an error.

AMD lists 95 °C as the Ryzen 9 7900X's maximum operating temperature, and under
an all-core load the CPU boosts until it reaches it: a `Tctl` of 95 °C is
expected; more than that, or a shutdown, is not.

Optional, overnight: one pass of a dedicated memory tester over the same 40 GiB.
It can take hours; the last line is `Done.` with every test `ok`:

```bash
sudo memtester 40G 1 2>&1 | tee ~/bench/logs/memtester.log
```

**Check:** both stress tests completed with no failure, no machine-check error
was logged, and `Tctl` stayed at or below 95 °C. If anything failed, stop here:
test the memory again without EXPO before blaming anything else.

### 4. The Ubuntu SSD

The disk that holds the root filesystem is the Ubuntu SSD. Its name
(`/dev/nvme…n1`) can change between starts, so `U` is found again each time:

```bash
U=$(lsblk -lnso NAME,TYPE "$(findmnt -n -o SOURCE /)" | awk '$2 == "disk" { print "/dev/" $1 }'); echo "$U"
lsblk -d -o NAME,SIZE,MODEL "$U"          # the Ubuntu SSD's model and size
sudo smartctl -a "$U" | grep -E 'Model Number|Firmware Version|Critical Warning|Temperature:|Available Spare:|Percentage Used|Data Units Written|Media and Data Integrity Errors|Unsafe Shutdowns'
lsblk --discard "$U"                      # DISC-GRAN and DISC-MAX other than 0: TRIM reaches the SSD
systemctl is-enabled fstrim.timer         # enabled: Ubuntu trims once a week
```

*Unsafe Shutdowns* counts, over the SSD's whole life, the times it lost power
without being told to shut down. Note it: after the next normal restart it must
be the same (section 11 checks it).

The PCIe link of every NVMe controller, by model:

```bash
for c in /sys/class/nvme/nvme*; do
  echo "$(basename "$c"): $(cat "$c/model") $(cat "$c/device/current_link_speed") x$(cat "$c/device/current_link_width")"
done
```

A PCIe 4.0 SSD in M2_1, a PCIe 5.0 slot, links at `16.0 GT/s PCIe` x4: Gen4 x4.

Speed. The first two runs only read the raw disk (`--readonly` makes fio refuse
any write); the third writes a 2 GiB file in your home folder and deletes it:

```bash
sudo fio --readonly --name=seqread --filename="$U" --rw=read --bs=1M \
    --direct=1 --ioengine=libaio --iodepth=32 --runtime=30 --time_based
sudo fio --readonly --name=randread --filename="$U" --rw=randread --bs=4k \
    --direct=1 --ioengine=libaio --iodepth=64 --numjobs=4 --group_reporting --runtime=30 --time_based
fio --name=write2g --filename="$HOME/fio.tmp" --size=2G --rw=write --bs=1M \
    --direct=1 --ioengine=libaio --iodepth=16 --unlink=1
sudo smartctl -a "$U" | grep 'Temperature:'     # right after the runs
```

A 2 GiB write fits in the SSD's cache, so its speed is the cache's, not what a
long write sustains.

**Check:** the model and size are the Ubuntu SSD's; Gen4 x4; *Critical Warning*
0x00 and no media errors; the speeds, the temperatures and *Unsafe Shutdowns*
are in the results sheet.

### 5. GPUs, PCIe and power limits, read-only

```bash
nvidia-smi -L
nvidia-smi --query-gpu=name,pci.bus_id,pcie.link.gen.max,pcie.link.gen.hostmax,pcie.link.width.max --format=csv
nvidia-smi -q -d POWER
```

GPUs lower their PCIe link when idle, so the link in use is read under load, in
section 7. With two cards the board runs both GPU slots at x8; the RTX 5080 is a
PCIe 5.0 card and the RTX 4070 a PCIe 4.0 card.

From `nvidia-smi -q -d POWER`, note for each GPU its *Default*, *Min* and *Max
Power Limit*, and the *Current Power Limit*, which equals the default unless it
was changed. Section 8 builds its steps on the default each card reports, not on
the reference value of its model: partner cards ship with their own.

**Check:** both GPUs listed, and the power limits of each are in the results
sheet.

### 6. Training stack and benchmark dataset

uv, from its official installer, at the version these guides were checked with:

```bash
curl -LsSf https://astral.sh/uv/0.13.0/install.sh | sh    # installs uv into ~/.local/bin
```

Open a new terminal, so that `~/.local/bin` is on your `PATH`, then create the
benchmark project, with Python managed by uv and PyTorch from PyTorch's CUDA 13.0
index:

```bash
uv --version      # uv 0.13.0
mkdir -p ~/bench/nnunet && cd ~/bench/nnunet
uv python install 3.12
uv python pin 3.12
cat > pyproject.toml <<'EOF'
[project]
name = "nnunet-bench"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = ["torch==2.14.1", "nnunetv2==2.8.1"]

[tool.uv.sources]
torch = [{ index = "pytorch-cu130", marker = "sys_platform == 'linux'" }]

[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true
EOF
uv sync
```

A check that PyTorch computes on both GPUs and that `torch.compile`, which
nnU-Net turns on by default, builds a kernel on each:

```bash
cat > check_gpus.py <<'EOF'
"""PyTorch sees both GPUs, computes on each, and torch.compile works on each."""
import torch

print("torch", torch.__version__, "| CUDA", torch.version.cuda)
assert torch.cuda.device_count() == 2, "expected 2 GPUs"
f = torch.compile(lambda x: torch.sin(x) + 2 * x)
for i in range(2):
    p = torch.cuda.get_device_properties(i)
    x = torch.randn(4096, 4096, device=f"cuda:{i}")
    (x @ x).sum().item()
    y = torch.randn(1_000_000, device=f"cuda:{i}")
    torch.testing.assert_close(f(y), torch.sin(y) + 2 * y)
    print(f"cuda:{i}  {p.name}  {p.total_memory / 2**30:.1f} GiB  capability {p.major}.{p.minor}: ok")
EOF
uv run python check_gpus.py
```

The nnU-Net folders, kept apart from any project, and each GPU's identifier,
written by `nvidia-smi` itself:

```bash
cat > env.sh <<'EOF'
# nnU-Net folders for the benchmarks. In each new terminal: source ~/bench/nnunet/env.sh
export nnUNet_raw="$HOME/bench/nnunet/data/raw"
export nnUNet_preprocessed="$HOME/bench/nnunet/data/preprocessed"
export nnUNet_results="$HOME/bench/nnunet/data/results"
# nnU-Net's benchmark trainers accept only fold 0: each GPU writes to its own folder,
# and each benchmark leaves its result in this file inside that folder
export RESULTS_5080="$HOME/bench/nnunet/data/bench-5080"
export RESULTS_4070="$HOME/bench/nnunet/data/bench-4070"
export BENCH_JSON="Dataset009_Spleen/nnUNetTrainerBenchmark_5epochs__nnUNetResEncUNetMPlans__3d_fullres/fold_0/benchmark_result.json"
# Data-augmentation processes per training: 8, plus 4 for validation
export nnUNet_n_proc_DA=8
# GPUs by UUID, so that no command depends on how the cards are numbered
EOF
nvidia-smi --query-gpu=name,uuid --format=csv,noheader | awk -F', ' '
  /RTX 5080/ { print "export GPU_5080=" $2 }
  /RTX 4070/ { print "export GPU_4070=" $2 }' >> env.sh
source env.sh
mkdir -p "$nnUNet_raw" "$nnUNet_preprocessed" "$nnUNet_results" "$RESULTS_5080" "$RESULTS_4070" download
echo "RTX 5080: $GPU_5080"; echo "RTX 4070: $GPU_4070"
```

The dataset is *Task09_Spleen* of the Medical Segmentation Decathlon: CT, like
the thesis, 41 training cases, public under CC BY-SA 4.0. MONAI's mirror allows
a command-line download and publishes its MD5 checksum:

```bash
cd ~/bench/nnunet/download
curl -LO https://msd-for-monai.s3-us-west-2.amazonaws.com/Task09_Spleen.tar
md5sum Task09_Spleen.tar      # 410d4a301da4e5b2f6f86ec3ddba524e
tar -xf Task09_Spleen.tar
cd ~/bench/nnunet
uv run nnUNetv2_convert_MSD_dataset -i download/Task09_Spleen
uv run nnUNetv2_plan_and_preprocess -d 9 -pl nnUNetPlannerResEncM -c 3d_fullres --verify_dataset_integrity
```

The plan nnU-Net chose:

```bash
uv run python - <<'EOF'
import json, os
plans = os.path.join(os.environ["nnUNet_preprocessed"], "Dataset009_Spleen", "nnUNetResEncUNetMPlans.json")
c = json.load(open(plans))["configurations"]["3d_fullres"]
print("patch", c["patch_size"], "| batch", c["batch_size"], "| spacing", c["spacing"])
EOF
```

Why this dataset and this plan: ResEnc M is the configuration the thesis uses.
nnU-Net's planner sizes the patch and the batch to fit a memory budget (8 GB in
its own estimate for ResEnc M), so the memory a training takes depends on the
plan, not on the size of the dataset. nnU-Net Revisited measured ResEnc M at
9.1 GB on average across six datasets, and nnU-Net's documentation calls it best
suited for GPUs with 9 to 11 GB. Spleen downloads (1.5 GB) and
preprocesses in minutes. Every nnU-Net epoch is 250 training iterations, so its
duration depends on the patch, the batch and the network, not on how many cases
the dataset has. Repeat sections 7 to 9 with the thesis dataset once it is
converted: two input channels change the plan, and `BENCH_JSON` changes with the
dataset's name.

**Check:** `check_gpus.py` prints `ok` for both GPUs; each GPU's line prints a
`GPU-…` identifier, never an empty value; the MD5 matches; the plan prints a
patch and a batch. If a GPU's line is empty, the card is missing or its name
did not match the pattern: fix that before going on, because every command of
sections 7 to 11 depends on it.

### 7. nnU-Net benchmark, each GPU alone

Two helper scripts. The first logs both GPUs every second and the CPU and memory
every five seconds, under a run name, until Ctrl+C:

```bash
cat > ~/bench/monitor.sh <<'EOF'
#!/usr/bin/env bash
# Usage: ~/bench/monitor.sh <run-name>    Logs into ~/bench/logs until Ctrl+C.
set -u
cd ~/bench/logs
nvidia-smi --query-gpu=timestamp,name,utilization.gpu,memory.used,temperature.gpu,power.draw,power.limit,clocks.sm,pcie.link.gen.gpucurrent,pcie.link.width.current,clocks_event_reasons.active \
    --format=csv,noheader,nounits -l 1 > "gpu-$1.csv" &
GPU_PID=$!
vmstat -n -w 5 > "vmstat-$1.log" &
VM_PID=$!
trap 'kill "$GPU_PID" "$VM_PID" 2>/dev/null; echo "stopped: $1"' EXIT
trap 'exit 130' INT TERM
echo "logging $1, Ctrl+C to stop"
wait
EOF
chmod +x ~/bench/monitor.sh
```

The second summarizes a run. It counts only the samples in which a GPU is at
least 50% busy: the RTX 5080 also draws the desktop, and its idle samples would
dilute the averages. Peaks (memory, temperature, PCIe link) come from every busy
sample, because memory peaks in epoch 0, while `torch.compile` tunes its
kernels. Means (utilization, power) and the clock event reasons leave out the
first 120 busy samples, the warm-up:

```bash
cat > ~/bench/summary.sh <<'EOF'
#!/usr/bin/env bash
# Usage: ~/bench/summary.sh <run-name> [busy seconds of warm-up to leave out, default 120]
# Only samples in which a GPU is at least 50% busy count. Peaks (memory, temperature,
# PCIe link) come from all of them; means and clock event reasons skip the warm-up.
set -u
cd ~/bench/logs
awk -F', ' -v skip="${2:-120}" '
  $3 + 0 >= 50 {
    n[$2]++
    if ($4 + 0 > m[$2]) m[$2] = $4 + 0
    if ($5 + 0 > t[$2]) t[$2] = $5 + 0
    if ($9 + 0 > gen[$2]) gen[$2] = $9 + 0
    if ($10 + 0 > w[$2]) w[$2] = $10 + 0 }
  $3 + 0 >= 50 && n[$2] > skip {
    k[$2]++; u[$2] += $3; p[$2] += $6
    seen[$2, $11]++ }
  END {
    for (g in k) {
      printf "%s: %d busy samples, utilization %.0f%%, power %.0f W, peak memory %d MiB, peak %d C, PCIe Gen%d x%d\n",
             g, k[g], u[g] / k[g], p[g] / k[g], m[g], t[g], gen[g], w[g]
      for (s in seen) { split(s, a, SUBSEP); if (a[1] == g) printf "  clock event reasons %s in %d samples\n", a[2], seen[s] } } }' "gpu-$1.csv"
T=$(awk '/^MemTotal/ { print $2 }' /proc/meminfo)
awk -v T="$T" 'NR > 3 && $1 ~ /^[0-9]+$/ {
    busy = 100 - $15; used = T - $4 - $5 - $6
    if (busy > cb) cb = busy; if (used > mx) mx = used; if ($1 > rq) rq = $1 }
  END { printf "CPU: peak busy %d%%, peak memory in use %.1f GiB, peak run queue %d (24 threads)\n", cb, mx / 1048576, rq }' "vmstat-$1.log"
EOF
chmod +x ~/bench/summary.sh
```

Runs go in tmux, which keeps them alive if the terminal closes. Ctrl+b then c
opens a new window, Ctrl+b then a number moves to that window, Ctrl+b then d
leaves everything running, and `tmux attach -t bench` comes back.

The order matters: the monitor starts first and stops last, so that it records
the whole run. For the RTX 5080:

1. `tmux new -A -s bench` opens window 0 of a session named bench (or returns
   to it, if it exists). In window 0, start the monitor:
   `~/bench/monitor.sh alone-5080`. It prints `logging alone-5080`.
2. Ctrl+b then c opens window 1. In it, the training:

   ```bash
   cd ~/bench/nnunet && source env.sh
   CUDA_VISIBLE_DEVICES="$GPU_5080" nnUNet_results="$RESULTS_5080" \
       uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs
   ```

3. When window 1 prints `Training done.`, go to window 0 (Ctrl+b then 0) and
   stop the monitor with Ctrl+C: it prints `stopped: alone-5080`.
4. Back in window 1 (Ctrl+b then 1), keep the result and summarize the run:

   ```bash
   cp "$RESULTS_5080/$BENCH_JSON" ~/bench/logs/alone-5080.json
   grep -E '"(gpu_name|fastest_epoch)"' ~/bench/logs/alone-5080.json
   ~/bench/summary.sh alone-5080
   ```

Then the RTX 4070, in the same session and windows: in window 0,
`~/bench/monitor.sh alone-4070`; in window 1, the commands of steps 2 and 4
with `$GPU_4070`, `$RESULTS_4070` and `alone-4070` in place of the 5080's.

Each benchmark writes its result to the same file of its GPU's folder, and the
next run overwrites it: that is why step 4 copies it right away. Each run is
pinned to a GPU by its UUID, so nothing depends on how PyTorch or `nvidia-smi`
number the cards. If `torch.compile` fails inside nnU-Net, `nnUNet_compile=f` in
front of the command turns it off; note it, because it changes the speed.

The first benchmark after an install also compiles its kernels: its epoch 0 can
take twice as long as in later runs, which reuse them. `fastest_epoch` is not
affected. Repeating a run gives the same `fastest_epoch` within about 1%, so a
smaller difference between two runs is noise.

How to fill the benchmark table:

- **s/epoch:** `fastest_epoch`, the fastest of the five epochs.
- **Peak memory:** from the summary. It includes the CUDA context and PyTorch's
  cache and, on the 5080, the desktop.
- **Wh/epoch:** mean power in W × s/epoch ÷ 3600. This is the GPU board alone;
  section 10 measures the whole PC.
- **PCIe link under load:** Gen5 x8 for the 5080 and Gen4 x8 for the 4070.
- **Clock event reasons:** a bitmask, with the number of samples of each value.
  `0x0000000000000000` is none; `0x0000000000000004` is *SW Power Cap*, the card
  at its power limit, which is normal under load. Any other value means
  something else held the clocks back, temperature for example: note it, and
  look it up in `nvidia-smi --help-query-gpu`.

**Check:** both runs finish; the RTX 4070's peak memory stays below its 12 GB
with room to spare; each link reaches its generation at x8.

### 8. Power limits: each GPU's sweet spot

A power limit caps what the card may draw; a little less power often costs
little speed. The steps are 100, 90, 80 and 70% of each card's default limit
(section 5), rounded, leaving out any value below its *Min Power Limit*. This
prints them:

```bash
source ~/bench/nnunet/env.sh
for g in "$GPU_5080" "$GPU_4070"; do
  nvidia-smi -i "$g" --query-gpu=name,power.default_limit,power.min_limit --format=csv,noheader,nounits |
    awk -F', ' '{ printf "%s:", $1; for (p = 100; p >= 70; p -= 10) { w = int($2 * p / 100 + 0.5); if (w >= $3) printf " %d", w }; print " W" }'
done
```

Each step is one benchmark, with the other GPU idle, in the tmux session of
section 7. Below, the RTX 5080 at 324 W: for each step, replace `324` in both
windows with the value the loop printed.

1. Window 0, the monitor:

   ```bash
   W=324; ~/bench/monitor.sh pl-5080-$W
   ```

2. Window 1, the limit. First:

   ```bash
   cd ~/bench/nnunet && source env.sh
   W=324
   sudo -v
   ```

   then the limit, its check and the benchmark:

   ```bash
   sudo nvidia-smi -i "$GPU_5080" -pl "$W"
   nvidia-smi -i "$GPU_5080" --query-gpu=power.limit --format=csv,noheader     # 324.00 W
   CUDA_VISIBLE_DEVICES="$GPU_5080" nnUNet_results="$RESULTS_5080" \
       uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs
   ```

3. At `Training done.`, stop the monitor in window 0 with Ctrl+C.
4. Window 1, the result:

   ```bash
   cp "$RESULTS_5080/$BENCH_JSON" ~/bench/logs/pl-5080-$W.json
   grep '"fastest_epoch"' ~/bench/logs/pl-5080-$W.json
   ~/bench/summary.sh pl-5080-$W
   awk -F', ' '$2 ~ /5080/ && $3 + 0 >= 50 { print $7 }' ~/bench/logs/gpu-pl-5080-$W.csv | sort | uniq -c    # one value: the limit set
   ```

   That last line lists the power limit of every busy sample. The samples
   logged before the limit was set carry the previous one, and the line leaves
   them out.

For the RTX 4070, `4070` in place of `5080` everywhere, `$GPU_4070` and
`$RESULTS_4070`, and its own values. A value outside a card's *Min* and *Max
Power Limit* is refused, and the benchmark would then run at the previous
limit: the check after `-pl` shows it before the training starts.

On the RTX 4070, `nvidia-smi -pl` warns that persistence mode is disabled. A
limit set that way holds while some program keeps the GPU open. The monitor
does, which is why it starts before the limit is set; the last line of step 4
proves it, with every busy sample at the limit set. The RTX 5080 drives the
desktop, which keeps it open anyway.

At the end, return both GPUs to their defaults:

```bash
sudo -v
```

```bash
for g in "$GPU_5080" "$GPU_4070"; do
  sudo nvidia-smi -i "$g" -pl "$(nvidia-smi -i "$g" --query-gpu=power.default_limit --format=csv,noheader,nounits)"
done
nvidia-smi --query-gpu=name,power.limit,power.default_limit --format=csv
```

A limit set this way lasts until the next restart, at most. Applying the chosen
limits at every start is a separate decision, with its own record.

How to read it:

- Wh/epoch falls as the limit falls, and s/epoch grows. The sweet spot is the
  step after which the time starts to grow faster than the energy falls; decide
  in advance how much slower you accept, for example 5%.
- A limit above what the card draws under this load (the summary's mean power
  at 100%) changes nothing.
- Under a cap, the power that the RTX 4070 reports can sit well below the cap
  (about 141 W under a 160 W limit, on the first run), while the RTX 5080's sits
  at its cap. Whether the 4070 really draws that little is for the wall meter
  to say: treat its Wh/epoch as provisional until section 10.
- Choose with the whole PC (section 10): while a slower epoch takes its extra
  time, the rest of the machine keeps drawing power, and a GPU's saving can
  vanish at the wall.

**Check:** the sweep table has every step of both GPUs; each run's last line
shows only the limit set; both GPUs are back at their defaults.

### 9. One GPU against two

Both benchmarks at once, with the run name `together` for the monitor. The RTX
5080 finishes its five epochs long before the RTX 4070, so more runs, which
nobody measures, keep it busy until the 4070 is done. Without them, the 4070's
last epochs would run alone and look faster than they are together.

1. Window 0: `~/bench/monitor.sh together`.
2. Window 1, the RTX 5080: the measured run, its result, and runs that keep the
   GPU busy, one after another, until you stop them:

   ```bash
   cd ~/bench/nnunet && source env.sh
   CUDA_VISIBLE_DEVICES="$GPU_5080" nnUNet_results="$RESULTS_5080" \
       uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs &&
   cp "$RESULTS_5080/$BENCH_JSON" ~/bench/logs/together-5080.json &&
   while CUDA_VISIBLE_DEVICES="$GPU_5080" nnUNet_results="$RESULTS_5080" \
       uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs; do :; done
   ```

3. Window 2 (Ctrl+b then c), the RTX 4070, right after:

   ```bash
   cd ~/bench/nnunet && source env.sh
   CUDA_VISIBLE_DEVICES="$GPU_4070" nnUNet_results="$RESULTS_4070" \
       uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs
   ```

4. When window 2 prints `Training done.`: Ctrl+C in window 1, which stops the
   5080's extra runs (it may print an error trace; their results are not used),
   then Ctrl+C in window 0.
5. Window 2, the results:

   ```bash
   cp "$RESULTS_4070/$BENCH_JSON" ~/bench/logs/together-4070.json
   grep -h -E '"(gpu_name|fastest_epoch)"' ~/bench/logs/together-*.json
   ~/bench/summary.sh together
   ```

Both runs use fold 0 because the benchmark trainers accept no other. The fold
does not change the speed: every epoch is 250 iterations of the same patch and
batch. Two real folds at once come in section 11.

How to read it, with T as s/epoch:

- **Throughput:** epochs per hour, 3600 ÷ T. Alone, the 5080 gives
  3600 ÷ T(5080 alone). Together, the machine gives 3600 ÷ T(5080 together) +
  3600 ÷ T(4070 together). Their ratio is what the second GPU adds.
- **Interference:** if each GPU is much slower together than alone, the two
  trainings compete for the CPU. Compare s/epoch first. The summary's CPU peaks
  include the seconds in which nnU-Net starts its worker processes, at the
  start of each training and of each validation, when the run queue jumps far
  above 24; that alone is not contention. If the epochs did slow down, repeat
  with `nnUNet_n_proc_DA=6` and with `10` (put it in front of both commands) and
  keep the faster.

**Check:** the one-against-two table is filled, and a value of
`nnUNet_n_proc_DA` is chosen.

### 10. The whole PC from the wall

`nvidia-smi` measures only the GPU boards. The CPU, the memory, the board, the
SSDs, the fans, the pump and the power supply's own losses are only seen from
the wall. That needs a plug-in energy meter rated for at least 15 A at 127 V,
showing W and kWh; the PC alone is plugged into it, the monitor elsewhere.

Read each state after it has run for at least two minutes, as an average over
another two:

- idle, on the desktop;
- the RTX 5080 training alone, then the RTX 4070 alone (the benchmarks of
  section 7 again);
- each step of section 8 that is a candidate for the sweet spot;
- both together, at their default limits and at the chosen ones;
- the kWh over the whole soak test (section 11), if it is repeated with the
  meter.

The difference between the wall and the sum of `power.draw` is the rest of the
machine. The kWh of a training is what it costs: kWh × your tariff.

Until this section runs, both GPUs stay at their default limits.

**Check:** the wall-power table is filled.

### 11. Soak test: both GPUs for three hours

Run it once sections 1 to 9 pass (section 10 can wait for its meter), with the
chosen `nnUNet_n_proc_DA` in `env.sh`, at the default power limits: the hottest
case. If section 8 later
sets lower limits, the soak's temperatures are an upper bound. nnU-Net's
default trainer on fold 0 and fold 1, one per GPU, stopped after three hours.
`timeout` sends the interrupt that Ctrl+C would; it calls nnU-Net's own command
in the project's environment so that the signal reaches it directly.

Window 0, the start time and the monitor:

```bash
date '+%F %T' > ~/bench/logs/soak-start
~/bench/monitor.sh soak
```

Window 1, the RTX 5080 on fold 0:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES="$GPU_5080" timeout -s INT 3h .venv/bin/nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans
```

Window 2, the RTX 4070 on fold 1, right after:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES="$GPU_4070" timeout -s INT 3h .venv/bin/nnUNetv2_train 9 3d_fullres 1 -p nnUNetResEncUNetMPlans
```

Window 3, disk and temperatures; window 4, `htop` to watch while it runs:

```bash
iostat -xz 5 > ~/bench/logs/iostat-soak.log &
while sleep 30; do date; sensors 2>/dev/null; done > ~/bench/logs/sensors-soak.log
```

When both trainings have stopped, stop the monitors: Ctrl+C in window 0; in
window 3, Ctrl+C, then `kill %1`. Then check:

```bash
S=$(cat ~/bench/logs/soak-start)
journalctl -k --since "$S" | grep -iE 'NVRM|Xid|AER|machine check|hardware error|EDAC|nvme|I/O error'   # nothing
journalctl -u systemd-oomd --since "$S" --no-pager | grep -i killed                                     # nothing
~/bench/summary.sh soak 300
cd ~/bench/nnunet && source env.sh
for f in 0 1; do
  grep -h 'Epoch time' "$nnUNet_results"/Dataset009_Spleen/nnUNetTrainer__nnUNetResEncUNetMPlans__3d_fullres/fold_$f/training_log_*.txt | sed -n '3p;$p'
done                                                                                       # an early epoch and the last, per fold: about equal
grep 'Tctl' ~/bench/logs/sensors-soak.log | sort -t+ -k2 -n | tail -n 1                    # the CPU's highest reading
grep -A2 '^spd5118' ~/bench/logs/sensors-soak.log | grep 'temp1:' | sort -t+ -k2 -n | tail -n 1   # the memory modules' highest
grep 'Composite' ~/bench/logs/sensors-soak.log | sort -t+ -k2 -n | tail -n 1               # the SSDs' highest reading
```

In the kernel log, `Xid` lines are GPU errors, `AER` lines PCIe errors,
`machine check`, `hardware error` and `EDAC` lines CPU or memory errors, and
`nvme` or `I/O error` lines disk errors: during the soak there should be none.
Epochs that grow longer over the three hours point at heat: compare the
temperatures and the clock event reasons.

The CPU can hold a `Tctl` near 90 °C through the soak while it is mostly idle:
it raises the clock of its busy cores until temperature or power stops it, and
the hottest core sets `Tctl`. It is a concern only near 95 °C. The case fans'
response is set in the firmware (install guide, sections 6 and 21). DDR5
modules work normally up to 85 °C.

After the next normal restart, the SSD's count of unsafe shutdowns must be the
one noted in section 4:

```bash
U=$(lsblk -lnso NAME,TYPE "$(findmnt -n -o SOURCE /)" | awk '$2 == "disk" { print "/dev/" $1 }')
sudo smartctl -a "$U" | grep 'Unsafe Shutdowns'
```

**Check:** both trainings ran three hours and stopped only at the timeout; the
kernel logged no error; systemd-oomd killed nothing; epoch times and
temperatures held steady; after a normal restart, the unsafe shutdowns did not
grow.

### 12. Results sheet

Copy these tables into your private note and fill them as you go.

**Baseline**

| Item | Value |
|---|---|
| CPU, threads | |
| Board, firmware version and date | |
| Memory: size, configured speed, EXPO on or off | |
| CPU frequency: driver and mode, governor, EPP, power profile | |
| Ubuntu, kernel, driver, Secure Boot | |
| Resizable BAR on each GPU | |
| Idle: CPU `Tctl`, memory modules, SSD `Composite`, each GPU's temperature, power and memory | |

**Stability and SSD**

| Item | Value |
|---|---|
| CPU stress, 30 min: result, peak `Tctl` | |
| Memory stress, 60 min: result | |
| memtester (optional): result | |
| Kernel log and systemd-oomd after the tests | |
| SSD model and slot; link; critical warning; percentage used; media errors | |
| SSD unsafe shutdowns: in section 4, and after the next normal restart | |
| SSD sequential read (MB/s), random read (IOPS), write (MB/s) | |
| SSD temperature, idle and after the speed test | |

**Power limits**

| | RTX 5080 | RTX 4070 |
|---|---|---|
| Default / min / max power limit | | |
| PCIe generation: card maximum, host maximum | | |

**Benchmark, each GPU alone, default limits**

| Measure | RTX 5080 | RTX 4070 |
|---|---|---|
| s/epoch | | |
| Peak GPU memory (MiB) | | |
| GPU utilization (%) | | |
| Mean power (W) | | |
| Wh/epoch | | |
| Peak temperature (°C) | | |
| PCIe link under load | | |
| Samples at the power cap (`0x4`) | | |
| CPU peak busy (%), peak run queue | | |
| Peak memory in use (GiB) | | |

**Power sweep** (one table per GPU)

| Limit (W) | s/epoch | Time vs 100% | Mean power (W) | Wh/epoch | Energy vs 100% | Peak °C | Samples at the cap |
|---|---|---|---|---|---|---|---|
| 100% | | | | | | | |
| 90% | | | | | | | |
| 80% | | | | | | | |
| 70% | | | | | | | |

**One GPU against two**

| | RTX 5080 | RTX 4070 | Machine |
|---|---|---|---|
| s/epoch alone | | | |
| s/epoch together | | | |
| Peak temperature together (°C) | | | |
| Epochs per hour, together | | | |
| Gain over the 5080 alone | | | |
| CPU busy: steady, and peak while workers start; peak run queue | | | |
| Peak memory in use (GiB) | | | |
| `nnUNet_n_proc_DA` chosen | | | |

**Wall power**

| State | W at the wall | GPU W (`nvidia-smi`) |
|---|---|---|
| Idle | | |
| 5080 training | | |
| 4070 training | | |
| Both, default limits | | |
| Both, chosen limits | | |
| Soak test: kWh in three hours | | |

**Soak test**

| Item | Value |
|---|---|
| Errors in the kernel log | |
| systemd-oomd kills | |
| Early and last epoch, each GPU | |
| Peak temperatures: each GPU, CPU, memory modules, SSD | |

What the results decide:

- **The RTX 4070's role:** if its peak memory leaves room below 12 GB with
  ResEnc M, it trains folds of its own; repeat with the thesis dataset before
  relying on it.
- **Power limits:** whether to apply the sweet spots at every start, once the
  wall meter (section 10) confirms them.
- **`nnUNet_n_proc_DA`** for two trainings at once.
- **The cost of a training:** its kWh from the wall.

## Appendix: the identifiers, for your private note

These print the values that stay out of this repository, all at once:

```bash
source ~/bench/nnunet/env.sh
echo "RTX 5080: $GPU_5080"; echo "RTX 4070: $GPU_4070"
nvidia-smi --query-gpu=name,pci.bus_id --format=csv,noheader
U=$(lsblk -lnso NAME,TYPE "$(findmnt -n -o SOURCE /)" | awk '$2 == "disk" { print "/dev/" $1 }')
ls -l /dev/disk/by-id/ | grep "/$(basename "$U")$"          # the Ubuntu SSD's identifiers
sudo smartctl -i "$U" | grep -E 'Model Number|Serial Number'
hostname
```

## References

- nnU-Net ResEnc presets:
  https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/resenc_presets.md
- Isensee et al., *nnU-Net Revisited: A Call for Rigorous Validation in 3D
  Medical Image Segmentation*, MICCAI 2024 (VRAM per configuration):
  https://arxiv.org/abs/2404.09556
- nnU-Net benchmarking: https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/benchmarking.md
- Medical Segmentation Decathlon: https://medicaldecathlon.com
- MONAI's mirror and checksums:
  https://github.com/Project-MONAI/MONAI/blob/dev/monai/apps/datasets.py
- `nvidia-smi`: https://docs.nvidia.com/deploy/nvidia-smi/index.html
- `stress-ng`: https://manpages.ubuntu.com/manpages/noble/man1/stress-ng.1.html
- smartmontools: https://www.smartmontools.org
- `fio`: https://fio.readthedocs.io/en/latest/fio_doc.html
- `lsblk`: https://man7.org/linux/man-pages/man8/lsblk.8.html
- AMD P-State driver (`amd-pstate`, EPP):
  https://docs.kernel.org/admin-guide/pm/amd-pstate.html
- `spd5118` (DDR5 module temperatures): https://docs.kernel.org/hwmon/spd5118.html
