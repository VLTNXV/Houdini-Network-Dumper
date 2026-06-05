import hou
try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

# ----------------------------------------------------------------------
# Houdini network dumper (shelf tool version)
# Select nodes, click the shelf button -> a window pops up with the dump.
# Read-only: inspects nodes and shows text. Changes nothing in your scene.
# ----------------------------------------------------------------------

ONLY_NON_DEFAULT = True

REDACT_HINTS = ("filename", "user", "host", "email", "author", "license", "token", "$HOME")

def is_pathish(parm):
    n = parm.name().lower()
    return any(h in n for h in REDACT_HINTS)

def looks_personal(val):
    s = str(val)
    return ("\\Users\\" in s or "/Users/" in s or "/home/" in s
            or "C:\\" in s
            or (s.count("@") == 1 and "." in s and " " not in s))

def redact(parm, val):
    s = str(val)
    if looks_personal(s):
        return "<redacted-personal>"
    return s

def parm_line(parm):
    try:
        try:
            expr = parm.expression()
            raw = parm.rawValue()
        except hou.OperationFailed:
            expr = None
            raw = None

        if ONLY_NON_DEFAULT and parm.isAtDefault() and not expr:
            return None

        if expr:
            lang = "py" if parm.expressionLanguage() == hou.exprLanguage.Python else "hscript"
            return f"      {parm.name()} = [{lang} expr] {redact(parm, raw)}"
        else:
            val = parm.eval()
            return f"      {parm.name()} = {redact(parm, val)}"
    except Exception as e:
        return f"      {parm.name()} = <error: {e}>"

def dump_node(node, all_selected_paths):
    out = []
    out.append(f"NODE: {node.path()}")
    out.append(f"  type: {node.type().name()}  (category: {node.type().category().name()})")

    flags = []
    try:
        if node.isDisplayFlagSet(): flags.append("display")
    except Exception: pass
    try:
        if node.isRenderFlagSet(): flags.append("render")
    except Exception: pass
    try:
        if node.isBypassed(): flags.append("BYPASSED")
    except Exception: pass
    try:
        if node.isTemplateFlagSet(): flags.append("template")
    except Exception: pass
    if flags:
        out.append(f"  flags: {', '.join(flags)}")

    inputs = node.inputs()
    if inputs:
        conns = []
        for i, src in enumerate(inputs):
            if src is None:
                continue
            tag = "" if src.path() in all_selected_paths else "  [outside selection]"
            conns.append(f"    input {i} <- {src.path()}{tag}")
        if conns:
            out.append("  inputs:")
            out.extend(conns)
    else:
        out.append("  inputs: (none)")

    try:
        labels = node.inputLabels()
        if labels and any(labels):
            out.append(f"  input_labels: {list(labels)}")
    except Exception:
        pass

    plines = []
    for parm in node.parms():
        line = parm_line(parm)
        if line is not None:
            plines.append(line)
    if plines:
        out.append("  parameters" + (" (non-default only)" if ONLY_NON_DEFAULT else "") + ":")
        out.extend(plines)
    else:
        out.append("  parameters: (all at default)")

    children = node.children()
    if children:
        out.append(f"  contains {len(children)} child node(s): "
                   + ", ".join(f"{c.name()}({c.type().name()})" for c in children))

    return "\n".join(out)

def build_dump():
    sel = hou.selectedNodes()
    if not sel:
        return "No nodes selected. Select nodes in the Network Editor and re-run."

    selected_paths = {n.path() for n in sel}
    lines = []
    lines.append("=" * 70)
    lines.append(f"HOUDINI NETWORK DUMP — {len(sel)} node(s) selected")
    try:
        lines.append(f"Houdini version: {hou.applicationVersionString()}")
    except Exception:
        pass
    lines.append(f"Context: {sel[0].parent().path() if sel[0].parent() else '/'}")
    lines.append("=" * 70)

    for node in sorted(sel, key=lambda n: n.path()):
        lines.append("")
        lines.append(dump_node(node, selected_paths))

    lines.append("")
    lines.append("-" * 70)
    lines.append("CONNECTION SUMMARY (within selection):")
    for node in sorted(sel, key=lambda n: n.path()):
        for i, src in enumerate(node.inputs()):
            if src is not None:
                lines.append(f"  {src.name()} --> {node.name()} (input {i})")
    lines.append("=" * 70)

    return "\n".join(lines)

# ----------------------------------------------------------------------
# Pop-up window
# ----------------------------------------------------------------------

class DumpWindow(QtWidgets.QWidget):
    def __init__(self, text):
        super(DumpWindow, self).__init__()
        self.setWindowTitle("Network Dump")
        self.resize(800, 600)
        self.setWindowFlags(QtCore.Qt.Window)

        layout = QtWidgets.QVBoxLayout(self)

        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        # Monospace font so the indentation lines up.
        font = self.text_edit.font()
        font.setFamily("Courier New")
        self.text_edit.setFont(font)
        layout.addWidget(self.text_edit)

        btn_row = QtWidgets.QHBoxLayout()
        copy_btn = QtWidgets.QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def copy_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setText(self.text_edit.toPlainText())

# Keep a reference so the window isn't garbage-collected and closed instantly.
_dump_text = build_dump()
_dump_window = DumpWindow(_dump_text)
_dump_window.setParent(hou.qt.mainWindow(), QtCore.Qt.Window)
_dump_window.show()
