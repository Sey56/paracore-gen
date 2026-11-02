"""
MEASURE the transaction granularity contract — one transaction per write vs one per loop.

The contract, as stated by the operator and implemented by TransactionLoopGuard:

  * a SINGLE el.SetVal(...)          -> its own transaction (correct, convenient)
  * a LOOP of el.SetVal(...)         -> ONE transaction PER write  (the footgun)
  * the same loop inside Transact()  -> ONE transaction, the inner ones suppressed
  * a COLLECTION .SetParam(...)      -> ONE transaction, built in

⚠ "Suppressed" is the claim that needs proof, not belief. The mechanism is
`if (doc.IsModifiable) Action(); else Tx.Transact(...)` — so the discriminator is
whether the document reports itself modifiable at the moment of the write.

METHOD: subscribe to DocumentChanged from INSIDE the script and record every
transaction name Revit reports. That is Revit's own record of what committed, not
the engine's opinion of what it intended.

⚠ The probe WRITES. It restores every Comments value by ELEMENT ID and then
asserts the restore, because a probe that leaves the model dirty is a defect of
its own (that already happened once in this repo).
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _harness

MARK = "TX-GRAN"

SNAPSHOT = r'''
var sb = new System.Text.StringBuilder();
int n = 0;
foreach (var w in GetElements("Walls")) {
    if (n++ >= 3) break;
    sb.Append(w.Id.Value + "=" + w.GetStr("Comments") + "\n");
}
return sb.ToString();
'''

# ── A: ONE write, one element, no enclosing transaction ──────────────────────
A = r'''
var w = GetElements("Walls").First();
var names = new System.Collections.Generic.List<string>();
EventHandler<Autodesk.Revit.DB.Events.DocumentChangedEventArgs> h = (s, a) => {
    foreach (var t in a.GetTransactionNames()) { if (!string.IsNullOrEmpty(t)) names.Add(t); }
};
Doc.Application.DocumentChanged += h;
w.SetVal("Comments", "MARK-A");
Doc.Application.DocumentChanged -= h;
return "count=" + names.Count + " names=[" + string.Join("|", names) + "]";
'''

# ── B: THREE writes in a loop, NO enclosing transaction ──────────────────────
B = r'''
var ws = GetElements("Walls").Take(3).ToList();
var names = new System.Collections.Generic.List<string>();
EventHandler<Autodesk.Revit.DB.Events.DocumentChangedEventArgs> h = (s, a) => {
    foreach (var t in a.GetTransactionNames()) { if (!string.IsNullOrEmpty(t)) names.Add(t); }
};
Doc.Application.DocumentChanged += h;
foreach (var w in ws) { w.SetVal("Comments", "MARK-B"); }
Doc.Application.DocumentChanged -= h;
return "count=" + names.Count + " names=[" + string.Join("|", names) + "]";
'''

# ── C: the SAME loop inside Transact ─────────────────────────────────────────
C = r'''
var ws = GetElements("Walls").Take(3).ToList();
var names = new System.Collections.Generic.List<string>();
EventHandler<Autodesk.Revit.DB.Events.DocumentChangedEventArgs> h = (s, a) => {
    foreach (var t in a.GetTransactionNames()) { if (!string.IsNullOrEmpty(t)) names.Add(t); }
};
Doc.Application.DocumentChanged += h;
Transact("loop inside Transact", () => { foreach (var w in ws) { w.SetVal("Comments", "MARK-C"); } });
Doc.Application.DocumentChanged -= h;
return "count=" + names.Count + " names=[" + string.Join("|", names) + "]";
'''

# ── D: collection SetParam ───────────────────────────────────────────────────
D = r'''
var ws = GetElements("Walls").Take(3).ToList();
var names = new System.Collections.Generic.List<string>();
EventHandler<Autodesk.Revit.DB.Events.DocumentChangedEventArgs> h = (s, a) => {
    foreach (var t in a.GetTransactionNames()) { if (!string.IsNullOrEmpty(t)) names.Add(t); }
};
Doc.Application.DocumentChanged += h;
ws.SetParam("Comments", "MARK-D");
Doc.Application.DocumentChanged -= h;
return "count=" + names.Count + " names=[" + string.Join("|", names) + "]";
'''


def run(t, code, label):
    out = t.execute_dynamic_query(code, label)
    return out


def kv(out):
    """Pull `count=N` out of the formatted tool output."""
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("count="):
            n = int(s.split("count=")[1].split()[0])
            return n, s
    return None, out.strip().splitlines()[-1] if out.strip() else "<empty>"


def main():
    t = _harness.boot(start_watcher=False)
    results = []

    before = run(t, SNAPSHOT, "snapshot comments")
    print("=== BEFORE ===")
    print(before.strip()[:600])

    cases = [
        ("A one write, no Transact", A, 1, "exactly one transaction"),
        ("B loop of 3, no Transact", B, 3, "three transactions — the footgun"),
        ("C loop of 3 in Transact", C, 1, "inner transactions suppressed"),
        ("D collection SetParam", D, 1, "one built-in transaction"),
    ]

    for label, code, want, why in cases:
        out = run(t, code, label)
        n, detail = kv(out)
        ok = (n == want)
        results.append((label, "PASS" if ok else "FAIL", "got %s want %s — %s" % (n, want, detail[:120])))

    # ── restore by id, then ASSERT ──────────────────────────────────────────
    restore_lines = []
    for line in before.splitlines():
        line = line.strip()
        if "=" in line and line.split("=")[0].isdigit():
            wid, val = line.split("=", 1)
            restore_lines.append('var e%s = Doc.GetElement(new ElementId(%s)); if (e%s != null) e%s.SetVal("Comments", "%s");'
                                 % (wid, wid, wid, wid, val.replace('"', '\\"')))
    restore = "\n".join(restore_lines) + r'''
string bad = "";
foreach (var w in GetElements("Walls")) {
    string c = w.GetStr("Comments");
    if (c.StartsWith("MARK-")) bad += w.Id.Value + "=" + c + "; ";
}
return bad.Length == 0 ? "CLEAN" : ("DIRTY: " + bad);
'''
    out = run(t, restore, "restore")
    results.append(("E model restored by id", "PASS" if "CLEAN" in out else "FAIL", " ".join(out.split())[-120:]))

    print("\n=== RESULTS ===")
    for label, verdict, detail in results:
        print("%-4s %-30s %s" % (verdict, label, detail))
    failed = [r for r in results if r[1] != "PASS"]
    print("\n%d passed, %d failed" % (len(results) - len(failed), len(failed)))


if __name__ == "__main__":
    main()
