---
name: family-authoring
description: Creating and editing loadable families (.rfa) — NewFamilyDocument, EditFamily, extrusions, revolutions, sweeps, blends, FamilyManager parameters and types
---

# Family Authoring

Build and edit loadable families (`.rfa`) — extrusions, revolutions, sweeps, blends, plus the
parameters and types that drive them.

All signatures on this page were read off the live Revit 2025 API by reflection. Where a
behaviour is asserted beyond a signature, it is marked.

## READ THIS FIRST — `Doc` is almost certainly a project document

On a **project** document, both of these **throw `InvalidOperationException`**. They do **not**
return `null`, so a null-check will not save you:

| Call | On a project document |
|:---|:---|
| `Doc.FamilyCreate` | `InvalidOperationException` |
| `Doc.FamilyManager` | `InvalidOperationException` |

Verified live: `Doc.IsFamilyDocument == False` → both throw.

So you cannot build family geometry against `Doc`. Get a **family document** first.

## Route A — create a new family from a template

```csharp
// FamilyTemplatePath verified live: C:\ProgramData\Autodesk\RVT 2025\Family Templates
// NOTE: templates live in a LANGUAGE subfolder — "\English\", "\English-Imperial\", etc.
// They are NOT directly under FamilyTemplatePath.
string tpl = UIApp.Application.FamilyTemplatePath + "\\English\\Metric Generic Model.rft";
Document famDoc = UIApp.Application.NewFamilyDocument(tpl);
```

Verified template paths under that root (Revit 2025, English install):

| Template | Relative path |
|:---|:---|
| Generic model | `\English\Metric Generic Model.rft` |
| Conceptual mass | `\English\Conceptual Mass\Metric Mass.rft` |
| Adaptive component | `\English\Metric Generic Model Adaptive.rft` |
| Face based | `\English\Metric Generic Model face based.rft` |
| Line based | `\English\Metric Generic Model line based.rft` |
| Pattern based | `\English\Metric Generic Model Pattern Based.rft` |

Other language packs sit alongside (`\Italian\`, `\Portuguese\`, …). On a non-English install
the folder and file names differ, so list `FamilyTemplatePath` first if the path above 404s.

## Route B — edit a family already loaded in the project

```csharp
var door  = GetElements<FamilyInstance>("Doors").FirstOrDefault();
var fam   = door.Symbol.Family;      // → Family
Document famDoc = Doc.EditFamily(fam);   // → Document (a NEW document, not the active one)
```

`famDoc` is a **separate document**. `Doc` still points at the project. Everything below
operates on `famDoc`.

## Transactions — ONE per build

⚠⚠ **`Transact()` CANNOT target a family document. Use `Transaction` directly.**

`Transact(name, action)` is hard-wired to the **active** document. `ExecutionGlobals.Transact`
always calls `Tx.Transact(Doc, …)` — even for the `Action<Document>` overload, whose `d` is
therefore **`Doc`, the project**, not your family document. So `d.FamilyCreate` is called on a
project document, where it throws `InvalidOperationException`.

**The doc-access overload is not a way to reach a second document.** (Measured 2026-09-30: a
spike written that way did not fail cleanly — it **stalled the REPL for the full 120 s
deadline**. See the B1 spike in `spikes/`.)

`Autodesk.Revit.DB` is pre-imported, so build the transaction yourself against the family document:

```csharp
var tx = new Transaction(famDoc, "Build family");
tx.Start();
// … all geometry, parameters and types …
var status = tx.Commit();      // TransactionStatus — check it, do not assume Committed
```

**SPEED RULE — build the whole family in ONE transaction.** Every transaction is a regeneration
plus an undo entry. Wrapping each `New*` call in its own transaction regenerates the family once
per primitive. Put all geometry, parameters and types in a single block.

Note that `SketchPlane.Create(...)` creates an element, so it needs the transaction too. Plain
geometry (`Line.CreateBound`, `Plane.CreateByNormalAndOrigin`, `CurveArray`) does not.

**Verified end to end 2026-09-30** — create → build → verify → save → close, **732 ms total**,
on the live Revit 2025 API from the MCP's REPL context.

## Profile plumbing (verified)

`NewExtrusion` and `NewRevolution` take a `CurveArrArray`, not a `CurveArray`. A
`CurveArrArray` is a list of closed loops; each loop is a `CurveArray`.

```csharp
CurveArray    loop;   // ctor()            → Append(Curve)
CurveArrArray prof;   // ctor()            → Append(CurveArray)
ReferenceArray      ; // ctor()            → Append(Reference)
ReferencePointArray ; // ctor()            → Append(ReferencePoint)

SketchPlane.Create(Document, Plane)
SketchPlane.Create(Document, Reference planarFaceReference)
SketchPlane.Create(Document, ElementId datumId)

Plane.CreateByNormalAndOrigin(XYZ normal, XYZ origin)
Plane.CreateByThreePoints(XYZ p1, XYZ p2, XYZ p3)
Plane.Create(Frame frameOfReference)
```

## FamilyItemFactory — reachable as `Doc.FamilyCreate`

The family document's factory. 30 public methods; the geometry ones:

| Method | Signature |
|:---|:---|
| `NewExtrusion` | `Extrusion NewExtrusion(bool isSolid, CurveArrArray profile, SketchPlane sketchPlane, double end)` |
| `NewRevolution` | `Revolution NewRevolution(bool isSolid, CurveArrArray profile, SketchPlane sketchPlane, Line axis, double startAngle, double endAngle)` |
| `NewBlend` | `Blend NewBlend(bool isSolid, CurveArray profile1, CurveArray profile2, SketchPlane sketchPlane)` |
| `NewSweep` | `Sweep NewSweep(bool isSolid, CurveArray path, SketchPlane pathPlane, SweepProfile profile, int profileLocationCurveIndex, ProfilePlaneLocation profilePlaneLocation)` |
| `NewSweep` | `Sweep NewSweep(bool isSolid, ReferenceArray path, SweepProfile profile, int profileLocationCurveIndex, ProfilePlaneLocation profilePlaneLocation)` |
| `NewSweptBlend` | `SweptBlend NewSweptBlend(bool isSolid, Curve path, SketchPlane pathPlane, SweepProfile bottomProfile, SweepProfile topProfile)` |
| `NewSweptBlend` | `SweptBlend NewSweptBlend(bool isSolid, Reference path, SweepProfile bottomProfile, SweepProfile topProfile)` |
| `NewOpening` | `Opening NewOpening(Element host, CurveArray profile)` |
| `NewModelText` | `ModelText NewModelText(string text, ModelTextType modelTextType, SketchPlane sketchPlane, XYZ position, HorizontalAlign horizontalAlign, double depth)` |
| `NewSymbolicCurve` | `SymbolicCurve NewSymbolicCurve(Curve curve, SketchPlane sketchPlane)` |
| `NewControl` | `Control NewControl(ControlShape controlShape, View view, XYZ origin)` |
| `NewReferencePoint` | `ReferencePoint NewReferencePoint(XYZ)` / `(Transform)` / `(PointElementReference)` |
| `NewCurveByPoints` | `CurveByPoints NewCurveByPoints(ReferencePointArray points)` |

Enums (verified values):
`ProfilePlaneLocation` = `Start, MidPoint, End` · `HorizontalAlign` = `Left, Center, Right` ·
`ControlShape` = `VerticalArrow, HorizontalArrow, DoubleVerticalArrow, DoubleHorizontalArrow`

Dimensions are also on this factory, if the family needs them:
`NewLinearDimension(View, Line, ReferenceArray[, DimensionType])`,
`NewAngularDimension(View, Arc, Reference, Reference[, DimensionType])`,
`NewArcLengthDimension(View, Arc, Reference, Reference, Reference[, DimensionType])`,
`NewRadialDimension(View, Reference, XYZ[, DimensionType])`,
`NewDiameterDimension(View, Reference, XYZ)`.

### Worked example — a rectangular extrusion

```csharp
double w = 600.InputUnit("mm"), h = 400.InputUnit("mm"), depth = 3000.InputUnit("mm");

// Geometry objects — no transaction needed
var loop = new CurveArray();
loop.Append(Line.CreateBound(new XYZ(0, 0, 0), new XYZ(w, 0, 0)));
loop.Append(Line.CreateBound(new XYZ(w, 0, 0), new XYZ(w, h, 0)));
loop.Append(Line.CreateBound(new XYZ(w, h, 0), new XYZ(0, h, 0)));
loop.Append(Line.CreateBound(new XYZ(0, h, 0), new XYZ(0, 0, 0)));

var profile = new CurveArrArray();
profile.Append(loop);

Document famDoc = UIApp.Application.NewFamilyDocument(
    UIApp.Application.FamilyTemplatePath + "\\English\\Metric Generic Model.rft");

// ONE transaction for the whole build — on the FAMILY document, not via Transact()
var tx = new Transaction(famDoc, "Build family");
tx.Start();
var sp = SketchPlane.Create(famDoc, Plane.CreateByNormalAndOrigin(new XYZ(0, 0, 1), XYZ.Zero));
var ex = famDoc.FamilyCreate.NewExtrusion(true, profile, sp, depth);
tx.Commit();
```

`NewExtrusion` returns **`Extrusion`**, whose base class is **`GenericForm`** — it is *not* a
`Form` and does not implicitly convert to one. Declaring `Form f = NewExtrusion(...)` fails to
compile (`CS0029`). The massing creators (`NewLoftForm` etc.) *do* return `Form`.

`SweepProfile` is abstract. Build a concrete one from the application factory:

```csharp
// UIApp.Application.Create → Autodesk.Revit.Creation.Application
CurveLoopsProfile     p1 = UIApp.Application.Create.NewCurveLoopsProfile(curveArrArray);
FamilySymbolProfile   p2 = UIApp.Application.Create.NewFamilySymbolProfile(familySymbol);
```

## FamilyManager — reachable as `Doc.FamilyManager`

40 public methods. This is where family **types** and **parameters** live.

### Types

```csharp
FamilyType  NewType(string typeName);
void        DeleteCurrentType();
void        RenameCurrentType(string typeName);
FamilyType  CurrentType { get; set; }
FamilyTypeSet Types { get; }
```

### Parameters

```csharp
FamilyParameter AddParameter(string parameterName, ForgeTypeId groupTypeId, Category familyCategory, bool isInstance);
FamilyParameter AddParameter(string parameterName, ForgeTypeId groupTypeId, ForgeTypeId specTypeId, bool isInstance);
FamilyParameter AddParameter(ExternalDefinition familyDefinition, ForgeTypeId groupTypeId, bool isInstance);
void RemoveParameter(FamilyParameter p);
void RenameParameter(FamilyParameter p, string name);
FamilyParameter ReplaceParameter(FamilyParameter current, string parameterName, ForgeTypeId groupTypeId, bool isInstance);
FamilyParameterSet Parameters { get; }
FamilyParameter get_Parameter(string parameterName);      // also (Guid) (Definition) (BuiltInParameter)
FamilyParameter GetParameter(ForgeTypeId parameterTypeId);
void SetDescription(FamilyParameter p, string description);
```

Note the modern overloads take **`ForgeTypeId`**, not `BuiltInParameterGroup` /
`ParameterType`. That is the Revit 2022+ API and it is what Revit 2025 exposes.

### Setting values, instance/type, formulas

```csharp
void Set(FamilyParameter p, double value);      // also (ElementId) (string) (int)
void SetValueString(FamilyParameter p, string value);
void SetFormula(FamilyParameter p, string formula);
void MakeInstance(FamilyParameter p);           // instance parameter
void MakeType(FamilyParameter p);               // type parameter
void MakeReporting(FamilyParameter p);
void MakeNonReporting(FamilyParameter p);
```

### Association and locking

```csharp
void AssociateElementParameterToFamilyParameter(Parameter elementParameter, FamilyParameter familyParameter);
bool CanElementParameterBeAssociated(Parameter elementParameter);
FamilyParameter GetAssociatedFamilyParameter(Parameter elementParameter);
bool IsParameterLockable(FamilyParameter p);
bool IsParameterLocked(FamilyParameter p);
void SetParameterLocked(FamilyParameter p, bool locked);
void ReorderParameters(IList<FamilyParameter> parameters);
void SortParameters(ParametersOrder order);
```

### Worked example — add a driving parameter, then a second type

```csharp
var tx2 = new Transaction(famDoc, "Add Width parameter");
tx2.Start();
var fm = famDoc.FamilyManager;

// ⚠⚠ A fresh family document has NO current type. NewType() must come FIRST, or every Set()
//    throws InvalidOperationException: "There is no current type."
fm.CurrentType = fm.NewType("Standard 450");

var width = fm.AddParameter("Width", GroupTypeId.Geometry,
                            SpecTypeId.Length, false);   // false = type parameter
fm.Set(width, 900.InputUnit("mm"));
tx2.Commit();
```

Cautions on that example:

- **Use the `GroupTypeId` / `SpecTypeId` static properties — never a hand-written string.**
  Verified live on Revit 2025: `GroupTypeId.Geometry` →
  `autodesk.parameter.group:dimensions-1.0.0` (the *Dimensions* group),
  `GroupTypeId.Constraints` → `…:constraints-1.0.0`,
  `SpecTypeId.Length` → `autodesk.spec.aec:length-2.0.1`. The old
  `new ForgeTypeId("autodesk.parameter.group:pg_geometry")` string was **never verified** and
  is not the right id. `fm.IsUserAssignableParameterGroup(GroupTypeId.Geometry)` → `True`.
- `fm.Set(...)` must run **inside** a transaction, and `CurrentType` must be set before
  setting values for a specific type.
- **`FamilyParameter` has no value accessor of its own.** Read values through the *type*:
  `fm.CurrentType.AsDouble(p)` (returns `double?` — unwrap `.Value`), `AsString`,
  `AsInteger`, `AsElementId`, `AsValueString`. Calling `p.AsValueString()` directly on the
  `FamilyParameter` does **not** compile (`CS1061`) — `AsValueString` lives on `FamilyType`.

## Making it parametric — parameters alone do nothing

Adding a parameter does **not** make geometry follow it. A family is parametric only where
geometry is **constrained to** the parameter. Three mechanisms work through this API; all
verified live on Revit 2025.

**1. Extrusion depth → associate `Extrusion Start` / `Extrusion End`.**

An `Extrusion` exposes these as ordinary parameters and `FamilyManager` accepts them:

```csharp
fm.AssociateElementParameterToFamilyParameter(FindP(extrusion, "Extrusion End"), heightParam);
```

Discover what is associatable rather than guessing:

```csharp
foreach (Parameter p in extrusion.Parameters)
    if (fm.CanElementParameterBeAssociated(p)) Println(p.Definition.Name);
// → Visible, Material, Extrusion End, Extrusion Start
```

⚠ **Offsets are measured from the SKETCH PLANE, not the family origin.** Build every form on a
sketch plane at `Z = 0` and let the offsets place it vertically. A plane already at `Z = SH`
double-counts, and the form lands at `2·SH`.

⚠⚠ **In a stacked family, each form's start binds to the height of the form BELOW it — never to one
shared height.** Because every form sits on the same `Z = 0` plane, its vertical position comes
*entirely* from the `Extrusion Start` / `Extrusion End` associations. For legs → frame → seat →
arms → back, the correct chain is:

| form | `Extrusion Start` | `Extrusion End` |
|:---|:---|:---|
| legs | *(literal)* `0` | `Leg Height` |
| frame | `Leg Height` | `Frame Top Height` |
| seat / arms / back | **`Frame Top Height`** | `Seat Height` / `Arm Top Height` / `Overall Height` |

Binding an *upper* form's start to `Leg Height` is the defect: it begins at the floor of the frame
and passes straight through it. Measured 2026-10-01 on a generated 3-seater sofa — both armrests'
`Extrusion Start` were associated to `Leg Height` (150) instead of `Frame Top Height` (300), so they
started 150 mm low and intersected the frame. They were the **only 2 of 11 forms** that were wrong,
which is why it reads as a modelling slip rather than a systemic error.

**Prove the binding — do not read the numbers.** `AsValueString()` on an associated parameter
returns the **resolved** value, so a hardcoded `300` and a bound `300` are indistinguishable. Only
the association tells you which you have:

```csharp
var fm = famDoc.FamilyManager;
foreach (var e in GetElements<Extrusion>()) {
    var p  = e.get_Parameter(BuiltInParameter.EXTRUSION_START_PARAM);
    var fp = fm.GetAssociatedFamilyParameter(p);       // null => a LITERAL value
    Println("id" + e.Id.IntegerValue + "  start<-" + (fp == null ? "(LITERAL)" : fp.Definition.Name));
}
// → id2848  start<-Leg Height          id2863  start<-Frame Top Height
```

A `(LITERAL)` is not automatically wrong — a leg on the family origin legitimately has a literal `0`
start. It is wrong when an **upper** form reads `(LITERAL)`, or binds to a height *below* the form it
sits on.

Pair it with a bounding-box overlap count, which catches the symptom the binding check alone misses:

```csharp
// 0 intersecting pairs == the stack is disjoint. Forms that merely TOUCH at a shared Z
// (frame ends 300, seat starts 300) must NOT count — hence the strict < with a tolerance.
var ids = new List<int>();  var bbs = new List<BoundingBoxXYZ>();
foreach (var e in GetElements<Extrusion>()) { ids.Add(e.Id.IntegerValue); bbs.Add(e.get_BoundingBox(null)); }
int ov = 0;
for (int i = 0; i < bbs.Count; i++)
  for (int j = i + 1; j < bbs.Count; j++) {
    var a = bbs[i]; var b = bbs[j];
    if (a == null || b == null) continue;
    if (a.Min.X < b.Max.X - 1e-6 && b.Min.X < a.Max.X - 1e-6 &&
        a.Min.Y < b.Max.Y - 1e-6 && b.Min.Y < a.Max.Y - 1e-6 &&
        a.Min.Z < b.Max.Z - 1e-6 && b.Min.Z < a.Max.Z - 1e-6) {
      ov++; Println("OVERLAP " + ids[i] + " x " + ids[j]);
    }
  }
Println("INTERSECTING PAIRS = " + ov);
```

⚠ That comparison is only valid **because the recipe puts every form on one `Z = 0` sketch plane**,
where the extrusion's own frame and model space coincide. If forms sit on *different* sketch planes,
`get_BoundingBox(null)` is in each form's own frame and the test is meaningless — walk
`solid.Faces → EdgeLoops → Edge.AsCurve().GetEndPoint(k)` instead (see the warning below).

**2. Plan profile (width / depth / thickness) → a driving dimension, between REFERENCE PLANES.**

The planes are the skeleton, the labelled dimension between them carries the parameter, and the
geometry is aligned to the planes (step 3):

```csharp
// ⚠ The skeleton must ALREADY EXIST and be COMMITTED before this runs — see the trap below.
//   Used in the same transaction that created the planes, it throws
//   "The references are not geometric references."
var refs = new ReferenceArray();
refs.Append(leftPlane.GetReference());     // a ReferencePlane
refs.Append(rightPlane.GetReference());
var d = famDoc.FamilyCreate.NewLinearDimension(planView, line, refs);
d.FamilyLabel = widthParam;                // ← this is what makes it DRIVE
```

**Fallback — dimension the extrusion's own opposite faces.** Use this when there is no skeleton to
dimension. It costs one dimension per face that must move:

```csharp
// ⚠⚠ Face.Reference is NULL unless ComputeReferences is true — the #1 silent failure here.
var opt = new Options(); opt.ComputeReferences = true;
Reference F(Element e, XYZ n)
{
    foreach (var g in e.get_Geometry(opt))
        if (g is Solid s)
            foreach (Face fc in s.Faces)
                if (fc is PlanarFace pf && pf.FaceNormal.IsAlmostEqualTo(n)) return pf.Reference;
    return null;
}

var faceRefs = new ReferenceArray();
faceRefs.Append(F(seat, new XYZ(-1, 0, 0)));   // left face
faceRefs.Append(F(seat, new XYZ( 1, 0, 0)));   // right face
var df = famDoc.FamilyCreate.NewLinearDimension(planView, line, faceRefs);
df.FamilyLabel = widthParam;
```

`Dimension.FamilyLabel` is a settable `FamilyParameter` (`CanWrite = true`). Label several
dimensions with the same parameter to drive several forms together.

⚠ Reading `FamilyLabel` off a dimension that **cannot** be labelled throws
`InvalidOperationException: This dimension can not be labeled` — e.g. a template's own
dimensions. Wrap such a read if you are enumerating.

**3. Positioning one form against another → `NewAlignment`.**

⚠⚠ **A reference plane's `Reference` is NOT a geometric reference until the document regenerates.**
This one timing detail is what makes the reference-plane workflow *look* impossible. Measured
2026-10-01 on Revit 2025, three cases in one document:

| case | construction | result |
|:---|:---|:---|
| A | planes created → **committed** → dimensioned in a *new* transaction | ✅ works |
| B | planes created → **`doc.Regenerate()`** → dimensioned in the *same* transaction | ✅ works |
| C | planes created → dimensioned in the *same* transaction, **no regenerate** | ❌ `ArgumentException: The references are not geometric references. Parameter name: references` |

**So: build the skeleton, commit (or call `Regenerate()`), and only then dimension or align it.**
Nothing else is wrong with reference planes — they are ordinary, fully usable constraint targets:

| operation | result |
|:---|:---|
| dim reference plane ↔ reference plane (after regenerate) | ✅ **works, drives** |
| align reference plane ↔ sketch line | ✅ **works** |
| align reference plane ↔ solid face | ✅ **works** |
| **dim solid face ↔ solid face** | ✅ **works, drives** |
| **align solid face ↔ solid face** | ✅ **works, drives** |

⚠ Three ways this was mis-diagnosed, each worth avoiding:

- **The message names neither the plane nor the transaction.** `The references are not geometric
  references` reads like a bad reference; it is a *timing* problem. Log `ex.Message`, not just
  `ex.GetType().Name` — `ArgumentException` alone is consistent with a dozen different causes, and
  discarding the message is what turned a one-line fix into a false "API boundary".
- **Coincident planes give a second, different failure.** Two planes at the *same* offset throw
  `ArgumentException: One of the conditions for the inputs was not satisfied` (a degenerate distance).
  That is a real geometry error, not an API limit — print the plane **origins** before concluding.
- **Aligning a plane to a sketch line requires the line to be parallel to the plane** (line direction
  ⊥ plane normal). Align a *horizontal* line to a plane whose normal is horizontal and you get
  `ArgumentException: The two references are not geometrically aligned so the Alignment cannot be
  created` — a genuine geometry mismatch, not a rejection of planes.

⚠ **A reference plane's defining line must lie in the view plane it is created in.** For a plan view:
`bubbleEnd`/`freeEnd` spanning the plan, `cutVec` along Z. For an elevation view: a line spanning the
elevation, `cutVec` along that view's direction. Measured convention:
`normal = cutVec × (freeEnd − bubbleEnd)`, and `cutVec` must be perpendicular to the line or you get
`ArgumentsInconsistentException`.

### What a working parametric family therefore looks like

**Preferred — a reference-plane skeleton.** Verified end to end 2026-10-01 on Revit 2025:
11 skeleton planes (8 in plan, 3 in elevation), **8 labelled dimensions between planes**, 6
extrusions whose sketch lines are each aligned to a plane (**24 alignments, 0 failures**),
`Extrusion Start`/`End` associated for the vertical stack, 2 types. Re-measured after driving:

| type | legA | legD | seat | backrest |
|:---|:---|:---|:---|:---|
| `Standard 450` | X `0..40` Y `0..40` Z `0..405` | X `410..450` Y `410..450` | X `0..450` Y `0..450` Z `405..450` | X `0..450` Y `410..450` Z `450..900` |
| `Large 900` | X `0..60` Y `0..60` Z `0..450` | X `840..900` Y `540..600` | X `0..900` Y `0..600` Z `450..495` | X `0..900` Y `540..600` Z `495..945` |

Every form follows, including the leg-inner planes and the elevation planes. The skeleton itself
moved with the parameters — `Large 900` gave `X[L0 LL60 LR840 R900]`, `Y[F0 LF60 LB540 B600]`,
`Z[0=0 S=450 T=945]` — and that is precisely what makes the aligned geometry follow.

**Fallback — solid-face references.** Also verified: 8 parameters, 2 formulas, 6 extrusions,
**12 labelled face dimensions, 10 face alignments**, 2 types. Dimension every face that must move,
align every part that must stay in formation. Works, but every face needs its own dimension.

Either way, a part that is neither dimensioned nor aligned **does not move** — measured: a seat
driven to 900 mm wide left its backrest sitting at 450 mm.

Sketch-line references are reachable — `extrusion.Sketch.GetAllElements()` returns `ElementId`s that
resolve to `ModelLine`s, whose `GeometryCurve.Reference` is populated. They align to reference planes
and to solid faces.

⚠ **Units.** Every `XYZ` and every `fm.Set(...)` value is in **internal units (feet)**, not mm.
`new XYZ(450,0,0)` is a 450-**foot** chair — it measures perfectly and is useless in a project.
Convert, or use `.InputUnit("mm")` / `.OutputUnit("mm")`.

⚠ **Never call `fm.Set(...)` on a type you intend to keep.** A drive test mutates whatever
`fm.CurrentType` happens to be at that moment. Measured: `Standard 450` and `Large 900` ended up
producing **identical** geometry because the drive test wrote the 900-series values into the first
type before the second was created. Create extra types *after* all testing, or re-set the first
type's values before saving.

⚠ `Document.Close()` throws `InvalidOperationException: Close is not allowed when there is any open
sub-transaction, transaction or transaction group` — and if it throws inside an open transaction,
that document is left holding the transaction and **cannot be closed from a later script**. End
every transaction before closing.

### Full recipe, in order

1. `NewFamilyDocument(tpl)` — the generic template is `English\Metric Generic Model.rft`
   (there is no `Metric Template.rft` in Revit 2025).
2. **tx1** — `fm.NewType(name)` **first** (a fresh family document has no current type), then
   `AddParameter(...)` for each parameter, then `fm.SetFormula(...)`.
3. **tx2** — create the reference-plane skeleton; **commit**. This regeneration is mandatory
   before anything can be dimensioned or aligned to the planes.
4. **tx3** — label one dimension per skeleton axis: `dm.FamilyLabel = param`.
5. **tx4** — one `SketchPlane` at `Z = 0`; create all forms on it, then associate each form's
   `Extrusion Start` / `Extrusion End` to the vertical parameters — **each start to the height of
   the form directly below it**, never one shared height (see the stacking rule in §1).
6. **tx5** — `NewAlignment(planView, planeRef, sketchLineRef)` per sketch line; lock with
   `alignmentDim.IsLocked = true`.
7. **tx6** — `fm.Set(param, value)`; the geometry follows.
8. `fm.NewType(...)` for further types, then `SaveAs`.

**Measured 2026-09-30, live Revit 2025** — an 8-parameter metric chair, 6 extrusions, 10 driving
dimensions, 2 types. Driving four parameters at once moved every form:

| form | before | after (`W` 450→900, `D` 450→600, `LT` 40→60, `SH` 405→500) |
|:---|:---|:---|
| seat | X `0..450` Y `0..450` Z `405..450` | X `0..900` Y `0..600` Z `500..545` |
| leg | X `0..40` Z `0..405` | X `0..60` Z `0..500` |
| backrest | Z `450..900` | Z `545..995` |

⚠ **Measure model space through the solid's face edges, not `Element.get_BoundingBox`.**
`Extrusion.get_BoundingBox(null)` reports in the **extrusion's own sketch-plane frame** — a seat
whose sketch plane sits at `Z = 405` reads `@z0` no matter where it actually is. Walk
`solid.Faces → EdgeLoops → Edge.AsCurve().GetEndPoint(k)` for true model coordinates.

## Two factories — `Doc.Create` is PROJECT-ONLY

`Doc.Create` (`Autodesk.Revit.Creation.Document`) and `Doc.FamilyCreate`
(`Autodesk.Revit.Creation.FamilyItemFactory`) are **mutually exclusive by document kind**, and
each throws on the other's document:

| call | on a project document | on a family document |
|:---|:---|:---|
| `Doc.Create.*` | ✅ works | ❌ `InvalidOperationException: Document.Create can only be used with project documents.` |
| `Doc.FamilyCreate.*` | ❌ `InvalidOperationException: Document.FamilyCreate can only be used in the Revit Family Editor.` | ✅ works |

Both inherit the geometry, reference-plane, dimension and alignment creators from
`ItemFactoryBase` — `NewReferencePlane`, `NewReferencePlane2`, `NewAlignment`, `NewDimension`.
So **on a family document, build reference planes with `famDoc.FamilyCreate.NewReferencePlane(...)`,
not `famDoc.Create`.**

⚠ Reflection trap: `Doc.Create.GetType().GetMethods()` filtered with `m.DeclaringType == type`
returns **zero** of these, because they are declared on `ItemFactoryBase`, not on
`Creation.Document`. Drop the `DeclaringType` filter (or include base types) before concluding an
API is missing.

## Saving and loading

```csharp
famDoc.SaveAs(@"C:\path\MyFamily.rfa");
famDoc.SaveAs(path, new SaveAsOptions());

// Into the project
Family loaded;
Doc.LoadFamily(@"C:\path\MyFamily.rfa", out loaded);
Doc.LoadFamily(path, new FamilyLoadOptions(), out loaded);   // FamilyLoadOptions is yours to implement
Doc.LoadFamilySymbol(@"C:\path\MyFamily.rfa", "Type Name", out symbol);
```

`Document.LoadFamily`, `LoadFamilySymbol`, `EditFamily` and `SaveAs` are all on `Document`
and verified present. `IFamilyLoadOptions` is an interface you must implement — there is no
built-in default, which makes `LoadFamily(string, out Family)` the easier overload.

## Wall-hosted families — what `Metric Door.rft` already contains

Measured 2026-10-01 on Revit 2025. The door template is **not empty** — inventory it before building:

| | |
|:---|:---|
| category | Doors, wall-hosted, with a host wall `Generic - 150mm` present in the document |
| reference planes | `Left` X=−500, `Right` X=+500, `Exterior` Y=+75, `Interior` Y=−75, head plane Z=2000, `Center (Left/Right)` X=0, wall centreline Y=0 |
| **already driven** | **`Width`** (dim between Left/Right) and **`Height`** (dim to the head plane) — verified by setting them and re-reading the planes |
| **not driven** | **`Thickness`** — setting it does **not** move `Exterior`/`Interior` |
| existing geometry | 1 `Opening` (already cuts the host wall), 2 extrusions (interior/exterior casing plates at Y ±75..±100), 2 symbolic lines (elevation diagonals — there is **no** plan swing) |
| parameters | 30 type parameters, incl. `Width`, `Height`, `Thickness`, `Frame Width` (=75), `Rough Width`, `Wall Closure`, `Function`, `Operation` |

So: reuse `Width`/`Height`/`Thickness`/`Frame Width`; add only what is missing.

### ⚠⚠ Do NOT label a dimension between `Exterior` and `Interior` — it raises a MODAL

The template already locks those planes to the host wall:
`dim3135 refs=[Exterior, wall]` and `dim3142 refs=[Interior, wall]`. The wall therefore fixes the
plane separation, so a second driving dimension between them is redundant and Revit raises

> **"Locking this dimension would overconstrain the sketch."**

as a **modal dialog**. ⚠⚠ **A modal blocks the whole Revit API** — the call never returns and the
user must click before anything works again (measured 2026-10-01: the session had to be interrupted).
Cancelling rolls the **entire open transaction** back, not just the failing call.

To make wall thickness parametric, therefore: either leave `Thickness` a plain type parameter and
drive geometry from it **by formula**, or **align** geometry to the planes. Do not dimension between
them.

### Geometry notes specific to wall-hosted families

- **`NewExtrusion` extrudes along the sketch plane's NORMAL by `end`.** Verified: a plane with normal
  `(0,1,0)` at `Y=0` and `end = 200mm` produced a form spanning `Y 0..+200`.
- **A negative `Extrusion Start` works** and extends the form *backwards* through the sketch plane.
  That is how a form is centred on a plane. Measured: `Frame Back = -Thickness / 2` and
  `Frame Front = Thickness / 2` gave a frame spanning `Y −100..+100` at `Thickness = 200`.
- **Profile curves are given in WORLD coordinates** but must be coplanar with the sketch plane. For a
  `(0,1,0)`-normal plane every point has `Y = 0` and you vary X and Z directly — the plane's own
  coordinate system never enters into it.
- **Symbolic curves are the plan/elevation representation.** A curve on a Z-normal plane shows in
  **plan**; on a Y-normal plane it shows in **elevation**. Build the swing with
  `Arc.Create(center, radius, startAngle, endAngle, xAxis, yAxis)`.
- ⚠ **A symbolic arc is NOT parametric.** It is family-level geometry, so it does **not** scale when
  you switch type. A swing arc drawn for a 900 door is wrong on an 800 or 1000 type. Making it follow
  needs its own reference-plane skeleton and dimensions — budget for it, or state the limitation.

#### The door elevation swing lines CONVERGE on the hinge side

The template's two elevation lines run from the two corners of one edge to the **midpoint of the
opposite edge**, forming a V. Measured 2026-10-01, the shipped lines were `(450,1050) → (−450,2100)`
and `(450,1050) → (−450,0)` — apex on the **right** edge.

**The apex (where the lines converge) is the HINGE side. The open end — the base, the two corners —
is the edge that swings free and carries the knob.** This is counter-intuitive and widely misread:
the two corners *look* like a pair of hinges and the single apex *looks* like a knob, so people read
it backwards. Do not.

Corroboration: a CAD-drafting forum thread with three independent veterans (30, 40 and 70 years)
states it plainly — *"The dashed lines converge on the hinge side, never any deviation … the dashed
lines spread toward the open side, and converge at the attachment side."* The same grammar governs
casement and awning windows (a top-hung sash has its apex along the top rail). The opposite reading
does circulate, but it comes from door/window **manufacturers**, not from architectural drafting
convention.

⚠ **Practical rule: the elevation V and the plan swing arc must name the same physical edge.** The
plan arc's *centre* is the hinge; the elevation V's *apex* must be on that edge. In the first build
of the door family they disagreed — the arc hinged at X=−375 while the template's V converged at
X=+450 — so the two annotations described opposite-handed doors. Mirror the lines, reusing the
original's `SketchPlane` (`SymbolicCurve.SketchPlane`, inherited from `ModelCurve`), so the apex
lands on the hinge edge.

### Reaching a non-active family document

- **`GetElements<T>()` has no document overload** — it always reads the ACTIVE document. On a
  `NewFamilyDocument(...)` result only `FamilyManager` (parameters, types) is reachable.
- **`UIApp.OpenAndActivateDocument(path)` opens the family, but `Doc` does not change within the same
  script run** — `Doc` is bound when the script starts. Open in one call, query in the NEXT one.
  (Owner matters: it is `UIApplication.OpenAndActivateDocument`; `UIDocument` has no such method,
  `CS1061`.)
- ⚠ **`GetElements<T>().FirstOrDefault(predicate)` does not compile** (`CS0411` — the pipeline
  enumerable takes no predicate). Use an explicit `foreach`, or `.Where(...)`.

## What is NOT verified here

- **Runtime success of any specific build.** The signatures above are read from the live API,
  but whether a given template accepts a given profile/plane combination can only be found by
  running it. Start with one extrusion and confirm before composing a complex family.
- `FamilyLoadOptions` / `IFamilyLoadOptions` behaviour on a workshared project.
- Adaptive-component helpers (`AdaptiveComponentInstanceUtils`) — not probed. Reference points
  and `NewCurveByPoints` are verified; the adaptive-placement layer above them is not.
