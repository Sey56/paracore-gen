# 🧩 Paracore Extension Methods Reference

A comprehensive guide to every extension method available on Revit elements and collections in Paracore scripts. All methods are globally available in the REPL and in all scripts.

Source files: `ElementExtensions.cs`, `ElementParamExtensions.cs`, `ElementWriteExtensions.cs`, `ElementDoorExtensions.cs`, `ElementDiscoveryExtensions.cs`, `ElementGeometryExtensions.cs`, `ElementUIExtensions.cs`, `CollectionAggregateExtensions.cs`, `CollectionWriteExtensions.cs`, `CollectionUIExtensions.cs`, `PipelineEnumerable.cs`, `UnitExtensions.cs`,<!-- #PRO-ONLY-BEGIN Pro-only sources; stripped from the free copy --> `CoordinationExtensions.cs`, `CurtainGridRepairExtensions.cs`<!-- #PRO-ONLY-END -->, `NotebookExtensions.cs`, `ScriptApi.cs`<!-- #PRO-ONLY-BEGIN -->, `Eco.cs`<!-- #PRO-ONLY-END -->.

> [!NOTE]
> All extension methods work identically in the **REPL** and in **Gallery scripts**. They are standard C# extension methods available everywhere the engine runs.

> [!TIP]
> All collection extension methods are **fully generic** — they preserve the specific element type (`Wall`, `FamilyInstance`, etc.) throughout the entire fluent chain.

> [!IMPORTANT]
> **Script Rules:** Top-level statements only — no `namespace`, `class Program`, or `Main()`. All namespaces pre-imported — never write `using` or fully-qualified names. No `FilteredElementCollector` — use `GetElements<T>()` or `GetElements("Category")`. No `IExternalApplication`/`IExternalCommand`.

---

## 📦 Element Retrieval

SYSTEM FAMILIES (`Wall`, `Floor`, `Room`, `Ceiling`, etc.):
```
GetElements<Wall>()      → typed Wall instances, no category string needed
GetElements<WallType>()  → typed wall type definitions
GetElements("Walls")     → untyped Element list (use only when necessary)
```

LOADABLE FAMILIES (Doors, Windows, Furniture, Columns, etc.):
```
GetElements<FamilyInstance>("Doors")  → typed FamilyInstance, door category
GetElements<FamilySymbol>("Doors")    → typed type symbols (door family types)
GetElements("Doors")                  → untyped Element list
```

Single-element: `GetElement("name-or-id")` | Discovery: `GetMagicNames()`, `GetCategories()`

---

## 📖 Table of Contents

1. [Element: Parameter & Property Accessors (Read)](#1-element-parameter--property-accessors-read)
2. [Element: Type-Level Accessors](#2-element-type-level-accessors)
3. [Element: Smart Write Methods](#3-element-smart-write-methods)
4. [Element: Identity & Discovery](#4-element-identity--discovery)
5. [Element: Specialized Door/Window](#5-element-specialized-doorwindow)
6. [Element: Materials & Sustainability](#6-element-materials--sustainability)
7. [Element: Geometry](#7-element-geometry)
8. [Element: Revit UI Actions](#8-element-revit-ui-actions)
9. [Collection: Filtering](#9-collection-filtering)
10. [Collection: Sorting](#10-collection-sorting)
11. [Collection: Grouping & Aggregation](#11-collection-grouping--aggregation)
12. [Collection: Bulk Write](#12-collection-bulk-write)
13. [Collection: Revit UI Actions](#13-collection-revit-ui-actions)
14. [Collection: Notebook Export](#14-collection-notebook-export)
15. [Numeric & Unit Helpers](#15-numeric--unit-helpers)
<!-- #PRO-ONLY-BEGIN  Pro-only engines — Clash Detection (CoordinationExtensions.cs) and Curtain Grid Repair (CurtainGridRepairExtensions.cs). gen-engine-docs.py strips this region from the free-repo copy; do not remove the markers. -->
16. [Coordination & Clash Detection](#16-coordination--clash-detection)
17. [Curtain Grid Repair](#17-curtain-grid-repair)
<!-- #PRO-ONLY-END -->
18. [Global ScriptApi Methods](#18-global-scriptapi-methods)
19. [Complete Fluent Chain Examples](#19-complete-fluent-chain-examples)

---

## 1. Element: Parameter & Property Accessors (Read)

### GetStr — parameter value as string

```csharp
// Resolution chain: Level → LookupParameter → BuiltInParameter → C# Property → NativeProperties → Type
GetElements("Walls").First().GetStr("Comments")        // "North wall"
GetElements("Walls").First().GetStr("Fire Rating")      // "2 hr"
GetElements("Walls").First().GetStr("Room Bounding")    // "1" or "0" (yes/no checkbox)
GetElements("Walls").First().GetStr("Level")            // "02 - Ground Floor Plan" (via NativeProperties)
```

**"Level" resolution**: GetStr("Level") works on ALL categories. Walls → NativeProperties LevelId, Structural Framing → "Reference Level", Columns → "Base Level", Doors/Windows/Rooms → built-in "Level" parameter. Uses category-specific fallback chain: Reference Level → Base Level → Base Constraint → Native LevelId.

**Unknown parameters**: GetStr returns "" silently (safe for chained queries) but logs a one-time warning: `⚠ GetStr("BadParam"): parameter not found on element. Check spelling or use .CombinedParams().Table() to discover available parameters.`

### GetNum — parameter value as double

```csharp
wall.GetNum("Area")                   // internal units (sq ft)
wall.GetNum("Area", "m2")            // 14.52
wall.GetNum("Unconnected Height")     // internal units (ft)
wall.GetNum("Unconnected Height", "m") // 2.80
wall.GetNum("Width", "mm")            // 200
```

Falls back to C# properties via Reflection if the parameter isn't found.

### GetInt — parameter value as integer

```csharp
wall.GetInt("Room Bounding")          // 1 or 0 (yes/no checkbox)
beam.GetInt("Number of Studs")        // 3
```

### GetVal — formatted value string as seen in Revit Properties

```csharp
wall.GetVal("Area")                   // "14.52 m²"
wall.GetVal("Volume", "m3")           // "2.450 m³"
```

### GetVal with unit

```csharp
wall.GetVal("Area", "m2")             // "14.52 m²"
```

---

## 2. Element: Type-Level Accessors

All instance-level getters have type-level equivalents:

```csharp
column.GetTypeStr("Material")         // "Concrete - C-25"
column.GetTypeNum("b", "mm")          // 250
column.GetTypeNum("h", "mm")          // 300
column.GetTypeInt("Usage")            // 0
column.GetTypeVal("Cost")             // "25.00 Birr"
```

`GetElementType()` returns the `ElementType` for any instance.

---

## 3. Element: Smart Write Methods

### SetNum — set a numeric value with unit conversion

```csharp
wall.SetNum("Unconnected Height", 3.0, "m")   // converts 3.0m → internal ft, sets parameter
wall.SetNum("Base Offset", -150, "mm")         // converts -150mm → internal ft
```

Wraps in a transaction automatically if one isn't active.

### SetVal — THE smart setter

```csharp
wall.SetVal("Comments", "New comment")         // String
wall.SetVal("Unconnected Height", 3.0)         // Double
wall.SetVal("Room Bounding", 0)                // Int (yes/no checkbox — 0 = unchecked)
wall.SetVal("Level", "Level 2")                // ElementId resolved by name
wall.SetVal("Mark", "A-12")                    // String parameter
```

### SetVal with unit

```csharp
wall.SetVal("Unconnected Height", 2800, "mm")  // converts from mm
column.SetVal("Base Offset", -0.15, "m")       // converts from m
```

When no unit is specified for a Double parameter, the handler defaults to the parameter's own display unit (via `GetUnitTypeId()`).

---

## 4. Element: Identity & Discovery

### Reflection discovery

```csharp
wall.ReflectionProperties().Table()   // all C# properties on Wall
wall.ReflectionMethods().Table()      // all C# methods on Wall (public, not Object)
```

### Parameter discovery

```csharp
wall.BuiltInParams().Table()          // built-in parameters with current values
wall.InstanceParams().Table()         // instance parameters: Name, Storage, Value
wall.TypeParams().Table()             // type parameters on the element's family type
wall.CombinedParams().Table()         // instance + type + native properties, separated by scope
wall.ParamsDict()                     // Dictionary<string,string> of all params
wall.NativeProperties()               // Category, Level, Workset, etc.
```

### Identity helpers

```csharp
wall.Matches("HCB")                   // fuzzy match against Type Name + Family Name
wall.FamilyName                       // "Basic Wall"
wall.GetStr("Family and Type")        // full identity string
```

---

## 5. Element: Specialized Door/Window

### Orientation (stable regardless of flips)

```csharp
door.RoomFrom()                       // "LIVING ROOM"
door.RoomTo()                         // "CORRIDOR"
door.RoomAccess()                     // alias for RoomFrom
door.RoomDestination()                // alias for RoomTo
door.Handing()                        // "LH" or "RH"
door.HingeSide()                      // "Left" or "Right"
door.IsHandFlipped                    // true/false
door.IsFacingFlipped                  // true/false
door.FindSwingArc()                   // largest Arc in geometry (swing path)
```

### Standard door filter

```csharp
// Exclude curtain-wall-hosted glass doors
GetElements<FamilyInstance>("Doors").StandardDoor().Table()
// → 33 standard doors (out of 40 total)

door.IsStandardDoor()                 // true if NOT hosted on a Curtain Wall
```

---

## 6. Element: Materials & Sustainability

```csharp
wall.Materials().Table()              // all Material objects on the element
wall.MaterialNames()                  // IEnumerable<string>: "Concrete - C-25", "Plaster - Cement"
wall.GetMaterialNames()              // comma-separated string

// Eco (static, not extension methods)
Eco.GetCarbon(element)                // kgCO2e
Eco.GetUValue(element)                // W/m²K
Eco.GetWeather()                      // live Open-Meteo API for project location
```

---

## 7. Element: Geometry

```csharp
wall.GeometrySummary()                // recursive: Solids, Curves, Arcs in world space
```

---

## 8. Element: Revit UI Actions

```csharp
element.Select()                      // select in UI, returns element (chainable)
element.Zoom()                        // zoom to fit
element.Isolate()                     // temporarily isolate in active view
element.Hide() / element.Unhide()     // hide/unhide in active view
element.Delete()                      // delete from document
```

---

## 9. Collection: Filtering

All filters preserve the generic element type and track pipeline counts.

### WhereParam — string match

```csharp
GetElements("Walls").WhereParam("Fire Rating", "2 hr")
GetElements("Walls").WhereParam("Comments", "!=", "")    // has a comment
```

### WhereParam — numeric

```csharp
GetElements("Structural Columns").WhereParam("Volume", ">", 1.0, "m3")
GetElements("Walls").WhereParam("Unconnected Height", ">=", 2.5, "m")
```

### WhereParam — string operators (contains, starts, ends)

```csharp
GetElements("Doors").WhereParam("Type", "starts", "Interior")
GetElements("Walls").WhereParam("Type Name", "contains", "HCB")
```

### WhereAnyParam

```csharp
// Matches if ANY of the named parameters contains the value
GetElements("Walls").WhereAnyParam(new[]{"Comments","Mark"}, "fire")
```

### WhereTypeParam — filter by type-level parameter

```csharp
GetElements("Walls").WhereTypeParam("Material", "contains", "HCB")
```

### WhereMatches — fuzzy name search

```csharp
GetElements<FamilyInstance>("Doors").WhereMatches("flush")
```

### WhereMaterial / WhereMaterialNot

```csharp
GetElements("Structural Framing").WhereMaterial("Concrete").Table()
GetElements("Structural Framing").WhereMaterialNot("Steel")
```

### Standard C# Where (lambda)

```csharp
GetElements<Wall>()
    .Where(w => w.GetNum("Unconnected Height", "m") > 3.0)
    .Table()
```

---

## 10. Collection: Sorting

```csharp
GetElements<FamilyInstance>("Doors")
    .OrderByParam("Width")
    .Table()

GetElements("Structural Columns")
    .OrderByParamDesc("Volume")
    .Table()
```

Automatically uses numeric sorting for Double/Integer parameters, string sorting otherwise.

---

## 11. Collection: Grouping & Aggregation

### GroupByParam — count per group

```csharp
GetElements("Structural Framing").GroupByParam("Type").Table()
// Group | Count
// Grade Beam | 81
// IntermediateBeams | 145
```

### GroupByParam with sum

```csharp
GetElements("Structural Columns").GroupByParam("Type", "Volume", "m3").Table()
// Group | Count | Total (m3)
// Basement Column | 21 | 3.250
```

### SumParam

```csharp
GetElements("Structural Framing").SumParam("Volume", "m3")  // 59.67
```

---

## 12. Collection: Bulk Write

All set operations run in a single transaction. All methods are chainable.

```csharp
GetElements("Walls")
    .WhereParam("Fire Rating", "None")
    .SetParam("Fire Rating", "2 hr")

GetElements("Structural Columns")
    .SetParam("Base Offset", -150, "mm")        // with unit conversion

GetElements("Doors")
    .SetParam("Mark", d => $"D-{d.RoomFrom()}")  // dynamic factory

GetElements("Walls")
    .SetParam("Mark", (w, idx) => $"W{idx+1:D3}") // indexed factory
```

---

## 13. Collection: Revit UI Actions

```csharp
elements.Select()                     // select in UI + zoom
elements.Zoom()                       // zoom to fit
elements.Isolate()                    // temporarily isolate
elements.Hide() / elements.Unhide()   // hide/unhide
elements.Delete()                     // delete all in one transaction
```

---

## 14. Collection: Notebook Export

```csharp
GetElements("Doors").ToNotebook("DoorAnalysis")
// → JSON file + auto-generated Jupyter Notebook, opens in VS Code
```

---

## 15. Numeric & Unit Helpers

### Unit Conversion

```csharp
// Input (human → Revit internal feet)
3.0.InputUnit("m")                    // 9.8425
150.InputUnit("mm")                   // 0.4921

// Output (Revit internal feet → human)
196.85.OutputUnit("m2")              // 18.29
area.OutputUnit("mm", 0)             // round to nearest mm

// String dimension parser
"50mm".ToMeters()                    // 0.05
"2ft".ToMeters()                     // 0.6096
```

### Formatting

```csharp
value.FormatUnit("m2")               // "18.29 m²"
value.FormatValueOnly("m2", 1)       // "18.3"
value.RoundTo("mm")                  // round internal value to nearest mm
```

### Unit Type Resolution

```csharp
UnitExtensions.GetUnitTypeId("m3")   // ForgeTypeId for cubic meters
```

Accepted unit strings: `mm`, `cm`, `m`, `km`, `in`, `ft`, `m2`, `sqm`, `ft2`, `sqft`, `m3`, `cum`, `ft3`, `cuft`, `deg`, `%`, `kg`, `nr`, `no`

### Precision-Aware Comparisons (fuzzy equality)

```csharp
x.IsAlmostEqualTo(y)                 // tolerance 1e-9
x.AlmostZero()                       // |x| < 1e-9
x.IsLessThan(limit) / IsGreaterThan(limit)
x.IsPositive() / IsNegative()
```

---

<!-- #PRO-ONLY-BEGIN  Pro-only engines — Clash Detection (CoordinationExtensions.cs) and Curtain Grid Repair (CurtainGridRepairExtensions.cs). gen-engine-docs.py strips this region from the free-repo copy; do not remove the markers. -->
## 16. Coordination & Clash Detection

```csharp
// Source collection vs target category
GetElements("Pipes").AuditClashes("Structural Framing").Table()

// With tolerance
GetElements<Pipe>("Pipes").AuditClashes("Walls", "2mm").Table()

// Two explicit collections
sourceElements.AuditClashes(targetElements, 0.01).Table()

// Cleanup
Doc.ClearClashHelpers()
```

`.Table()` on clash results renders an interactive table AND creates visual helper geometry in the model.

---

## 17. Curtain Grid Repair

A curtain wall's grid spacing is a **type** parameter, and Revit offers no minimum. Set "Vertical Grid = Fixed Distance 900 mm" so a 900 mm door fits between two mullions, and Revit lays the lines out at 900, 1800, 2700 … and leaves whatever is **left over** as the last bay. On a 3100 mm wall that last bay is 400 mm — a mullion 400 mm from the jamb — and if the remainder rounds to zero you get two **coincident** grid lines, two mullions in the same place, and a zero-width cell.

There is no API to delete a grid line (`CurtainGrid` exposes `AddGridLine` and nothing else, and `Mullion` exposes no delete), so the only lever is the **segment**: removing a grid line's segments deletes its mullions.

```csharp
// 1. Look first — read-only. Reports every bay narrower than the minimum (default 500 mm).
selectedWall.AuditNarrowBays().Table()
selectedWall.AuditNarrowBays(600).Table()
GetElements<Wall>().AuditNarrowBays().Table()

// 2. Merge them. Removes the offending grid line's segments, so the bay merges into
//    its neighbour and the mullion goes with it.
selectedWall.MergeNarrowBays().Table()
selectedWall.MergeNarrowBays(500).Table()
GetElements<Wall>().MergeNarrowBays(500).Table()          // one transaction

// One axis only (Vertical = the mullion bays along the wall, Horizontal = the transoms)
selectedWall.MergeNarrowBays(500, CurtainBayAxis.Vertical).Table()

// 3. Phantom members (defect D38) — ids a grid still RETURNS but no longer CONTAINS.
selectedWall.PurgeGhostMembers().Table()
GetElements<Wall>().PurgeGhostMembers().Table()
```

**The second cleanup — segments whose mullion was deleted.**

Select a mullion, unpin it, delete it: the mullion goes, but the grid line's **segment stays existing**. The division outlives the member — so the wall reports two panels where one continuous pane was intended, and the grid line is still drawn in every view. `RemoveMullionlessSegments` removes those segments, which merges the panels and takes the line out of the view.

```csharp
// 4. Remove every segment that has no mullion on it.
selectedWall.RemoveMullionlessSegments().Table()
GetElements<Wall>().RemoveMullionlessSegments().Table()          // one transaction
selectedWall.RemoveMullionlessSegments(CurtainBayAxis.Vertical).Table()
```

Measured on the villa, 2026-10-05 — 28 curtain walls, **33 mullion-less segments on 10 walls**:

| Wall | Existing segments | Mullion-less | Note |
|---|---|---|---|
| 544635 | 10 | **6** | all three vertical lines stripped by hand |
| 478741 | 10 | 6 | also carries the 4 phantom mullions |
| 512772 | 15 | 4 | |
| 804823 / 807435 / 807526 / 807593 | 10 | 1 each | a horizontal segment |
| the other 18 walls | — | **0** | ⚠ the test does not manufacture orphans |

**Emptying a line is supported.** Removing a line's *last* segment makes Revit post *"Curtain grid lines must have at least one segment"*. That is a **warning with no consequence** — the owner's own hand edit leaves wall 804645's line 804659 at `existingSegs 0 / skippedSegs 2`, and that wall is healthy (8 panel ids = 6 built + 2 ghost, which the schedule already reports as 6). But the warning raises a **modal dialog**, and a modal dialog blocks the API — which is why this cleanup could not be automated before. Every transaction these tools open now installs a failures preprocessor that deletes warnings. Measured in the REPL: `preprocessor calls=1, warningsDeleted=3`, commit completed, no dialog. ⚠ Only **warnings** are deleted — an error still fails the transaction.

**The merge rule.** Boundaries are the two ends of the axis plus every grid line that still has a live segment. A bay shorter than `minBayMm` is fixed by removing its **starting** boundary, so it merges *backwards* into its neighbour — for the trailing bay that is exactly "remove the last grid before reaching the edge". A leading bay has no removable start (the wall edge), so its ending boundary goes instead. Removals are re-scanned from the far end after each one, so a wall needing two merges gets both.

**What is measured, not assumed.** On the villa, 2026-10-05:

| Wall | Type / layout | Bays | Result |
|---|---|---|---|
| 512772 | Type4, Fixed Distance 900, 5000 mm | 900/900/900/900/**500** | left alone — exactly the minimum |
| 804556 | Type2, Fixed Distance 900, 3100 mm | 900/900/1300 | already merged; no-op |
| 544635 | Type4, Fixed Distance 900, 2900 mm | 900/900/900/**200** | flagged **Trailing**, merged to 1100 |
| 478741 | Type4, Fixed Distance 900, 2550 mm | two lines at **900** | flagged **Coincident** (0 mm), merged to 900 |

`MergeNarrowBays` returns one row per bay with the axis, kind, the offending width, the merged width, the removed line id, and the type's own layout and spacing. `.Table()` renders it and states the headline. An empty result prints "no narrow bays".

**Notes.**

- ⚠⚠ **DO NOT run this on a wall whose glazing is BUTT-JOINTED BY DESIGN.** In real construction there are glass walls with no mullions at all, and their panels must still be reported **separately**. This method cannot tell that intent from a mullion that was deleted by mistake — it removes **every** mullion-less segment on the wall it is given. Two consequences:
  - Call it on **`selectedWall`**, not `GetElements<Wall>()`, unless you genuinely mean it across the model.
  - It is **all-or-nothing per wall** — there is no "remove these three, keep those two". Preserve by hand the ones you want to keep, or leave that wall alone.
- ⚠ The layout *mode* is `SPACING_LAYOUT_VERT` / `SPACING_LAYOUT_HORIZ` and the *spacing* is `SPACING_LENGTH_VERT` / `SPACING_LENGTH_HORIZ`. `CURTAINGRID_BELT_U/V` are **not** the spacing — they do not exist on these types.
- ⚠ `GetVGridLineIds()` are the **vertical** grid lines (the mullion bays); `GetUGridLineIds()` are the horizontal ones (the transoms). The U/V naming is the opposite of what it looks like.
- The grid line **element** survives the merge with zero existing segments — that is Revit's behaviour, and it matches the state a hand edit leaves behind. It is skipped on a re-run, so the tool is idempotent.
- `PurgeGhostMembers` deletes singly and tolerates refusal: Revit refuses every phantom **panel** and some phantom mullions, and a multi-id `Delete` is atomic, so one refusal would otherwise block the lot.
- ⚠ `RemoveMullionlessSegments`'s test is **geometric**: a *live* mullion, parallel to the segment, whose midpoint lies on it to within 6 mm. 18 of the 28 walls report zero orphans at that band, which is what makes it trustworthy rather than trigger-happy. Ghost mullions are excluded, so an already-orphaned member can never excuse a segment.
- ⚠ What the cleanup **leaves behind** is not a defect and is not fixed here: a merge strands one ghost panel per removed division (Revit refuses to delete phantom panels), and the perpendicular mullion pieces do not become one element. Both are already absorbed downstream — by the built-panel test and by `MullionMemberCount`.
- All writers open their own transaction unless one is already active, so they are safe inside a script's own `Transact`.

<!-- #PRO-ONLY-END -->

---

## 18. Global ScriptApi Methods

These are called directly without a prefix — available in every script.

### Properties

```csharp
Doc           // current Document
UIApp         // current UIApplication
UIDoc         // current UIDocument
ActiveView    // current active View
Selection     // current selected elements
Parameters    // parameters from agent/UI context
```

### Output

```csharp
Println(message)          // print to console
Table(object)             // render list as interactive table
Table(elements)           // render elements (adapts columns to element kind)
BarGraph(data)            // bar chart
PieGraph(data)            // pie chart
LineGraph(data)           // line chart
Show("table", data)       // generic render
```

### Element Retrieval

```csharp
GetElement<Wall>("name-or-id")              // single element
GetElements<Wall>()                         // all Walls (typed)
GetElements<FamilyInstance>("Doors")        // typed, door category
GetElements("Walls")                        // untyped
GetElements(BuiltInCategory.OST_Doors)      // by BuiltInCategory
GetMagicNames()                             // all discoverable categories/classes
GetCategories()                             // all Revit categories in doc
```

### Transactions

```csharp
Transact("My Operation", () => { /* modify doc */ });
Transact("With Doc Access", doc => { /* use doc */ });
Regen()                   // regenerate the document (opens the transaction for you)
```

⚠ `Doc.Regenerate()` requires an open transaction — called outside one it throws *"Modification of
the document is forbidden"*, which names neither the method nor the cause. `Regen()` wraps it.
You rarely need it: a committed transaction already regenerates, and `ExportImage` exports after the
model has settled.

### UI Actions (on collections, without prefixes)

```csharp
Select(elements)          // select + zoom in Revit
Isolate(elements)         // isolate + zoom
Zoom(elements)            // zoom to fit
```

### Image Export

Render a view to an image file — how a script, or an AI agent driving the REPL, **looks** at what
it built. Returns the path that was actually written.

```csharp
// Active view → returns the file that exists
var shot = ExportImage(@"C:\tmp\current");

// A named view, at 2000 px
var elev = ExportImage(@"C:\tmp\north-elev", "North Elevation", 2000);

// Keep the level/grid tags in the picture (they are suppressed by default)
var tagged = ExportImage(@"C:\tmp\tagged", "Ground Floor", 2000, hideAnnotation: false);
```

⚠ **Use the RETURN value — it is the file that exists, not the path you passed.** Revit appends the
view identity to the base name and may change the extension: asking for `C:\tmp\shot` on the default
3D view writes `C:\tmp\shot - 3D View - {3D}.jpg`. **A 3D or shaded view is written as `.jpg` even
though PNG is requested.**

⚠ **Annotation is suppressed by default** (`hideAnnotation: true`). Revit's export does not clip
annotation to the view, so level heads, grid bubbles and elevation/section marks are drawn wherever
they sit — and because the whole extent is fitted to the page, they **shrink the subject**. A plan
view with elevation markers beside it renders the building into a fraction of the frame. The whole
`CategoryType.Annotation` set is hidden for the export and restored afterwards (no undo entry).

- Pass the path **without** an extension. The directory is created if it does not exist.
- `viewName` omitted ⇒ the **active view**. Matched case-insensitively; view templates are rejected.
- **No `Transact()` needed** — the suppression transaction is opened and rolled back internally, so
  the model and the view are unchanged when this returns.

---

## 19. Complete Fluent Chain Examples

```csharp
// Doors on Level 1, sorted by width
GetElements<FamilyInstance>("Doors")
    .WhereParam("Level", "Level 1")
    .StandardDoor()
    .OrderByParam("Width")
    .Table()

// Concrete framing by type with volume totals
GetElements("Structural Framing")
    .WhereMaterial("Concrete")
    .GroupByParam("Type", "Volume", "m3")
    .Table()

// Find and fix missing fire ratings
GetElements("Walls")
    .WhereParam("Fire Rating", "None")
    .SetParam("Fire Rating", "2 hr")
    .Select()

// Heavy columns
GetElements<StructuralColumn>("Structural Columns")
    .WhereParam("Volume", ">", 1.0, "m3")
    .OrderByParamDesc("Volume")
    .Table()

```
<!-- #PRO-ONLY-BEGIN Pro-engine fluent examples — Clash Detection (CoordinationExtensions.cs) and Curtain Grid Repair (CurtainGridRepairExtensions.cs); gen-engine-docs.py strips this from the free-repo copy -->
```
GetElements("Pipes")
    .AuditClashes("Structural Framing", "5mm")
    .Table()
```

```
// Curtain grids: look first, then merge anything under 500 mm, then clear the phantoms
GetElements<Wall>().AuditNarrowBays().Table()

GetElements<Wall>().MergeNarrowBays(500).Table()

GetElements<Wall>().RemoveMullionlessSegments().Table()

GetElements<Wall>().PurgeGhostMembers().Table()
```
<!-- #PRO-ONLY-END -->
