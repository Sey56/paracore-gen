---
name: massing-forms
description: Conceptual massing with Form objects — AddProfile, AddEdge, AddPath, FormUtils, loft forms, profile editing, adaptive components
---

# Conceptual Massing & Forms

Conceptual massing in Revit is **family authoring with a mass template**. There is no separate
massing API: the form creators live on `FamilyItemFactory`, reachable as `Doc.FamilyCreate` on a
**mass family document**.

All signatures on this page were read off the live Revit 2025 API by reflection. Behaviour
assertions are marked.

## Entry point — you need a mass family document

`Doc.FamilyCreate` **throws `InvalidOperationException`** on a project document. Verified
template path (Revit 2025 English):

```csharp
Document massDoc = UIApp.Application.NewFamilyDocument(
    UIApp.Application.FamilyTemplatePath + "\\English\\Conceptual Mass\\Metric Mass.rft");
```

Or edit a mass family already loaded in the project:

```csharp
var mass = GetElements<FamilyInstance>("Masses").FirstOrDefault();
Document massDoc = Doc.EditFamily(mass.Symbol.Family);
```

See the **family-authoring** skill for the template layout, the transaction rules and
`FamilyManager`. Everything there applies here.

## Transactions — ONE per build

```csharp
Transact("Build mass", d => { /* d = the mass document */ });
```

`Transact("label", () => {...})` targets the **active** document. Use the doc-access overload
for a mass document you opened separately.

**SPEED RULE.** Every `Transact()` costs a regeneration and an undo entry. Build the whole mass
in one block. Creating a form per transaction, then editing it in more transactions, is the
slow path — do it in one pass where you can.

## Form creators — `Doc.FamilyCreate`, verified

| Method | Signature |
|:---|:---|
| `NewLoftForm` | `Form NewLoftForm(bool isSolid, ReferenceArrayArray profiles)` |
| `NewExtrusionForm` | `Form NewExtrusionForm(bool isSolid, ReferenceArray profile, XYZ direction)` |
| `NewRevolveForms` | `FormArray NewRevolveForms(bool isSolid, ReferenceArray profile, Reference axis, double startAngle, double endAngle)` |
| `NewSweptBlendForm` | `Form NewSweptBlendForm(bool isSolid, ReferenceArray path, ReferenceArrayArray profiles)` |
| `NewFormByCap` | `Form NewFormByCap(bool isSolid, ReferenceArray profile)` |
| `NewFormByThickenSingleSurface` | `Form NewFormByThickenSingleSurface(bool isSolid, Form singleSurfaceForm, XYZ thickenDir)` |

`NewRevolveForms` returns a **`FormArray`**, not a single `Form` — a revolve can produce
several forms when the profile crosses the axis.

Note the argument types: these take `Reference`/`ReferenceArray`/`ReferenceArrayArray`, **not**
`Curve`/`CurveArray`. A profile here is a set of *references to geometry already in the mass
document* (reference points and the lines/curves between them), not a bare `CurveArray`. That is
the main structural difference from `NewExtrusion` / `NewBlend` in the family-authoring skill,
which do take `CurveArray` / `CurveArrArray`.

### Reference plumbing (verified)

```csharp
ReferenceArray      ;  // ctor()  → Append(Reference)
ReferenceArrayArray ;  // ctor()  → Append(ReferenceArray) | Insert(ReferenceArray, int index)
ReferencePointArray ;  // ctor()  → Append(ReferencePoint)
```

## Building a loft — the usual massing workflow

```csharp
Document massDoc = UIApp.Application.NewFamilyDocument(
    UIApp.Application.FamilyTemplatePath + "\\English\\Conceptual Mass\\Metric Mass.rft");

double w = 6000.InputUnit("mm"), d = 4000.InputUnit("mm");

Transact("Loft mass", doc => {
    // 1. Reference points defining the base profile
    var p0 = doc.FamilyCreate.NewReferencePoint(new XYZ(0, 0, 0));
    var p1 = doc.FamilyCreate.NewReferencePoint(new XYZ(w, 0, 0));
    var p2 = doc.FamilyCreate.NewReferencePoint(new XYZ(w, d, 0));
    var p3 = doc.FamilyCreate.NewReferencePoint(new XYZ(0, d, 0));

    // 2. Curves between them
    doc.FamilyCreate.NewCurveByPoints(new ReferencePointArray());
    // ... append points to the ReferencePointArray first, then call NewCurveByPoints

    // 3. Loft the profile
    // var profiles = new ReferenceArrayArray();
    // profiles.Append(<ReferenceArray of the profile's curves/edges>);
    // doc.FamilyCreate.NewLoftForm(true, profiles);
});
```

The commented lines are deliberately left as scaffolding: **the step that turns points into a
`ReferenceArray` of curve references is the one part of this workflow that was not exercised
end-to-end in this pass.** `NewCurveByPoints` returns a `CurveByPoints`; getting a `Reference`
to it (rather than the element) is what `NewLoftForm` needs. Verify that hop on a scratch mass
family before composing a complex loft — see "What is NOT verified" below.

## `Form` — editing an existing form

47 public methods. Reach a form as the return of any creator, or via `GetElements<Form>()`.

### Profiles

```csharp
int          ProfileCount { get; }
int          ProfileCurveLoopCount(int index);            // get_ProfileCurveLoopCount
ReferenceArray CurveLoopReferencesOnProfile(int profileIndex, int curveLoopIndex);
int          AddProfile(Reference edgeReference, double param);   // returns new profile index
void         DeleteProfile(int profileIndex);
bool         CanManipulateProfile(int profileIndex);
bool         IsReferenceOnlyProfile(int profileIndex);
void         GetProfileAndCurveLoopIndexFromReference(Reference curveOrEdgeReference,
                                                     out int profileIndex, out int curveLoopIndex);
```

`AddProfile` takes a **`Reference` to an edge** plus a parameter along it — not a curve loop.
That is the single most surprising signature in this class.

### Moving profiles and sub-elements

```csharp
void MoveProfile(int profileIndex, XYZ offset);
void RotateProfile(int profileIndex, Line axis, double angle);
void ScaleProfile(int profileIndex, double factor, XYZ origin);

void MoveSubElement(Reference subElementReference, XYZ offset);
void RotateSubElement(Reference subElementReference, Line axis, double angle);
void ScaleSubElement(Reference subElementReference, double factor, XYZ origin);
void DeleteSubElement(Reference subElementReference);
bool CanManipulateSubElement(Reference subElementReference);
```

### Edges and paths

```csharp
void AddEdge(Reference startPointReference, Reference endPointReference);
void AddEdge(Reference startEdgeReference, double startParam,
             Reference endEdgeReference, double endParam);
void AddEdge(Reference faceReference, XYZ point);

int       PathCurveCount { get; }
Reference PathCurveReference(int curveIndex);
int       GetPathCurveIndexByCurveReference(Reference curveReference);
```

### Constraints, offsets, rehosting

```csharp
bool   AreProfilesConstrained { get; set; }
void   ConstrainProfiles(int primaryProfileIndex);
bool   IsInXRayMode { get; set; }
bool   HasOpenGeometry { get; }
double TopOffset { get; set; }
double BaseOffset { get; set; }
void   Rehost(SketchPlane sketchPlane, XYZ location);
void   Rehost(Reference hostRef, XYZ location);
```

### Reference classification — use these before assuming a reference type

```csharp
bool IsVertexReference(Reference r);
bool IsEdgeReference(Reference r);
bool IsCurveReference(Reference r);
bool IsFaceReference(Reference r);
bool IsBeginningFace(Reference r);
bool IsEndFace(Reference r);
bool IsSideFace(Reference r);
bool IsAutoCreaseEdge(Reference r);
bool IsProfileEdge(Reference r);
bool IsConnectingEdge(Reference r);
ReferenceArray GetControlPoints(Reference curveOrEdgeOrFaceReference);
ReferenceArray GetCurvesAndEdgesReference(Reference pointReference);
```

These are cheap and they are the guard against the classic massing error: passing a face
reference where an edge reference is required. Classify first, then act.

## `FormUtils` — dissolving forms (verified, 3 methods)

```csharp
bool CanBeDissolved(Document doc, ICollection<ElementId> elements);
ICollection<ElementId> DissolveForms(Document doc, ICollection<ElementId> elements);
ICollection<ElementId> DissolveForms(Document doc, ICollection<ElementId> elements,
                                     out ICollection<ElementId> profileOriginPointSet);
```

**These take `ElementId`, not `Form`.** Pass `form.Id`:

```csharp
var ids = new System.Collections.Generic.List<ElementId>();
ids.Add(form.Id);
Transact("Dissolve", d => {
    if (FormUtils.CanBeDissolved(d, ids)) { FormUtils.DissolveForms(d, ids); }
});
```

Dissolving a form leaves the profiles and reference points behind, which is the normal way to
get back to editable profiles.

## `FormArray` — returned by `NewRevolveForms`

```csharp
int    Size { get; }
bool   IsEmpty { get; }
Form   this[int index] { get; set; }
void   Append(Form item);
void   Insert(Form item, int index);
void   Clear();
FormArrayIterator ForwardIterator();
FormArrayIterator ReverseIterator();
```

## Adaptive components

Verified pieces: `NewReferencePoint(XYZ | Transform | PointElementReference)`,
`NewCurveByPoints(ReferencePointArray)`, `NewFormByCap`, `NewFormByThickenSingleSurface`, and the
adaptive template `\English\Metric Generic Model Adaptive.rft`.

Not verified: `AdaptiveComponentInstanceUtils` and the adaptive-placement layer that places an
adaptive family on a divided surface. Do not assume those signatures — probe them before use.

## What is NOT verified here

- **The reference-point → curve → loft hop.** `NewLoftForm` needs `ReferenceArrayArray` of
  *references*; turning freshly-created reference points and curves into those references is the
  step that was not run end-to-end. This is the first thing to try on a scratch mass family.
- Runtime success of any specific form creation. Signatures are from the live API; whether a
  given profile/axis/direction combination is accepted can only be found by running it.
- `NewFormByThickenSingleSurface` requires an existing single-surface `Form`; the path to
  obtaining such a form (a loft with open geometry — `HasOpenGeometry`) was not exercised.
- Worksharing behaviour when editing a mass family from a workshared project.
