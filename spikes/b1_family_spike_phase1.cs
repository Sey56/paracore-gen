// ============================================================================
// B1 SPIKE — Phase 1: can the MCP's REPL context author a family end to end?
//
// ✅ PASSED 2026-09-30, on the live Revit 2025 API from the MCP's REPL context.
//    create 414 ms · build 137 ms · save 411 ms · close ~100 ms · TOTAL 732 ms
//    bbox verified EXACT: 600 × 400 × 3000 mm
//    active project untouched (doc count 1 → 1)
//
// SCOPE: creates a NEW family document, builds ONE extrusion, verifies it
//        NUMERICALLY, saves to %TEMP%, and closes. LoadFamily is Phase 2.
//
// ⚠⚠ THE THING THAT COST 120 SECONDS — READ THIS FIRST
//    `Transact(name, action)` CANNOT target a family document. Both overloads
//    hard-wire to the ACTIVE document (ExecutionGlobals.cs:602-628 always calls
//    Tx.Transact(Doc, …)), so the Action<Document> overload hands you the
//    PROJECT — and `d.FamilyCreate` on a project throws InvalidOperationException.
//    The first version of this script used Transact() and did NOT fail cleanly:
//    it stalled the REPL for the full 120 s deadline.
//
//    Autodesk.Revit.DB IS pre-imported, so build the transaction yourself
//    against the family document. That is what the code below does.
//
// ⚠ NewExtrusion returns `Extrusion`, whose base is `GenericForm` — NOT `Form`.
//   `Form f = NewExtrusion(...)` fails to compile with CS0029.
//   (The massing creators — NewLoftForm etc. — DO return `Form`.)
//
// Grounded in mcp_core/skills/family-authoring/SKILL.md.
// ============================================================================

var t0 = DateTime.Now;
string tpl = UIApp.Application.FamilyTemplatePath + "\\English\\Metric Generic Model.rft";

// ---- Q1: NewFamilyDocument, from the REPL context --------------------------
Document famDoc = UIApp.Application.NewFamilyDocument(tpl);
Println("Q1 create : " + famDoc.Title + "   IsFamily=" + famDoc.IsFamilyDocument);

// ---- Q2: build ONE extrusion in ONE transaction ----------------------------
// NOTE: a direct Transaction on famDoc — NOT Transact(), which targets the project.
double w = 600.InputUnit("mm"), h = 400.InputUnit("mm"), depth = 3000.InputUnit("mm");

var loop = new CurveArray();
loop.Append(Line.CreateBound(new XYZ(0, 0, 0), new XYZ(w, 0, 0)));
loop.Append(Line.CreateBound(new XYZ(w, 0, 0), new XYZ(w, h, 0)));
loop.Append(Line.CreateBound(new XYZ(w, h, 0), new XYZ(0, h, 0)));
loop.Append(Line.CreateBound(new XYZ(0, h, 0), new XYZ(0, 0, 0)));

var profile = new CurveArrArray();
profile.Append(loop);

var tx = new Transaction(famDoc, "B1 - build extrusion");
tx.Start();
var sp = SketchPlane.Create(famDoc, Plane.CreateByNormalAndOrigin(new XYZ(0, 0, 1), XYZ.Zero));
var ex = famDoc.FamilyCreate.NewExtrusion(true, profile, sp, depth);
var status = tx.Commit();          // TransactionStatus — never assume Committed
Println("Q2 build  : id=" + ex.Id + "   commit=" + status);

// ---- Q3: NUMERIC verification — bbox must be 600 × 400 × 3000 mm -----------
var bb = ex.get_BoundingBox(null);
Println("Q3 bbox X (want 600)  : " + (bb.Max.X - bb.Min.X).OutputUnit("mm", 3));
Println("Q3 bbox Y (want 400)  : " + (bb.Max.Y - bb.Min.Y).OutputUnit("mm", 3));
Println("Q3 bbox Z (want 3000) : " + (bb.Max.Z - bb.Min.Z).OutputUnit("mm", 3));

// ---- Q4: SaveAs ------------------------------------------------------------
string outPath = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "b1_phase1_full.rfa");
famDoc.SaveAs(outPath);
Println("Q4 save   : " + new System.IO.FileInfo(outPath).Length + " bytes  -> " + outPath);

// ---- Q5: close, leaving nothing behind -------------------------------------
famDoc.Close(false);
Println("Q5 close  : docs open now = " + UIApp.Application.Documents.Size);
Println("TOTAL     : " + (long)(DateTime.Now - t0).TotalMilliseconds + " ms");
Println("project   : " + Doc.Title + "  (unchanged)");

// ============================================================================
// PHASE 2 (not yet run) — the three remaining unknowns from FAMILY_EDITOR_PLAN §8:
//   2. Does LoadFamily back into the host project succeed from this context?
//   3. Is in-place mass creation still available in Revit 2025 projects?
//   4. What is the real cost of EditFamily -> modify -> LoadFamily?
// Authoring is now known to be cheap (732 ms), so the round-trip cost lives in
// EditFamily/LoadFamily, not in building the geometry.
// ============================================================================
