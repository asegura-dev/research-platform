# Download a public imaging dataset from IDC onto the workstation

> **Scope:** the GPU workstation's Ubuntu, and the public collections of the
> NCI Imaging Data Commons (IDC). Written for PSMA-PET-CT-Lesions, the dataset
> the first project trains on. Another IDC collection takes the same steps,
> with its own `collection_id` and the numbers its dry run prints (section 3).
> Converting the DICOM files for training belongs to each project.

> **Status:** written on 2026-10-29 from idc-index 0.13.4, which carries IDC
> data release v25, and from the collection's page at The Cancer Imaging
> Archive (TCIA). The install and the dry run (sections 2 and 3) were checked
> with that version, and the download's behaviour on errors and resumes was
> read in the source of idc-index and s5cmd; the download has not run yet.

IDC keeps public DICOM collections in public cloud buckets. Its Python tool,
idc-index, downloads a whole collection with one command, needs no account,
and continues where it stopped. For PSMA-PET-CT-Lesions, IDC holds the same
DICOM files as TCIA's Version 2, the current one.

Every section ends with a check. Read-only commands come first. Nothing here
needs a placeholder: the collection is public, and the paths are in your home
folder.

## Decisions this guide depends on

| Decision | Value here | Why it matters | Record |
|---|---|---|---|
| Source | IDC, with idc-index; not TCIA's Data Retriever | No account, one command that resumes, and a free-space check before it starts. TCIA's new retriever downloads these series from IDC anyway | This guide |
| Format | DICOM, not the NIfTI copies on FDAT | DICOM keeps the CT at its original resolution and every header. The NIfTI copies resample the CT to the PET grid, and their license allows non-commercial use only | This guide |
| Version | idc-index 0.13.4, which fixes IDC data release v25 | The same command downloads the same files later, and the release goes into the project's record | This guide |
| Where | `~/data/idc` on the Ubuntu SSD; files from TCIA's page in `~/data/tcia` | Training reads from the NVMe SSD, and each folder holds what one source serves | This guide |

## The dataset

| | PSMA-PET-CT-Lesions |
|---|---|
| IDC `collection_id` | `psma_pet_ct_lesions` |
| Content | 378 patients and 597 studies; each study has a CT, a PET and a segmentation (DICOM SEG) |
| Size | 117,076,426,764 bytes (117.08 GB, 109.04 GiB) in 374,151 files and 1,791 series |
| Files by modality | CT 185,853; PT 187,701; SEG 597 |
| License | CC BY 4.0 |
| Page | https://www.cancerimagingarchive.net/collection/psma-pet-ct-lesions/ |

The data descriptor gives about 190 GB for the same 374,151 files; TCIA's page
and IDC's index both give 117.08 GB. This guide checks against IDC's numbers.

## 1. What you need

- The workstation through section 20 of
  [its guide](install-ubuntu-gpu-workstation.md), with uv and tmux from the
  [validation guide](validate-gpu-workstation.md) (sections 6 and 1).
- Space on the Ubuntu SSD: the download takes 117 GB, but start with at least
  235 GB free. Every run, a resumed one too, asks for the whole collection's
  117.08 GB free before it starts, however much of it is already on disk. The
  conversions that come after it, to NIfTI and then to nnU-Net's preprocessed
  data, take more: count on about 500 GB in all.
- Time, which depends on your internet connection:

  | Connection | Time for 117 GB |
  |---|---|
  | 50 Mbit/s | about 5 h 12 min |
  | 100 Mbit/s | about 2 h 36 min |
  | 250 Mbit/s | about 1 h 2 min |
  | 1 Gbit/s | about 16 min, in theory |

  With 374,151 small files the real speed is lower. One night is enough from
  50 Mbit/s up.

**Check:** `df -h ~` shows at least 235 GB under *Avail*; about 500 GB leaves
room for the conversions.

## 2. Install idc-index

uv installs it as a tool with its own Python, and puts its `idc` command in
`~/.local/bin`:

```bash
uv tool install idc-index==0.13.4
```

The version is fixed on purpose. idc-index 0.13.4 carries the index of IDC
data release v25, so the download is the same whenever it runs. A newer
idc-index brings a newer release: change it only on purpose, and write the new
version in your record (section 7).

**Check:**

```bash
uv tool list     # idc-index v0.13.4, with the idc command
idc --help       # Commands: download, download-from-manifest, download-from-selection
```

## 3. Check the size and the free space (dry run)

```bash
mkdir -p ~/data/idc
idc download-from-selection --collection-id psma_pet_ct_lesions --download-dir ~/data/idc --dry-run True
```

It downloads nothing. It prints the release, the size and the free space:

```text
… - Downloading from IDC v25 index
… - Disk size needed: 117.08 GB
… - Disk size available: … GB
```

When the space falls short it says *Insufficient disk space* instead. The
download in section 4 makes the same check at every run and refuses to start.

**Check:** `IDC v25` and `117.08 GB`, and at least 235 GB available, so that a
resumed run also fits.

## 4. Download

The download runs inside tmux, so that closing the terminal, or the SSH session
that opened it, does not stop it. In the workstation's terminal, or from
another computer after `ssh workstation`:

```bash
tmux new -A -s data
```

Inside tmux:

```bash
idc download-from-selection --collection-id psma_pet_ct_lesions --download-dir ~/data/idc --use-s5cmd-sync True
```

It prints the three lines of the dry run, then the download's progress. Ctrl+b
then d leaves it running; `tmux attach -t data`, at the workstation or over
SSH, shows it again.

**If it stops** (the connection drops, the machine restarts), run the same
command again, in tmux. With `--use-s5cmd-sync True` and files already in the
folder, it copies only what is missing or differs in size. It still needs
117.08 GB free to start (section 1).

The command returns to the prompt whether or not every file arrived, so read
its last lines:

- A first run that worked ends with `Successfully downloaded files to …`.
- `Download process failed` or `non-zero exit code` means that some files did
  not arrive: run the same command again.
- A resumed run prints no such line. Its `It appears that all requested DICOM
  files are already present in destination folder` also appears when the
  connection is down, after error lines.

Whatever it prints, the counts of section 5 decide.

The files land in one folder per patient, study and series:

```text
~/data/idc/psma_pet_ct_lesions/<PatientID>/<StudyInstanceUID>/<Modality>_<SeriesInstanceUID>/<uuid>.dcm
```

`<Modality>` is `CT`, `PT` or `SEG`. The file names are IDC's identifiers, not
slice numbers: the order of the slices is in the DICOM headers.

**Check:** the first run ends with `Successfully downloaded files to …`, or a
later run returned to the prompt; either way, section 5 next. `exit` closes the
tmux session.

## 5. Verify

idc-index carries no checksums, so the check is a count: patients, studies,
series, files and bytes must match IDC's index.

```bash
cd ~/data/idc/psma_pet_ct_lesions
ls -d PSMA_* | wc -l                                  # 378 patients
find . -mindepth 2 -maxdepth 2 -type d | wc -l        # 597 studies
for m in CT PT SEG; do printf '%s ' "$m"; find . -mindepth 3 -maxdepth 3 -type d -name "${m}_*" | wc -l; done                  # 597 series each
for m in CT PT SEG; do printf '%s ' "$m"; find . -mindepth 4 -type f -path "*/${m}_*/*" -name '*.dcm' | wc -l; done         # CT 185853, PT 187701, SEG 597
find . -type f -name '*.dcm' -printf '%s\n' | awk '{s+=$1} END {print s}'                                                     # 117076426764
find . -type f ! -name '*.dcm' | wc -l                # 0: nothing left over from an interrupted run
```

`find` adds up the files' own sizes; `du` would add the folders' blocks too and
print another number.

If a number falls short, run the command of section 4 again, which copies what
is missing or differs in size, then repeat these checks. The counts cannot
catch a file with the right size and wrong content; reading every file, as the
conversion does, is the check for that.

The last line counts leftovers. The download writes each file under a
temporary name, its own name with digits after `.dcm`, and renames it once
complete. A restart or a power cut in the middle leaves such files behind; the
counts above skip them, and a resumed run does not remove them. If the line is
not 0, list them first, read-only:

```bash
find . -type f ! -name '*.dcm'
```

Only if every name ends in `.dcm` followed by digits, delete them, and count
again:

```bash
find . -type f -regex '.*\.dcm[0-9]+' -delete
find . -type f ! -name '*.dcm' | wc -l                # 0
```

**Check:** every number matches, and nothing is left over.

## 6. The metadata from TCIA's page

One file is not in IDC: TCIA's table with each study's age at imaging, scanner,
PET radionuclide and CT contrast.

```bash
mkdir -p ~/data/tcia && cd ~/data/tcia
curl -fLO https://www.cancerimagingarchive.net/wp-content/uploads/PSMA-PET-CT-Lesions-CLINICAL_v01_20251118.tsv
```

Read-only checks:

```bash
F=PSMA-PET-CT-Lesions-CLINICAL_v01_20251118.tsv
head -n 1 "$F"                                # case_identifier_number, study_date, Age_at_Imaging, Manufacturer, …
tail -n +2 "$F" | wc -l                       # lines: one per study
tail -n +2 "$F" | cut -f1 | sort -u | wc -l   # patients
sha256sum "$F"                                # for your record
```

`case_identifier_number` is the DICOM `PatientID`, the name of each patient's
folder in section 4. The table has one line per study, so the two counts
should be the collection's 597 studies and 378 patients. They were not checked
when this guide was written: if they differ, write down what you got.

**Check:** the header starts with `case_identifier_number`, and the counts are
in your record.

## 7. Record what you downloaded

A project has to say exactly which data it used. Write in your private note, or
in the project's own records:

- the date, and *idc-index 0.13.4, IDC data release v25*;
- the numbers of sections 5 and 6;
- the SHA-256 of the TSV.

Everything that uses the data cites:

- the collection: PSMA-PET-CT-Lesions, The Cancer Imaging Archive,
  https://doi.org/10.7937/R7EP-3X37;
- its data descriptor: Jeblick, K. et al., *A whole-body PSMA-PET/CT dataset
  with manually annotated tumor lesions*, *Scientific Data* 13, 1023 (2026),
  https://doi.org/10.1038/s41597-026-07821-z;
- IDC: Fedorov, A. et al., *RadioGraphics* (2023),
  https://doi.org/10.1148/rg.230180.

**Check:** your record holds the release, the numbers and the hash.

## If something goes wrong

Find what you see and do what the last column says. If that does not fix it,
stop there and write down what you saw.

| Section | What you see | What to do |
|---|---|---|
| 2 | `uv: command not found` | uv comes from the validation guide, section 6. Open a new terminal after installing it. |
| 2, 3 | `idc: command not found` | Open a new terminal, so that `~/.local/bin` is on your `PATH`. `uv tool list` shows whether idc-index is installed. |
| 3, 4 | `Insufficient disk space. Need 117.08 GB, but only … GB available.` | Every run asks for the whole collection's size free, a resumed one too, however much is already downloaded. Free space on the SSD, then run the command again. |
| 4 | `Download process failed`, `non-zero exit code`, or the machine restarted | Run the same command again, in tmux: it continues. |
| 4 | `It appears that all requested DICOM files are already present in destination folder`, with error lines above it | The connection failed while the run compared the files, so nothing was compared. Run it again once the connection is back, and let section 5 decide. |
| 4 | `tmux attach -t data` answers `no sessions` or `can't find session: data` | The session is gone: the machine restarted, or it was closed with `exit`. Run the checks of section 5; if they fall short, open the session again and start the download. |
| 5 | Fewer files or bytes than expected | Run the download again: it copies only what is missing or differs. |
| 5 | The leftover count is not 0 | Files from an interrupted run: section 5 lists them before deleting anything. |
| 6 | `curl: (22) The requested URL returned error: 404` | TCIA replaced the file. Download the current table from the collection's page and write its name in your record. |

## References

- IDC, *Downloading data*:
  https://learn.canceridc.dev/data/downloading-data/downloading-data
- idc-index, source and documentation:
  https://github.com/ImagingDataCommons/idc-index and
  https://pypi.org/project/idc-index/
- IDC release notes (the collection arrived in v24):
  https://learn.canceridc.dev/data/data-release-notes
- IDC portal, the collection:
  https://portal.imaging.datacommons.cancer.gov/collections/psma_pet_ct_lesions
- IDC, how to cite it: https://portal.imaging.datacommons.cancer.gov/about
- TCIA, the collection's page (counts, versions, license, metadata table):
  https://www.cancerimagingarchive.net/collection/psma-pet-ct-lesions/
- The NIfTI copies on FDAT, not used here (CC BY-NC 4.0):
  https://fdat.uni-tuebingen.de/records/g27kx-86t35
- The conversion code that TCIA's page recommends:
  https://github.com/ClinicalDataScience/tcia-psma-pet-ct-preprocessing
- uv, *Using tools*: https://docs.astral.sh/uv/guides/tools/
- nnU-Net, where its folders should live:
  https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/setting_up_paths.md
