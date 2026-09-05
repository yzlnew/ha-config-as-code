---
name: sync-epaper-firmware
description: Synchronize paired ESPHome e-paper firmware between /root/epaper-dashboard/firmware and /root/ha/esphome while preserving repository-specific comments and dirty worktrees. Use whenever work touches epaper-bw.yaml, epaper-e6.yaml, trmnl_dashboard.yaml, or xiao-epaper-e6.yaml; when asked to sync firmware changes, validate mirrored panel configuration, or prepare paired firmware commits.
---

# Sync E-paper Firmware

Keep executable ESPHome behavior synchronized across both repositories without
overwriting unrelated work or repository-specific documentation.

## Fixed mappings

| Panel | `/root/epaper-dashboard` | `/root/ha` |
|---|---|---|
| BW / Waveshare 7.5 v2 | `firmware/epaper-bw.yaml` | `esphome/trmnl_dashboard.yaml` |
| E6 / GDEP073E01 | `firmware/epaper-e6.yaml` | `esphome/xiao-epaper-e6.yaml` |

Do not sync `secrets.yaml`, credentials, generated images, build output, or
unrelated ESPHome devices.

## Workflow

### 1. Load repository rules and inspect both worktrees

Read `/root/epaper-dashboard/AGENTS.md` and `/root/ha/AGENTS.md` completely.
Then inspect both repositories before editing:

```bash
git -C /root/epaper-dashboard status --short
git -C /root/ha status --short
git -C /root/epaper-dashboard diff -- firmware
git -C /root/ha diff -- esphome/trmnl_dashboard.yaml esphome/xiao-epaper-e6.yaml
```

Treat every pre-existing modification as user-owned. Never use `git reset`,
`git checkout --`, blanket restoration, or whole-file replacement to remove
differences.

### 2. Resolve the authoritative side

Use the side explicitly named by the user as the source. If the user only says
"sync", infer the source only when exactly one side of a mapped pair contains
the relevant change.

Stop and ask for direction when:

- both sides contain different executable changes;
- the source cannot be determined from the request and diffs;
- unrelated edits overlap the same lines and cannot be separated safely.

Process only the mapped pair or pairs touched by the task.

### 3. Port behavior, not repository identity

Apply the firmware logic to the counterpart with a focused patch. Keep these
behaviors semantically identical:

- ESPHome component and driver configuration;
- pins, IDs, image dimensions and image URLs;
- refresh interval and `online_image` update flow;
- refresh template button and component update target;
- networking, HTTP, display lambda, and panel-specific settings.

Preserve repository-specific comments, absolute-path explanations, device
names, and surrounding unrelated configuration. Comment-only wording may
differ. Do not blindly copy an entire YAML file unless the user explicitly
requests it and both worktrees are clean for that file.

If the change originates in `/root/ha`, mirror it back to
`/root/epaper-dashboard/firmware` in the same task. The synchronization rule is
bidirectional even though the filenames differ.

### 4. Validate both copies

Run the bundled semantic checker for the changed pair:

```bash
python3 /root/ha/.codex/skills/sync-epaper-firmware/scripts/check_sync.py --pair bw
python3 /root/ha/.codex/skills/sync-epaper-firmware/scripts/check_sync.py --pair e6
```

The checker ignores blank lines and full-line comments but compares every
executable YAML line. Review any reported diff; do not suppress it.

Also run:

```bash
git -C /root/epaper-dashboard diff --check
git -C /root/ha diff --check
```

If an `esphome` executable and required local secrets are available, run
`esphome config` on both files in the changed pair from their respective
directories. If not available, report that semantic synchronization passed but
ESPHome schema validation could not be run. Never claim an unavailable check
passed.

### 5. Keep commit and flashing boundaries explicit

Synchronization does not authorize committing, pushing, compiling, flashing,
or OTA updating a physical device.

When the user requests commits:

- stage only the two mapped files or separable hunks for this task;
- preserve unrelated dirty changes;
- create a separate commit in each repository;
- report both commit hashes.

When the user explicitly requests flashing or OTA, resolve the exact panel and
device first, then follow the repository instructions. Never flash both panels
from an ambiguous request.

### 6. Report the result

State:

- authoritative source and mapped target;
- executable sections synchronized;
- validation commands and outcomes;
- any comment-only differences intentionally preserved;
- uncommitted changes left untouched;
- commit, push, or device deployment status.
