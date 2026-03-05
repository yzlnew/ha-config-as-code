# HA Bug: `write_utf8_file_atomic` fails with UnicodeEncodeError on non-ASCII content

## Summary

`write_utf8_file_atomic` in `homeassistant/util/file.py` does not pass `encoding="utf-8"` to `AtomicWriter`, causing `UnicodeEncodeError: 'ascii' codec can't encode characters` when writing files containing non-ASCII characters (e.g. Chinese, emoji).

## Affected Version

- Home Assistant 2026.2.2
- Platform: qemux86-64 (HA OS VM)

## Root Cause

The HA core container's PID 1 process has **no locale environment variables** set (only `PATH`). Python defaults to ASCII for file I/O encoding when no locale is configured.

```bash
# Inside the homeassistant container:
$ cat /proc/1/environ   # PID 1 only has PATH=...
$ docker exec homeassistant env | grep LANG   # LANG=C.UTF-8 (but only for new processes)
```

`write_utf8_file_atomic` uses `atomicwrites.AtomicWriter` without specifying `encoding`:

```python
# homeassistant/util/file.py, line 36-39 (current)
with AtomicWriter(filename, mode=mode, overwrite=True).open() as fdesc:
    if not private:
        os.fchmod(fdesc.fileno(), 0o644)
    fdesc.write(utf8_data)
```

`AtomicWriter.__init__` accepts `**open_kwargs` which are forwarded to the underlying `open()` call. Without `encoding="utf-8"`, it falls back to `locale.getpreferredencoding()` which is ASCII for PID 1.

In contrast, `write_utf8_file` in the same file correctly sets encoding:

```python
# homeassistant/util/file.py, line 48 (correct)
encoding = "utf-8" if "b" not in mode else None
with tempfile.NamedTemporaryFile(
    mode=mode, encoding=encoding, ...
```

## Reproduction

1. Run HA OS in a VM (qemux86-64)
2. Create an automation with non-ASCII characters in any field (alias, notification message, etc.)
3. Try to update/create any automation via REST API (`POST /api/config/automation/config/{id}`)
4. Observe 500 Internal Server Error

Error traceback:
```
File "homeassistant/components/config/view.py", line 251, in _write
    write_utf8_file_atomic(path, contents)
File "homeassistant/util/file.py", line 39, in write_utf8_file_atomic
    fdesc.write(utf8_data)
UnicodeEncodeError: 'ascii' codec can't encode characters in position 2184-2194: ordinal not in range(128)
```

## Fix

### One-line patch (for `homeassistant/util/file.py`)

```diff
 def write_utf8_file_atomic(
     filename: str, utf8_data: bytes | str, private: bool = False, mode: str = "w"
 ) -> None:
     try:
-        with AtomicWriter(filename, mode=mode, overwrite=True).open() as fdesc:
+        with AtomicWriter(filename, mode=mode, overwrite=True, encoding="utf-8" if "b" not in mode else None).open() as fdesc:
             if not private:
                 os.fchmod(fdesc.fileno(), 0o644)
             fdesc.write(utf8_data)
```

### Workaround (applied to running instance)

```bash
docker exec homeassistant sed -i \
  's/AtomicWriter(filename, mode=mode, overwrite=True)/AtomicWriter(filename, mode=mode, overwrite=True, encoding="utf-8" if "b" not in mode else None)/' \
  /usr/src/homeassistant/homeassistant/util/file.py
ha core restart
```

Note: This workaround is lost on HA version updates.

### Secondary fix (defense in depth)

The HA core container should also set `LANG=C.UTF-8` for PID 1, not just for new processes spawned via `docker exec`. This would make `locale.getpreferredencoding()` return `UTF-8` by default.

## Discovery Process

1. All automation REST API writes returned 500 — both create and delete
2. `ha core logs` showed `UnicodeEncodeError: 'ascii' codec` in `write_utf8_file_atomic`
3. Checked container locale: `docker exec ... env` showed `LANG=C.UTF-8`, `python3 -c "import locale; print(locale.getpreferredencoding(False))"` showed `UTF-8` — appeared normal
4. Inspected PID 1 environment via `/proc/1/environ` — discovered only `PATH` was set, no locale variables
5. Read `homeassistant/util/file.py` source — found `AtomicWriter` called without `encoding` parameter
6. Confirmed `AtomicWriter.__init__` accepts `**open_kwargs` forwarded to `open()`
7. Verified fix: passing `encoding="utf-8"` resolves the issue
