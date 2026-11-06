import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "spikes"))
import _harness  # noqa: E402

t = _harness.boot()

q = [
    ("ownership of Fire Rating via the parameter SET",
     'var w = GetElements("Walls").First(); '
     'var p = w.Parameters.Cast<Parameter>().FirstOrDefault(x => x.Definition.Name == "Fire Rating"); '
     'Println("FOUND=" + (p != null)); '
     'if (p != null) { '
     'Println("OWNER_TYPE=" + (p.Element == null ? "null" : p.Element.GetType().Name)); '
     'Println("IS_TYPEPARAM=" + p.IsTypeParameter()); '
     'Println("W_TYPEID=" + w.GetTypeId().ToString()); '
     'Println("OWNER_ID=" + (p.Element == null ? "-" : p.Element.Id.ToString())); '
     'Println("BLAST=" + w.TypeInstanceCount()); '
     'Println("UI=[" + (p.AsValueString() ?? "") + "]"); }'),
    ("which walls carry a Fire Rating value",
     'foreach (var w in GetElements("Walls")) '
     'Println("ID=" + w.Id + " TYPE=" + w.GetTypeId() + " FR=[" + w.GetStr("Fire Rating") + "]");'),
    ("Absorptance ownership (the other one the reviewer used)",
     'var w = GetElements("Walls").First(); '
     'var p = w.Parameters.Cast<Parameter>().FirstOrDefault(x => x.Definition.Name == "Absorptance"); '
     'Println("FOUND=" + (p != null)); '
     'if (p != null) { Println("OWNER_TYPE=" + (p.Element == null ? "null" : p.Element.GetType().Name)); '
     'Println("IS_TYPEPARAM=" + p.IsTypeParameter()); }'),
]

for label, code in q:
    print("=====", label)
    try:
        print(t.execute_dynamic_query(code, "type-write probe 2"))
    except Exception as exc:  # noqa: BLE001
        print("RAISED", type(exc).__name__, exc)
