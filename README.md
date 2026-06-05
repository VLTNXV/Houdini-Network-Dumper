# Houdini Network Dumper

A Houdini shelf tool that exports selected nodes — their types, wiring,
parameters, and expressions — as readable text. Useful for sharing your
setup with someone (or an AI assistant) for troubleshooting, documenting a
network, or keeping a plain-text record of how something was built.

Instead of sending screenshots, you select your nodes, click the shelf
button, and a window pops up with a complete text description of the
network that you can copy and paste anywhere.

## What it captures

For every selected node:
- Node path, type, and category (SOP / VOP / OBJ / etc.)
- Input wiring — which node feeds which input
- Flags (display, render, bypass, template)
- Parameters changed from their defaults (keeps output focused)
- Expressions, labeled as HScript or Python
- Subnet / HDA children, so nested structure is visible

It also prints a connection summary at the end as a quick map of the graph.

The output is read-only — the tool only inspects nodes and prints text. It
never changes your scene.

## Privacy

Values that look genuinely personal (absolute home/user disk paths, emails)
are redacted automatically. Group names, VEX snippets, ramps, and geometry
parameters are kept, since they matter for understanding a network and
aren't personal. You can always review the output before sharing it.

## Installation (shelf tool)

1. Right-click an empty spot on the shelf at the top of Houdini → **New Tool…**
2. Give it a **Name** and **Label** (e.g. `network_dump` / "Network Dump").
3. Optionally set the **Icon** to `MISC_python`.
4. Go to the **Script** tab and set the language to **Python**.
5. Paste the contents of `network_dump.py` into the script box.
6. Click **Accept**.

To use it: select nodes in the Network Editor, click the shelf button, and
copy the text from the pop-up window.

## Alternative: run from the Python Shell

If you'd rather not make a shelf tool, you can run the script directly:

1. Save `network_dump.py` somewhere (e.g. `C:\temp\network_dump.py`).
2. In Houdini open **Windows → Python Shell**.
3. Run: `exec(open(r"C:\temp\network_dump.py").read())`

(Pasting the full script line-by-line into the shell causes indentation
errors, so the `exec(open(...))` approach is the reliable way.)

## Compatibility

Tested on Houdini 21.0.729. The script imports Qt with a fallback that
tries PySide6 first, then PySide2, so it should work across recent Houdini
versions.

## License

MIT — do whatever you want with it. See `LICENSE`.
