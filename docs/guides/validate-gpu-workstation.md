# Validate the GPU workstation before it trains for real

> **Scope:** the GPU workstation once
> [install-ubuntu-gpu-workstation.md](install-ubuntu-gpu-workstation.md) is done:
> Ubuntu Desktop on its internal SSD, the 580 driver loaded, both GPUs visible.
> Nothing here changes the installation; the only changes are packages, files
> under `~/bench`, and GPU power limits that last until the next restart.

> **Status:** written on 2026-10-21; not yet run end to end.

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
- Keep the results in the results sheet at the end, copied into your private
  note. The tools print identifiers that never enter this repository: GPU UUIDs,
  serial numbers, and the hostname, which nnU-Net writes into its benchmark
  files.
- Measure on a quiet machine: no downloads, no video in the browser, no other
  training.
- Placeholders: `<uuid-5080>` and `<uuid-4070>` come from `nvidia-smi -L`;
  `<ubuntu-eui>` is the Ubuntu SSD's `nvme-eui.` identifier (install guide,
  sections 8 and 9).

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

Then leave the machine idle for ten minutes, with only a terminal open, and read
the idle state:

```bash
sensors
nvidia-smi --query-gpu=name,temperature.gpu,power.draw,memory.used,pstate --format=csv
```

How to read it:

- *Configured Memory Speed* of 6000 MT/s or similar means the memory runs its
  EXPO profile; 4800 to 5600 MT/s means the JEDEC defaults. EXPO is the most
  frequent cause of memory errors, which makes section 3 matter more.
- The *BAR1 Memory Usage* total of each GPU close to its memory size means
  Resizable BAR is on.
- In `sensors`, `k10temp` reports the CPU (`Tctl`) and the `nvme` entry the SSD
  (`Composite`).
- At idle the RTX 5080 holds some memory for the desktop, which runs on it; the
  RTX 4070 should hold almost none.

**Check:** the baseline table of the results sheet is filled.

### 3. CPU and memory stability

Watch the temperatures in a second terminal while the tests run:

```bash
watch -n 5 sensors
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
stress-ng --vm 8 --vm-bytes 5g --vm-method all --verify --timeout 60m --metrics-brief 2>&1 | tee stress-vm.log
```

Afterwards:

```bash
grep -E 'failed|successful run' ~/bench/logs/stress-*.log         # failed: 0, and successful run completed, in both
journalctl -k -b | grep -iE 'mce|machine check|hardware error'     # nothing
journalctl -u systemd-oomd -b --no-pager | grep -i kill           # nothing
```

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

Identify it by its identifier, not by its name, which can change between starts:

```bash
U=$(readlink -f /dev/disk/by-id/nvme-eui.<ubuntu-eui>); echo "$U"        # /dev/nvme…n1
findmnt -n -o SOURCE /                                                    # a partition of that disk
sudo smartctl -a "$U" | grep -E 'Model Number|Firmware Version|Critical Warning|Temperature:|Available Spare:|Percentage Used|Data Units Written|Media and Data Integrity Errors|Unsafe Shutdowns'
lsblk --discard "$U"                     # DISC-GRAN and DISC-MAX other than 0: TRIM reaches the SSD
systemctl is-enabled fstrim.timer        # enabled: Ubuntu trims once a week
```

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

**Check:** Gen4 x4; *Critical Warning* 0x00 and no media errors; the speeds and
temperatures are in the results sheet.

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

The nnU-Net folders, kept apart from any project:

```bash
cat > env.sh <<'EOF'
# nnU-Net folders for the benchmarks. In each new terminal: source ~/bench/nnunet/env.sh
export nnUNet_raw="$HOME/bench/nnunet/data/raw"
export nnUNet_preprocessed="$HOME/bench/nnunet/data/preprocessed"
export nnUNet_results="$HOME/bench/nnunet/data/results"
# nnU-Net's benchmark trainers accept only fold 0: each GPU writes to its own folder
export RESULTS_5080="$HOME/bench/nnunet/data/bench-5080"
export RESULTS_4070="$HOME/bench/nnunet/data/bench-4070"
# Data-augmentation processes per training: 8, plus 4 for validation
export nnUNet_n_proc_DA=8
EOF
source env.sh
mkdir -p "$nnUNet_raw" "$nnUNet_preprocessed" "$nnUNet_results" "$RESULTS_5080" "$RESULTS_4070" download
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
converted: two input channels change the plan.

**Check:** `check_gpus.py` prints `ok` for both GPUs; the MD5 matches; the plan
prints a patch and a batch.

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

The second summarizes a run. It leaves out the first two minutes of each GPU's
log, where `torch.compile` and the first epoch run, and the samples in which a
GPU did nothing:

```bash
cat > ~/bench/summary.sh <<'EOF'
#!/usr/bin/env bash
# Usage: ~/bench/summary.sh <run-name> [seconds of warm-up to leave out, default 120]
set -u
cd ~/bench/logs
awk -F', ' -v skip="${2:-120}" '
  { n[$2]++ }
  n[$2] > skip && $3 > 0 {
    k[$2]++; u[$2] += $3; p[$2] += $6
    if ($4 + 0 > m[$2]) m[$2] = $4 + 0
    if ($5 + 0 > t[$2]) t[$2] = $5 + 0
    if ($9 + 0 > gen[$2]) gen[$2] = $9 + 0
    if ($10 + 0 > w[$2]) w[$2] = $10 + 0
    seen[$2, $11] = 1 }
  END {
    for (g in k) {
      printf "%s: utilization %.0f%%, power %.0f W, peak memory %d MiB, peak %d C, PCIe Gen%d x%d\n",
             g, u[g] / k[g], p[g] / k[g], m[g], t[g], gen[g], w[g]
      for (s in seen) { split(s, a, SUBSEP); if (a[1] == g) print "  clock event reasons seen: " a[2] } } }' "gpu-$1.csv"
T=$(awk '/^MemTotal/ { print $2 }' /proc/meminfo)
awk -v T="$T" 'NR > 3 && $1 ~ /^[0-9]+$/ {
    n++; idle += $15; used = T - $4 - $5 - $6
    if (used > mx) mx = used; if ($1 > r) r = $1 }
  END { if (n) printf "CPU busy %.0f%%, peak memory in use %.1f GiB, peak run queue %d (24 threads)\n",
                      100 - idle / n, mx / 1048576, r }' "vmstat-$1.log"
EOF
chmod +x ~/bench/summary.sh
```

Runs go in `tmux`, which keeps them alive if the terminal closes:
`tmux new -s bench` starts a session; Ctrl+b then c opens a window, Ctrl+b then
n moves to the next one, Ctrl+b then d leaves it running, and
`tmux attach -t bench` comes back.

For the RTX 5080: in window 0, `~/bench/monitor.sh alone-5080`; in window 1:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-5080> nnUNet_results="$RESULTS_5080" \
    uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs
```

When it finishes, stop the monitor with Ctrl+C in window 0, and keep the
result:

```bash
cd ~/bench/nnunet && source env.sh
F="Dataset009_Spleen/nnUNetTrainerBenchmark_5epochs__nnUNetResEncUNetMPlans__3d_fullres/fold_0/benchmark_result.json"
cp "$RESULTS_5080/$F" ~/bench/logs/alone-5080.json
grep -E '"(gpu_name|fastest_epoch)"' ~/bench/logs/alone-5080.json
~/bench/summary.sh alone-5080
```

Then the same for the RTX 4070: the run name `alone-4070`, `<uuid-4070>` and
`$RESULTS_4070` in place of the 5080's.

Each run is pinned to a GPU by its UUID, so nothing depends on how PyTorch or
`nvidia-smi` number the cards. If `torch.compile` fails inside nnU-Net,
`nnUNet_compile=f` in front of the command turns it off; note it, because it
changes the speed.

How to fill the benchmark table:

- **s/epoch:** `fastest_epoch`, the fastest of the five epochs.
- **Peak memory:** from the summary. It includes the CUDA context and PyTorch's
  cache and, on the 5080, the desktop.
- **Wh/epoch:** mean power in W × s/epoch ÷ 3600. This is the GPU board alone;
  section 10 measures the whole PC.
- **PCIe link under load:** Gen5 x8 for the 5080 and Gen4 x8 for the 4070.
- **Clock event reasons:** a bitmask; `0x0000000000000000` is none. Any other
  value means something held the clocks back (power cap, temperature): note it.

**Check:** both runs finish; the RTX 4070's peak memory stays below its 12 GB
with room to spare; each link reaches its generation at x8.

### 8. Power limits: each GPU's sweet spot

A power limit caps what the card may draw; a little less power often costs
little speed. Steps of 100, 90, 80 and 70% of each card's default limit
(section 5), rounded, leaving out any value below its *Min Power Limit*: for a
default of 360 W, 360, 324, 288 and 252 W; for a default of 200 W, 200, 180, 160
and 140 W.

For each GPU and each step, with the other GPU idle. The limit:

```bash
sudo nvidia-smi -i <uuid-5080> -pl 324
nvidia-smi -i <uuid-5080> --query-gpu=power.limit --format=csv,noheader     # 324.00 W
```

Then the benchmark of section 7 under the run name `pl-5080-324`, and
`pl-5080-324.json` as its result file. Repeat for every step and both GPUs. At
the end, return each GPU to its default:

```bash
sudo nvidia-smi -i <uuid-5080> -pl <default-5080>
sudo nvidia-smi -i <uuid-4070> -pl <default-4070>
nvidia-smi --query-gpu=name,power.limit,power.default_limit --format=csv
```

A limit set this way lasts until the next restart. Applying the chosen limits at
every start is a separate decision, with its own record.

How to read it: Wh/epoch falls as the limit falls, and s/epoch grows. The sweet
spot is the step after which the time starts to grow faster than the energy
falls; decide in advance how much slower you accept, for example 5%.

**Check:** the sweep table has every step of both GPUs, and both are back at
their defaults.

### 9. One GPU against two

Both benchmarks at once, started together, with the run name `together` for the
monitor. Window 1, the RTX 5080:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-5080> nnUNet_results="$RESULTS_5080" \
    uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs
```

Window 2, the RTX 4070, at the same time:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-4070> nnUNet_results="$RESULTS_4070" \
    uv run nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerBenchmark_5epochs
```

When both have finished:

```bash
cd ~/bench/nnunet && source env.sh
F="Dataset009_Spleen/nnUNetTrainerBenchmark_5epochs__nnUNetResEncUNetMPlans__3d_fullres/fold_0/benchmark_result.json"
cp "$RESULTS_5080/$F" ~/bench/logs/together-5080.json
cp "$RESULTS_4070/$F" ~/bench/logs/together-4070.json
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
  trainings compete for the CPU. A busy CPU near 100% and a run queue above 24
  point there: repeat with `nnUNet_n_proc_DA=6` and with `10` (put it in front
  of both commands) and keep the faster.

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
- both together, at their default limits and at the chosen ones;
- the kWh over the whole soak test (section 11).

The difference between the wall and the sum of `power.draw` is the rest of the
machine. The kWh of a training is what it costs: kWh × your tariff.

**Check:** the wall-power table is filled.

### 11. Soak test: both GPUs for three hours

Run it once the previous sections pass, with the chosen power limits applied
(section 8) and the chosen `nnUNet_n_proc_DA` in `env.sh`. nnU-Net's default
trainer on fold 0 and fold 1, one per GPU, stopped after three hours. `timeout`
sends the interrupt that Ctrl+C would; it calls nnU-Net's own command in the
project's environment so that the signal reaches it directly.

Window 0, the start time and the monitors:

```bash
date '+%F %T' > ~/bench/logs/soak-start
~/bench/monitor.sh soak
```

Window 1, the RTX 5080 on fold 0:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-5080> timeout -s INT 3h .venv/bin/nnUNetv2_train 9 3d_fullres 0 -p nnUNetResEncUNetMPlans
```

Window 2, the RTX 4070 on fold 1, at the same time:

```bash
cd ~/bench/nnunet && source env.sh
CUDA_VISIBLE_DEVICES=<uuid-4070> timeout -s INT 3h .venv/bin/nnUNetv2_train 9 3d_fullres 1 -p nnUNetResEncUNetMPlans
```

Window 3, disk and temperatures; window 4, `htop` to watch while it runs:

```bash
iostat -xz 5 > ~/bench/logs/iostat-soak.log &
while sleep 30; do date; sensors; done > ~/bench/logs/sensors-soak.log
```

When both trainings have stopped, stop the monitors (Ctrl+C in windows 0 and 3,
then `kill %1` in window 3), and check:

```bash
S=$(cat ~/bench/logs/soak-start)
journalctl -k --since "$S" | grep -iE 'NVRM|Xid|AER|MCE|EDAC|nvme|I/O error'     # nothing
journalctl -u systemd-oomd --since "$S" --no-pager | grep -i kill               # nothing
~/bench/summary.sh soak 300
cd ~/bench/nnunet && source env.sh
for f in 0 1; do
  grep -h 'Epoch time' "$nnUNet_results"/Dataset009_Spleen/nnUNetTrainer__nnUNetResEncUNetMPlans__3d_fullres/fold_$f/training_log_*.txt | sed -n '3p;$p'
done                                                                            # an early epoch and the last, per fold: about equal
grep 'Tctl' ~/bench/logs/sensors-soak.log | sort -t+ -k2 -n | tail -n 1         # the CPU's highest reading
grep 'Composite' ~/bench/logs/sensors-soak.log | sort -t+ -k2 -n | tail -n 1    # the SSDs' highest reading
```

In the kernel log, `Xid` lines are GPU errors, `AER` lines PCIe errors, `MCE`
and `EDAC` lines CPU or memory errors, and `nvme` or `I/O error` lines disk
errors: during the soak there should be none. Epochs that grow longer over the
three hours point at heat: compare the temperatures and the clock event
reasons.

**Check:** both trainings ran three hours and stopped only at the timeout; the
kernel logged no error; systemd-oomd killed nothing; epoch times and
temperatures held steady.

### 12. Results sheet

Copy these tables into your private note and fill them as you go.

**Baseline**

| Item | Value |
|---|---|
| CPU, threads | |
| Board, firmware version and date | |
| Memory: size, configured speed, EXPO on or off | |
| Ubuntu, kernel, driver, Secure Boot | |
| Resizable BAR on each GPU | |
| Idle: CPU `Tctl`, SSD `Composite`, each GPU's temperature, power and memory | |

**Stability and SSD**

| Item | Value |
|---|---|
| CPU stress, 30 min: result, peak `Tctl` | |
| Memory stress, 60 min: result | |
| memtester (optional): result | |
| SSD link; critical warning; percentage used; media errors | |
| SSD sequential read (MB/s), random read (IOPS), write (MB/s) | |
| SSD temperature, idle and after the speed test | |

**Power limits**

| | RTX 5080 | RTX 4070 |
|---|---|---|
| Default / min / max power limit | | |

**Benchmark, each GPU alone, default limits**

| Measure | RTX 5080 | RTX 4070 |
|---|---|---|
| s/epoch | | |
| Peak GPU memory (MiB) | | |
| GPU utilization (%) | | |
| Mean power (W) | | |
| Wh/epoch | | |
| Peak temperature (°C) | | |
| CPU busy (%) | | |
| Peak memory in use (GiB) | | |
| PCIe link under load | | |
| Clock event reasons | | |

**Power sweep** (one table per GPU)

| Limit (W) | s/epoch | Mean power (W) | Wh/epoch | Peak °C |
|---|---|---|---|---|
| 100% | | | | |
| 90% | | | | |
| 80% | | | | |
| 70% | | | | |

**One GPU against two**

| | RTX 5080 | RTX 4070 | Machine |
|---|---|---|---|
| s/epoch alone | | | |
| s/epoch together | | | |
| Epochs per hour, together | | | |
| Gain over the 5080 alone | | | |
| CPU busy, peak run queue | | | |
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
| Peak temperatures: each GPU, CPU, SSD | |

What the results decide:

- **The RTX 4070's role:** if its peak memory leaves room below 12 GB with
  ResEnc M, it trains folds of its own; repeat with the thesis dataset before
  relying on it.
- **Power limits:** whether to apply the sweet spots at every start.
- **`nnUNet_n_proc_DA`** for two trainings at once.
- **The cost of a training:** its kWh from the wall.

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
