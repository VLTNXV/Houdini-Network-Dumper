import hou
import re
import traceback
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

# Value patterns that look personal/sensitive. Redaction is VALUE-based:
# we only blank out a value if the value itself matches one of these. We do
# NOT redact based on parameter name alone, because that hides harmless,
# useful data like group names ("top_pnt") and VEX snippets.
#
# Note: $HIP and other Houdini project variables are intentionally NOT
# treated as personal — they're project-relative and useful for context.
_PERSONAL_PATTERNS = (
    r"[A-Za-z]:\\",                                      # Windows drive path  C:\  D:\
    r"\\Users\\",                                        # Windows user dir
    r"/Users/",                                          # macOS user dir
    r"/home/",                                           # Linux user dir
    r"\\\\[^\\]+\\",                                     # UNC path  \\server\share
    r"\$HOME\b",                                         # $HOME var
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",  # email address
    r"\b[A-Za-z0-9]{40,}\b",                            # very long token-like strings
)
_PERSONAL_RE = re.compile("|".join(_PERSONAL_PATTERNS))


def looks_personal(val):
    """True if the VALUE looks personal/sensitive."""
    return bool(_PERSONAL_RE.search(str(val)))


def redact(val):
    """Redact a value only if the value itself looks personal."""
    s = str(val)
    if looks_personal(s):
        return "<redacted-personal>"
    return s


def parm_line(parm):
    try:
        try:
            expr = parm.expression()
            raw = parm.rawValue()
        except Exception:
            expr = None
            raw = None

        if ONLY_NON_DEFAULT and parm.isAtDefault() and not expr:
            return None

        # Tag user-defined (spare) parameters so HDA / promoted controls are
        # distinguishable from a node's built-in parameters.
        try:
            spare = " [spare]" if parm.isSpare() else ""
        except Exception:
            spare = ""

        if expr:
            try:
                lang = "py" if parm.expressionLanguage() == hou.exprLanguage.Python else "hscript"
            except Exception:
                lang = "expr"
            # Redact the raw expression text AND its evaluated result, since an
            # expression can evaluate to something sensitive even if its text isn't.
            raw_red = redact(raw)
            try:
                eval_red = redact(parm.eval())
            except Exception:
                eval_red = "<eval-failed>"
            return f"      {parm.name()}{spare} = [{lang} expr] {raw_red}  (-> {eval_red})"
        else:
            return f"      {parm.name()}{spare} = {redact(parm.eval())}"
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

    # Node comment / annotation — useful intent signal if present.
    try:
        c = node.comment()
        if c:
            out.append(f"  comment: {redact(c)}")
    except Exception:
        pass

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

    # Outputs (including those going to nodes outside the selection), so the
    # boundary of a partial selection is visible.
    try:
        outputs = node.outputs()
        if outputs:
            olines = []
            for dst in outputs:
                tag = "" if dst.path() in all_selected_paths else "  [outside selection]"
                olines.append(f"    --> {dst.path()}{tag}")
            if olines:
                out.append("  outputs:")
                out.extend(olines)
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
    lines.append("NOTE: redaction is best-effort. Eyeball the output before sharing publicly.")
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


# Build the dump defensively so a failure still shows a window with the
# traceback instead of silently doing nothing.
try:
    _dump_text = build_dump()
except Exception:
    _dump_text = "Network dump failed:\n\n" + traceback.format_exc()

_dump_window = DumpWindow(_dump_text)
_dump_window.setParent(hou.qt.mainWindow(), QtCore.Qt.Window)
_dump_window.show()
