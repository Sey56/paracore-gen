---
name: project-modeling
description: Model a REAL building — levels, plan views, grids, floor slabs, walls, curtain walls, roofs, rooms, doors/windows, stairs, columns/beams, wall-type duplication, family loading — plus the per-build verification and safety recipes. Use for "model a building", "make it 3 storeys", "add walls and rooms", "build this from the dimensions". NOT massing.
---

# Project Modeling — a real building, per level

**This is the path for a building.** "Model this building", "make it three storeys", "put
walls, floors and rooms in", "build it from these dimensions" — all of them start here.

⚠⚠ **Massing is NOT the path for a building.** A `Form` or `DirectShape` **cannot become a
floor, a wall or a room** — it is a dead end for anything downstream. `massing-forms` is for
concept studies only. If the target is a building, build it **per level with real elements**.

⚠ **Build per level, never as one object.** Levels → plan views → grids → slab → walls →
openings → rooms. Each step below carries the trap that has actually bitten this project.

> **Scope.** This skill covers generalist Revit modelling. BOQ, quantities, takeoff and
> cost are out of scope here.

---

## The contract — a number you cannot re-derive is not a result

"Created a building" is not a result. **"42 walls, 7 levels, 1,280 m² of slab, 0 warnings"**
is. Run the **Tier 1 check** (§Verification) after *every* build. Do not report success
without it.

---

## Step 0 — the spec, before any geometry

Writing the spec is **your** job, not the MCP's — the MCP has no opinion about what a building
should be. Its contribution is making the spec **checkable** (Tier 3, below).

Ask for, and write down, a short table: site, grids, levels (name + elevation), floor plates
(outline + area), facade type, opening rhythm. **Tag every value `measured` or `estimated`.**

⚠ **Scale from real dimensions, not pixels.** For photos, ask for **one or two true
dimensions** (a storey height, a door width) and derive everything else. Guessing a footprint
from image proportions is how a model ends up 60 ft on all sides when the site is 30 × 60.

⚠ **Work in internal feet; report with `.OutputUnit()`.** `5000.InputUnit("mm")` → feet;
`area.OutputUnit("m2")` → m². Never write `/ 304.8` or `* 0.3048` — the checker flags it and
the engine already does it.

---

## Recipes 1–14

Legend: ✅ exercised in this project · ○ signature from the Revit 2025 API, not yet exercised
here — verify with the Tier 1 check before reporting.

### 1. Levels ✅

```csharp
Transact("Create levels", () => {
    Level.Create(Doc, 0.0);
    Level.Create(Doc, 3.0.InputUnit("m"));
    Level.Create(Doc, 6.0.InputUnit("m"));
});
```

⚠ **Creating a level does NOT create a plan view.** The level exists in elevations and
schedules, but nothing appears in the Project Browser's floor plans until recipe 2.

### 2. Plan views ✅

```csharp
var vft = GetElements<ViewFamilyType>().FirstOrDefault(t => t.ViewFamily == ViewFamily.FloorPlan);
var lvl = GetElements<Level>().FirstOrDefault(l => l.Name == "Level 1");
Transact("Create plan view", () => ViewPlan.Create(Doc, vft.Id, lvl.Id));
```

⚠ Needs a `ViewFamilyType` whose `ViewFamily == ViewFamily.FloorPlan`. If `vft` is null, the
template has none — **say so and stop**; do not guess an id. Run the discovery recipe in
§Discovery to list what is available.

### 3. Grids ○

```csharp
Transact("Create grids", () => {
    var a = Grid.Create(Doc, Line.CreateBound(new XYZ(0, 0, 0), new XYZ(0, 20.InputUnit("m"), 0)));
    a.Name = "A";
});
```

⚠ **Name every grid.** Unnamed grids make every downstream reference positional — you cannot
later say "the wall on grid B" and be understood.

### 4. Footprint loop — validate closure FIRST ○

```csharp
var corners = new List<XYZ> {
    new XYZ(0, 0, 0),
    new XYZ(8.InputUnit("m"), 0, 0),
    new XYZ(8.InputUnit("m"), 6.InputUnit("m"), 0),
    new XYZ(0, 6.InputUnit("m"), 0),
};

// ⚠⚠ Validate closure EXPLICITLY and report the gap in mm BEFORE you build.
var gap = corners[0].DistanceTo(corners[corners.Count - 1]);
Println($"closure gap = {gap.OutputUnit("mm")} mm (0 = closed)");

var loop = new CurveLoop();
for (int i = 0; i < corners.Count; i++) {
    loop.Append(Line.CreateBound(corners[i], corners[(i + 1) % corners.Count]));
}
```

⚠⚠ **"Curve loops do not satisfy the input requirements" is a non-closure / non-planarity
error, and it tells you nothing about which corner is wrong.** Compare first against last
point and report the gap in mm instead of surfacing that message. All points must share Z.

### 5. Floor slab ○

```csharp
var ft  = GetElements<FloorType>().FirstOrDefault(t => t.Name == "Generic 150mm");
var lvl = GetElements<Level>().FirstOrDefault(l => l.Name == "Level 1");
Transact("Create slab", () =>
    Floor.Create(Doc, new List<CurveLoop> { loop }, ft.Id, lvl.Id));
```

⚠ **The slab sits *above* its level by default.** A "Level 1" slab has its base at Level 1
and its top one thickness higher. Check the base elevation in Tier 1, do not assume.

### 6. Walls ✅

```csharp
var wt  = GetElements<WallType>().FirstOrDefault(t => t.Name == "Generic - 200mm");
var lvl = GetElements<Level>().FirstOrDefault(l => l.Name == "Level 1");

Transact("Create walls", () => {
    for (int i = 0; i < corners.Count; i++) {
        var a = corners[i];
        var b = corners[(i + 1) % corners.Count];
        // height overload: (doc, curve, typeId, levelId, height, offset, flip, structural)
        // avoids a level-to-level constraint chain — the wall is exactly this tall.
        Wall.Create(Doc, Line.CreateBound(a, b), wt.Id, lvl.Id,
                    3.0.InputUnit("m"), 0.0, false, false);
    }
});
```

⚠ Two overloads exist and they are easy to confuse:
`Wall.Create(Doc, curve, levelId, structural)` uses the **default** wall type;
`Wall.Create(Doc, curve, typeId, levelId, height, offset, flip, structural)` uses the one you
name. Use the second when you care about the type.

### 7. Curtain walls ○

```csharp
var cwt = GetElements<WallType>().FirstOrDefault(t => t.Kind == WallKind.Curtain);
```

⚠ **Panel and mullion types are separate from the wall type.** Setting the curtain wall type
does not choose its panels. Add grid lines with `CurtainGrid.AddGridLine`, then assign
panel/mullion types separately — a curtain wall with no grid has one panel.

### 8. Roof / terrace ○

```csharp
// ⚠⚠ Needs a PLAN-view sketch plane — it will fail from a 3D view.
CurveArray outline = new CurveArray();
foreach (var c in loop) outline.Append(c);
ModelCurveArray map;
Transact("Create roof", () =>
    Doc.Create.NewFootPrintRoof(outline, lvl, roofType, out map));
```

⚠ `NewFootPrintRoof` takes a `CurveArray`, **not** a `CurveLoop` — and it needs the active
view to be a plan. Note this project models its "roof" as a **`Floor` slab**; a `Floor` and a
`Roof` are different categories, so `GetElements("Roofs")` will not find a slab.

### 9. Rooms ○

```csharp
Transact("Create rooms", () => {
    var r = Doc.Create.NewRoom(lvl, new UV(4.InputUnit("m"), 3.InputUnit("m")));
    r.Name = "Living";
});
```

⚠⚠ **`Room.Area` stays `0` until its boundaries actually close.** A room placed inside walls
that do not form a closed loop reports 0 m². **Check the area and say so** — do not report
`0` as if it were the answer. `NewRoomBoundaryLines` can add explicit boundaries.

### 10. Doors / windows ✅

```csharp
var sym = GetElements<FamilySymbol>("Doors").FirstOrDefault(s => s.Name == "0762 x 2032mm");
Transact("Place door", () =>
    Doc.Create.NewFamilyInstance(point, sym, hostWall, lvl, StructuralType.NonStructural));
```

⚠ **The point must lie on the host wall's location curve** — a point near it is rejected or
placed at the wrong angle. Take the point from `(wall.Location as LocationCurve).Curve`.

⚠ **An inactive symbol cannot be placed.** Inside the transaction: `if (!sym.IsActive) sym.Activate();`

### 11. Stairs ○ — heaviest, scope it LAST

```csharp
using (var scope = new StairsEditScope(Doc, "Create stairs")) {
    var stairsId = scope.StartTransaction(levelBottom.Id, levelTop.Id);
    // ... create the run / sketched stairs between the two levels here ...
    scope.Commit(new StairsFailurePreprocessor());   // built into the engine — do NOT redefine it
}
```

⚠ `scope.Commit(null)` **throws** — a `StairsEditScope` must be committed with a failure
preprocessor. `StairsFailurePreprocessor` is **provided by the engine** (globally available, like
`Transact`), so just name it; writing your own `IFailuresPreprocessor` is unnecessary. It deletes
warnings and rolls the whole scope back on an error, so a partial build cannot leave a broken run.

⚠ The heaviest recipe in this skill, and the least forgiving. Build everything else, verify,
**then** do stairs.

### 12. Columns / beams ○

```csharp
var col = Doc.Create.NewFamilyInstance(pt, colType, lvl, StructuralType.Column);
```

⚠ **A beam needs a `Line` + a level, not just a point** — use the
`NewFamilyInstance(Line, FamilySymbol, Level, StructuralType.Beam)` overload. Columns take a
point; beams take a curve.

### 13. Type duplication ○

```csharp
Transact("Duplicate wall type", () => {
    var wt  = GetElements<WallType>().First(t => t.Name == "Generic - 200mm");
    var dup = wt.Duplicate("Generic - 250mm") as WallType;
    var layers = new List<CompoundStructureLayer> {
        new CompoundStructureLayer(0.25.InputUnit("m"),
                                   MaterialFunctionAssignment.Structure, matId)
    };
    dup.SetCompoundStructure(CompoundStructure.CreateSimpleCompoundStructure(layers));
});
```

⚠⚠ **Layer widths are in FEET (internal units).** `0.25` is a quarter of a foot, not 250 mm.
Always `.InputUnit("mm")`.

### 14. Family loading ○

```csharp
Family fam;
Transact("Load family", () => Doc.LoadFamily(@"C:\path\to\family.rfa", out fam));

Transact("Activate symbols", () => {
    foreach (var id in fam.GetFamilySymbolIds()) {
        var s = Doc.GetElement(id) as FamilySymbol;
        if (s != null && !s.IsActive) s.Activate();
    }
});
```

⚠⚠ **A load does NOT activate a symbol.** An un-activated symbol is invisible to
`NewFamilyInstance` and to placement. Activate it in its own transaction.

---

## Verification — three tiers

### Tier 1 — re-derive after EVERY build (always on, free)

```csharp
Println($"Walls   {GetElements<Wall>().Count()}");
Println($"Floors  {GetElements<Floor>().Count()}");
Println($"Rooms   {GetElements<Room>().Count()}   total {GetElements<Room>().SumParam("Area", "m2")} m2");
Println($"Levels  {GetElements<Level>().Count()}");
Println($"Warnings {Doc.GetWarnings().Count}");
foreach (var w in Doc.GetWarnings()) Println($"  ! {w.Description}");
```

**`Doc.GetWarnings()` is not optional.** A build that "succeeded" with 6 warnings is not
done. Report the count, and read every warning.

### Tier 2 — look at it (one image)

**Seeing is not measuring** — an image tells you a proportion is wrong, never that a quantity
is right. Do both.

Use the **`export_view` tool** (returns the image directly), or in-script
`ExportImage(path, viewName, pixelSize)`. Full detail is in `display-visualize`.

⚠ A snapshot is not a live view, and a bad camera can hide a defect. Export a view you chose
deliberately.

### Tier 3 — spec vs model, pass/fail per row (free)

```csharp
var expLevels = 7;   var actLevels = GetElements<Level>().Count();
Println($"Levels    expected {expLevels}   actual {actLevels}   {(expLevels == actLevels ? "PASS" : "FAIL")}");

var expArea = 1280.0; var actArea = GetElements<Floor>().SumParam("Area", "m2");
Println($"Slab m2   expected {expArea}   actual {actArea}   {(Math.Abs(expArea - actArea) < 1.0 ? "PASS" : "FAIL")}");
```

One line per spec row. **A row that cannot be measured is a row that cannot be verified** —
say so rather than marking it PASS.

---

## Safety — three recipes, no new tools

| Want | How | Note |
|---|---|---|
| Checkpoint | `Doc.Save()` **before** a bulk operation | ⚠ Do **not** use `Doc.SaveAs` as a checkpoint — it **moves** the working file, so every later save goes to the copy. |
| Tagged batch | stamp created elements: `.SetVal("Comments", "ESB-v3")` | lets you say "replace batch ESB-v3" instead of deleting by a name prefix |
| Dry-run | count and `Println` the planned operations; commit only on a second, explicit call | mirrors the existing bulk-write warning |

⚠⚠ **Deleting a batch is still a delete.** List the ids, say how many, and get an explicit
confirmation before removing anything. A tagged batch makes the delete *safer*, not automatic.

---

## Discovery — before you build, list what exists

```csharp
GetElements<WallType>().Select(t => new { t.Id, Name = t.Name }).Table()
GetElements<FloorType>().Select(t => new { t.Id, Name = t.Name }).Table()
GetElements<ViewFamilyType>().Select(t => new { t.Id, Name = t.Name, Family = t.ViewFamily.ToString() }).Table()
GetElements<Level>().Select(l => new { l.Id, l.Name, Elevation = l.Elevation.OutputUnit("m") }).Table()
GetElements<View>().Select(v => new { v.Id, v.Name, Type = v.ViewType.ToString(), IsTemplate = v.IsTemplate }).Table()
GetElements<FamilySymbol>("Doors").Select(s => new { s.Id, s.Name }).Table()
```

⚠ **Discover first — do not guess a type name.** `GetElements<WallType>().FirstOrDefault(t => t.Name == "…")`
returns `null` for a wrong name, and `null.Id` then fails somewhere far from the cause. If a
lookup returns nothing, list the category and pick from it.

---

## Traps already paid for

- ⚠ **`Color` is ambiguous** between `System.Drawing.Color` and `Autodesk.Revit.DB.Color`. Qualify it.
- ⚠ **A `Revolve` failed where a blend worked** — prefer the construction already proven.
- ⚠ **`Doc.FamilyCreate` / `Doc.FamilyManager` THROW on a project document** (they do not
  return null). Family work belongs in `family-authoring`.
- ⚠ **A duplicated or renamed element TYPE arrives with an empty `BOQ_Section`** — names never
  block, values do. (Pro/takeoff concern; noted so a duplicate does not surprise you later.)
- ⚠ **A display string is a routing key, not a label** — renaming a section silently re-prices.

---

## Typical usage

**"Model this building"** → `project-modeling` (+ `query-filter` for discovery, `write-modify`
for parameters, `display-visualize` to look at it)

**"Does this look right?"** → `export_view` / `ExportImage`, then correct

**"How much slab did I create?"** → `project-modeling` (Tier 1) + `aggregate-group`

**Concept study, no rooms needed** → `massing-forms` — and only then.
