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

`Transact("label", () => { ... })` targets the **active** document. For a family document you
are editing separately, use the **doc-access overload**:

```csharp
Transact("Build family", d => { /* d is the document, not Doc */ });
```

**SPEED RULE — build the whole family in ONE transaction.** Every `Transact()` is a
regeneration plus an undo entry. Wrapping each `New*` call in its own transaction regenerates
the family once per primitive. Put all geometry, parameters and types in a single block.

Note that `SketchPlane.Create(...)` creates an element, so it needs the transaction too. Plain
geometry (`Line.CreateBound`, `Plane.CreateByNormalAndOrigin`, `CurveArray`) does not.

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

// ONE transaction for the whole build
Transact("Build family", d => {
    var sp = SketchPlane.Create(d, Plane.CreateByNormalAndOrigin(new XYZ(0, 0, 1), XYZ.Zero));
    d.FamilyCreate.NewExtrusion(true, profile, sp, depth);
});
```

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
Transact("Add Width parameter", d => {
    var fm = d.FamilyManager;
    var width = fm.AddParameter("Width", new ForgeTypeId("autodesk.parameter.group:pg_geometry"),
                                SpecTypeId.Length, false);   // false = type parameter
    fm.Set(width, 900.InputUnit("mm"));

    // A second type driven by a formula
    var t2 = fm.NewType("900 x 2100");
    fm.CurrentType = t2;
    fm.Set(width, 900.InputUnit("mm"));
});
```

Two cautions on that example:

- The **group `ForgeTypeId` string** (`autodesk.parameter.group:pg_geometry`) is the one part
  here that was *not* read off the live API in this pass. Verify it before relying on it —
  list the existing parameters with `fm.Parameters` and reuse a group id already present in
  the family rather than inventing one.
- `fm.Set(...)` must run **inside** a transaction, and `CurrentType` must be set before
  setting values for a specific type.

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

## What is NOT verified here

- **Runtime success of any specific build.** The signatures above are read from the live API,
  but whether a given template accepts a given profile/plane combination can only be found by
  running it. Start with one extrusion and confirm before composing a complex family.
- `FamilyLoadOptions` / `IFamilyLoadOptions` behaviour on a workshared project.
- Adaptive-component helpers (`AdaptiveComponentInstanceUtils`) — not probed. Reference points
  and `NewCurveByPoints` are verified; the adaptive-placement layer above them is not.
