# OpenDisplay on the TRMNL 7.5" — status & custom-build recipe

**Outcome (2026-06-28): not adopted.** OpenDisplay firmware flashes, runs, pairs
over BLE, accepts config, and receives the full image — but **the panel never
renders** with stock drivers. Device reverted to ESPHome (Path A), which works.

This doc preserves everything learned so a future custom-build attempt is cheap.

## What works (verified)
- **Flash over USB** with esptool (no browser Toolbox needed). Chip is **ESP32-S3,
  16 MB flash / 8 MB PSRAM** → image `esp32-s3-N16R8_full.bin` from
  `OpenDisplay/Firmware` releases, written at `0x0`:
  ```bash
  esptool --port /dev/cu.usbmodem21201 --chip esp32s3 write-flash --erase-all 0x0 esp32-s3-N16R8_full.bin
  ```
- **BLE provisioning** via py-opendisplay (see opendisplay_provision.py): a blank
  device returns empty config, so connect with `config=` to skip interrogation,
  then `write_config()`. Config that round-trips correctly (verified by re-reading):
  - system: `ic_type=2` (ESP32-S3), `communication_modes=1` (BLE)
  - display: `display_technology=1` (e-paper), `panel_ic_type=59`
    (`ep75_800x480_gen2`, GEDY075-D2 = Waveshare/Xiao V2), `800x480`,
    `color_scheme=0` (mono), pins `clk7 / data(MOSI)9 / cs44 / dc10 / rst38 / busy4`.
  - Device **reboots** to apply config → reconnect (normal interrogate) before upload.
- **Image transfer** over BLE completes (serial shows all `0x71` data chunks + the
  `EPD refresh: FULL` command).

## Why it doesn't render (root cause)
The panel needs **inverted (active-low) BUSY** — ESPHome drives it fine with
`busy_pin: inverted: true`. OpenDisplay has **no runtime busy-invert option**;
polarity is compiled into the bb_epaper panel definition. Serial evidence:
- panel_ic_type `59` (active-high busy): `ERROR: Epaper not busy after refresh
  command` immediately → BUSY read as not-busy (wrong polarity).
- panel_ic_type `1005` (`uc8179_750_bw`, active-low busy): enters the wait loop but
  BUSY never clears → `Display refresh timed out (device sent 0x74)` / 90 s timeout.
- `busy_pin=0xFF` (timed): refresh command issued, but **panel showed zero physical
  change** in all cases — so beyond BUSY polarity, the **init/SPI/reset sequence**
  isn't driving this exact panel either.

`waitforrefresh()` in firmware `src/display_service.cpp` loops on `bbepIsBusy()`;
the panel driver + BUSY polarity come from the **bb_epaper** library, not a config.

## Custom-build recipe (to actually make it render)
1. `git clone https://github.com/OpenDisplay/Firmware` (PlatformIO; pulls
   `lib_deps = https://github.com/bitbank2/bb_epaper.git` and the pioarduino
   `platform-espressif32`).
2. In **bb_epaper**, find the 7.5"/UC8179 panel definition and either add a variant
   with **active-low BUSY** or fix `bbepIsBusy`/wait polarity for it; cross-check the
   **init sequence + LUT** against ESPHome's working `waveshare_epaper` `7.50inV2`
   (model reported as `7.5inV2rev2`) — the zero-response symptom implies the init
   (not just BUSY) differs.
3. Build the `esp32-s3-N16R8` env, flash `*_full.bin` at `0x0` over USB, re-provision
   over BLE (opendisplay_provision.py), push (opendisplay_send.py), check the glass.
4. Expect a few **flash → test** iterations; keep ESPHome's `*_full.bin` handy to revert:
   ```bash
   cd esphome && esphome upload trmnl_dashboard.yaml --device /dev/cu.usbmodem21201
   ```

## Files
- `opendisplay_provision.py` — one-time BLE config write (panel_ic_type, pins) + first push.
- `opendisplay_send.py` — recurring render + BLE push (assumes provisioned device).
- Both reuse `render.py`. BLE-only (py-opendisplay); run on a BT host near the panel.
