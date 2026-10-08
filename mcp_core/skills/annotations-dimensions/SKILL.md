---
name: annotations-dimensions
description: Dimensions, tags and annotation — creating and READING dimension chains, room/door/window tags, tag orientation, text notes, room separation lines, and the traps that make a dimensioned drawing read wrong. Use for "add dimensions", "tag the rooms", "rotate the labels", "recreate this plan with its dimensions and room tags".
---

# Annotations & Dimensions

The **drawing** layer: dimensions, tags, text notes and room separation lines. Geometry that
looks right can still be an unusable drawing — a plan with no dimensions or untagged rooms
does not answer the question it was built for.

> **Scope.** Generalist Revit annotation. Room *schedules*, BOQ and quantities are elsewhere.

---

## ⚠⚠ The one rule: a formatted string is not a number

**NEVER read a dimension through `Dimension.ValueString`.** It is a *display artifact*, not a
measurement, and it is wrong in two different ways:

| Measured 2026-10-08, live | API said | Truth |
|---|---|---|
| a 5350 mm single-segment dimension | `ValueString = "535"` | **5350 mm** |
| a 7635 mm single-segment dimension | `ValueString = "764"` | **7635 mm** |
| every MULTI-segment dimension | `ValueString = ""` | non-empty |

`ValueString` reports the value in the **project's display units** — truncated to the project's
unit precision — and it **ignores the dimension type's own unit format**. In that document the
project unit is centimetres while the dimension type is `Linear - mm (Floor Plan)`, so the
*on-screen text reads 5350* and `ValueString` returns `535`. The same value, two answers.

**Read the number, then convert:**

```csharp
// single-segment dimension
var mm = (d.Value ?? 0.0).OutputUnit("mm");

// multi-segment — Value is null, walk the segments
foreach (DimensionSegment seg in d.Segments)          // ⚠ type the loop variable
    Println($"{seg.Value.OutputUnit("mm")}");
```

Two more traps in that snippet, both measured:

- ⚠ **`Dimension.Value` and `DimensionSegment.Value` are `double?`, not `double`.**
  `.OutputUnit()` on a `double?` fails with *"CS1929: 'double?' does not contain a definition
  for 'OutputUnit'"*. Null-coalesce first.
- ⚠ **`Dimension.Segments` enumerates as `object`** unless you declare the loop variable as
  `DimensionSegment`. `foreach (var seg in d.Segments)` gives *"CS1061: 'object' does not
  contain a definition for 'Value'"*.
- ⚠ **`OutputUnit` returns a `double`, not a string.** `string s = x.OutputUnit("mm");` is
  *"CS0029: Cannot implicitly convert type 'double' to 'string'"*.

---

## Creating a dimension chain

Verified signatures (Revit 2025, reflected live):

```
Document.Create.NewDimension(View, Line, ReferenceArray)
Document.Create.NewDimension(View, Line, ReferenceArray, DimensionType)
```

- The **`Line` is the dimension line itself** — it sets both the direction and the OFFSET at
  which the string sits. It must be parallel to the direction of the chain.
- The `ReferenceArray` is **ordered**: the dimension is measured between consecutive
  references in the order you append them.
- ⚠ The view must be a **plan/section/elevation** — `Doc.Create.NewDimension(ActiveView, …)`
  fails in a 3D view.

### The chain recipe

```csharp
// 1. Collect the references, IN ORDER along the chain. Name the order — do not rely on
//    the collector's order, which is not guaranteed to be geometric.
var walls = GetElements<Wall>()
    .WhereParam("Base Constraint", "Ground Floor")
    .OrderByParam("Id")
    .ToList();

var refs = new ReferenceArray();
foreach (var w in walls) refs.Append(new Reference(w));
Println($"references: {refs.Size}");

// 2. The dimension line: parallel to the chain, offset away from the wall by `offset`.
//    Compute it from the chain's own extent — never hardcode coordinates.
var a = ((LocationCurve)walls[0].Location).Curve.GetEndPoint(0);
var b = ((LocationCurve)walls[walls.Count - 1].Location).Curve.GetEndPoint(0);
var offset = 2.0.InputUnit("m");
var line = Line.CreateBound(
    new XYZ(a.X, a.Y + offset, a.Z),
    new XYZ(b.X, b.Y + offset, b.Z));

// 3. Create it.
Transact("dimension chain", () => Doc.Create.NewDimension(ActiveView, line, refs));
```

⚠⚠ **`new Reference(wall)` refers to the wall's own reference plane (its centreline)**, which is
what a wall-to-wall dimension chain wants. It does **not** refer to a face — for a
face-to-face dimension you must take the reference off `wall.Geometry` and match the face by
its `FaceNormal`. Mixing the two gives a chain that measures centreline-to-centreline while
looking like it measures faces.

⚠ **One `Transact` for the whole chain, not one per dimension.** A drawing with 12 dimension
strings is 12 undo entries otherwise.

⚠ **Stacking rows:** a second chain (wall thicknesses, window positions) needs a *different*
offset, or it draws on top of the first. Use a fixed ladder — overall at 3 m, wall thicknesses
at 2 m, openings at 1 m — so the rows read outward in a predictable order.

### Dimension types

```csharp
GetElements<DimensionType>().Select(t => new { t.Id, Name = t.Name }).Table()
```

⚠ **The project's display units and the dimension type are independent.** A `Linear - mm` type
inside a centimetre project still *displays* mm — that is why the on-screen text and
`ValueString` disagreed above. Do not conclude from `ValueString` that your dimension type was
ignored; check the exported image.

⚠ Creating a new `DimensionType` by duplication is a *type* edit — see `project-modeling`
recipe 13 for the duplicate-then-configure pattern, and remember a duplicated type starts with
the source type's settings, so verify the unit format afterwards.

---

## Tags

### Room tags

```
Document.Create.NewRoom(Level, UV)                      // ONE room, at a point. No tag.
Document.Create.NewRooms2(Level, Phase)                 // BULK, every enclosed region. TAGS THEM.
Document.Create.NewRooms2(Level)
Document.Create.NewRooms2(Phase, Int32)
Document.Create.NewRoomTag(LinkElementId, UV, ElementId)
Document.Create.NewRoom(Room, PlanCircuit)              // place into a known circuit
```

⚠⚠ **`NewRooms2` creates the tags for you.** If you then place your own with `NewRoomTag` you
get **duplicates** — the measured symptom is two stacked labels per room and a tag count double
the room count. Use `NewRoom(level, uv)` for a single room and add tags explicitly:

```csharp
Room room = null;
Transact("create room", () => { room = Doc.Create.NewRoom(lvl, new UV(x, y)); });
Transact("tag room", () =>
    Doc.Create.NewRoomTag(new LinkElementId(room.Id), new UV(x, y), ActiveView.Id));
```

⚠ **`LinkElementId` is required**, not a bare `ElementId` — that is the only `NewRoomTag`
overload. (For a non-linked room, `new LinkElementId(roomId)` is the right wrapper.)

⚠ **Count the tags, not just the rooms.** `GetElements<RoomTag>().Count()` must equal
`GetElements<Room>().Count()`; a mismatch is a duplicate or a missing label, and both are
invisible in a count of rooms alone.

### ⚠⚠ Tag orientation — tags CAN be rotated

A common and wrong belief is that a Revit room tag cannot be rotated. It can:

```csharp
tag.TagOrientation = TagOrientation.Vertical;   // Horizontal | Vertical | AnyModelDirection
```

- `IndependentTag.TagOrientation` is **read/write** (verified by reflection, 2026-10-08), and
  `RoomTag` inherits it from `SpatialElementTag`.
- ⚠⚠ **The enum member is `AnyModelDirection`, NOT `Model`.** The Revit UI's Orientation
  dropdown reads *Horizontal / Vertical / Model*, so an agent that copies the UI label writes
  `TagOrientation.Model` and gets a compile error. Use `AnyModelDirection` — it means the tag
  follows the element's own direction.
- Newly created tags are **`Horizontal`** (measured: all five room tags in the house model).
  A drawing whose labels are vertical needs this set explicitly, one `Transact` for all of them.
- ⚠ Tag orientation is a **per-instance** property. There is no type-level switch.

```csharp
Transact("vertical tags", () => {
    foreach (var t in GetElements<RoomTag>()) t.TagOrientation = TagOrientation.Vertical;
});
```

### Door / window tags

```csharp
Doc.Create.NewTag(Doc, element, false, TagMode.TM_ADDBY_CATEGORY, TagOrientation.Horizontal, point)
```

⚠ The point must be inside the host's extent, and the category must have a loaded tag family —
if `TagMode` finds no tag family for the category, nothing is placed and **no error is raised**.

---

## Text notes and room separation lines

```csharp
// TextNote.Create(Document, ElementId viewId, XYZ origin, String text, ElementId typeId)
// also: (…, Double width, String, …) and a TextNoteOptions overload — all four reflected live.
Transact("note", () => TextNote.Create(Doc, ActiveView.Id, new XYZ(x, y, 0), "AREA=38sqm", typeId));

// Room separation lines — for OPEN-PLAN areas that must still be separate rooms.
// Document.Create.NewRoomBoundaryLines(SketchPlane, CurveArray, View)
Transact("separation", () => Doc.Create.NewRoomBoundaryLines(sketchPlane, curves, ActiveView));
```

⚠ **A room separation line is not a wall** — it has no thickness, no height and no material, and
it does **not** appear in a wall schedule. It exists only to close a room boundary. If the
drawing shows a solid line, model a wall; if it shows a dashed line, model a separation line.

⚠ Room separation lines need a **`SketchPlane`** built from the view's plane
(`SketchPlane.Create(Doc, ActiveView.SketchPlane.Id)` is not valid — construct a `Plane` from
`ActiveView.Origin` and `ActiveView.ViewDirection`).

---

## ⚠⚠ Rooms are not valid until the transaction COMMITS

`IsPointInRoom`, `Room.Area`, `Room.Boundary` and the room's geometry all read the **regenerated**
model. Inside the same transaction that created the room:

- `IsPointInRoom` fails or answers against stale boundaries;
- `Room.Area` stays `0`.

**Split the work across calls**: create the rooms in one submission, then read membership and
areas in the next. This is also why a room placed inside walls that do not yet form a closed
loop reports `0 m²` — see `project-modeling` recipe 9.

---

## Verification for a drawing

Annotation is not in the geometry counts, so the Tier 1 check in `project-modeling` will not
catch a missing dimension. Check it separately:

```csharp
Println($"Rooms      {GetElements<Room>().Count()}");
Println($"Room tags  {GetElements<RoomTag>().Count()}   (must equal rooms)");
Println($"Dimensions {GetElements<Dimension>().Count()}");
Println($"Vertical   {GetElements<RoomTag>().Count(t => t.TagOrientation == TagOrientation.Vertical)}");
foreach (var d in GetElements<Dimension>())
    Println($"  dim {d.Id.IntegerValue}  segs={d.NumberOfSegments}  mm={(d.NumberOfSegments == 0 ? (d.Value ?? 0.0).OutputUnit("mm") : -1)}");
Println($"Warnings   {Doc.GetWarnings().Count}");
```

⚠⚠ **Then LOOK at it.** Annotation is exactly the thing a count cannot verify — a dimension can
exist, be correctly numbered, and still sit on top of another one. Export with
`export_view(annotations: "tags")` and read the drawing.

⚠ `export_view` defaults to `annotations: "model"`, which **hides** every dimension and tag. If
you exported and saw no dimensions, that is why — re-export with `"tags"`, not with a change to
the model.

---

## Traps already paid for

- ⚠⚠ **`ValueString` is a display string, not a measurement** — project units, truncated, empty
  for multi-segment. See the top of this skill.
- ⚠ **`Dimension.Value` / `DimensionSegment.Value` are `double?`**; `OutputUnit` returns
  `double`.
- ⚠ **`Dimension.Segments` needs an explicitly typed loop variable** or it is `object`.
- ⚠ **`NewRooms2` tags automatically** — adding your own gives duplicates.
- ⚠ **The tag-orientation enum member is `AnyModelDirection`, not `Model`.**
- ⚠ **Rooms and their geometry are stale until the transaction commits.**
- ⚠ **A room separation line is not a wall** and will not appear in a wall schedule.
- ⚠ **Renaming a room tag's type or the room does not re-run the drawing** — a stale tag can
  show the old name; re-check after a rename rather than trusting the label you just set.

---

## Typical usage

**"Recreate this plan with its dimensions"** → `project-modeling` (geometry first, verify it) +
`annotations-dimensions` (dimension chains, tags, text notes)

**"The labels should be vertical"** → `TagOrientation.Vertical`, one `Transact` for all tags

**"Are the dimensions right?"** → read `Value`/`seg.Value` in mm, **never** `ValueString`, then
`export_view(annotations: "tags")` and read the drawing

**"Add a room schedule"** → `query-filter` + `aggregate-group`
