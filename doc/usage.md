# Using the add-on

Day-to-day workflow: import, look, edit, write back. For the sound-space zones see
[`sound-space.md`](sound-space.md); for why things are modelled this way see
[`design.md`](design.md).

## Import

- Drag a `fmod/*.snd` file into the 3D viewport (a `FileHandler` is registered, no file dialog).
- Or `File ▸ Import ▸ X-Plane SND (.snd)`.

Import options (press `F9` right after import to change them):

| Option | Default | Effect |
|---|---|---|
| Sound spaces | on | draw `AABB` / `SPHERE` listening zones as wire volumes |
| Group by event | on | one collection per `EVENT_NAME` |
| Speaker objects | on | use Speaker objects instead of Empties (orientation cone, auditionable) |
| Axis | align with imported mesh | `(x, y, z) → (x, -z, y)`, same as the OBJ8 importers |

## Coordinates

`VEH_XYZ` (and every sound-space volume) is in metres, aircraft axes (`+X` right, `+Y` up,
`+Z` aft), relative to an origin resolved in this order:

1. `REF_POINT_ACF <y> <z>` in the `.snd` → origin = authoring point + `(0, y, z)`;
2. otherwise the aircraft's default CG from the `.acf` (`acf/_cgY`, `acf/_cgZ`, feet → metres);
3. otherwise `(0, 0, 0)` plus a warning.

So `authoring position = VEH_XYZ + origin`. The add-on reads the `.acf` next to the `.snd`
(same folder or up to two levels up, because `.snd` usually lives in `fmod/`).

Measured on the default King Air C90B: after conversion, **84 %** of the 413 `VEH_XYZ`
positions land within 10 cm of the cockpit mesh, switch-type cues within 0.0–0.1 cm, and the
farthest one (`fuel_pump`, ±1.948 m) matches the wing.

## Axis

Blender is Z-up; X-Plane is Y-up with `+Z` aft. The transform used by the OBJ8 importers
(`io_scene_xplane_obj` / XPlane2Blender, `xpmesh.py: xp_to_bl`) is:

```
X-Plane (x, y, z)  ->  Blender (x, -z, y)
```

| Mode | Mapping | When |
|---|---|---|
| Align with imported mesh (default) | `(x, -z, y)` | overlay the sound positions on cockpit geometry |
| Raw aircraft coordinates | identity | compare numbers directly against the `.snd` |

Export inverts whichever mode was used at import, so both round-trip byte-identically.

Measured (C90B, 436 Speakers against 9 cockpit OBJ surfaces):

```
XP2B : min 0.0003  p50 0.083  p90 0.193   <=0.2 m 90 %   PASS
RAW  : min 2.121   p50 3.745  p90 3.940   <=0.2 m  0 %   FAIL (negative control, expected)
```

The 3.7 m offset in RAW is not "slightly off", it is one axis — the mapping is required.

## Edit

- Move a Speaker → its `VEH_XYZ`.
- Duplicate (`Shift+D`) → the copy has no owner record, so it is exported as a **new**
  attachment appended to the end of the file.
- Rename a whole event from the sidebar event list → every `EVENT_NAME` line of that group.
- Change an object's `snd_blend_depth` custom property (sound-space only) → `BLEND_DEPTH`.

## Export

`File ▸ Export ▸ X-Plane SND (.snd)`, defaulting to the imported path.

Export is a **line-level patch**, not a regeneration:

- untouched files are written back **byte for byte** (tabs, comments, blank lines, line endings);
- a moved Speaker rewrites exactly one `VEH_XYZ` line;
- new Speakers and new sound spaces are inserted, never reordered.

Measured: all **56 `.snd` files** in a full X-Plane 12 install (including payware, ground
vehicles, jetways, carriers) round-trip byte-identically; moving one Speaker produces a
one-line diff.

> Export overwrites the file you point it at. Keep a backup, or export to a copy and rename it.

## Sidebar panel

`View3D ▸ Sidebar (N) ▸ X-Plane ▸ X-Plane SND`

- file name, resolved origin and its source, current axis mode;
- attachment count (plus how many are new);
- `Write .snd`, `Solo selected`, `Mute all`;
- event list: name + how many Speakers, with select / isolate / rename-whole-group;
- sound-space list: area name (from the comment above the block), kind, `inside_ratio[n]`,
  blend distance, visibility toggle, `+` to add a volume or a new zone.

Speakers are muted at import. Blender's Speaker has no start/end frame, so every unmuted
Speaker plays at once — use `Solo selected` to audition one cue at a time.

## Events are 1:N

`EVENT_NAME` is "a sound"; `VEH_XYZ` is "the N-th position of that sound on this aircraft",
so one event normally carries many positions. Measured on the C90B:

| Metric | Value |
|---|---|
| attachments | 436 |
| distinct `EVENT_NAME` | 96 |
| members per event: mean / median / max | 4.54 / 1 / **39** (`garmin`, 39 buttons) |
| multi-member groups whose conditions are identical | **0 of 38** |

Because member conditions almost never match, conditions stay per object — lifting them to
"event level" would lose information. Grouping exists only for navigation: with
*Group by event* on, each event becomes a collection
(`SND C90B.snd / model / kingair_c90b / switches / pushbutton_sm`).

## Limitations

- Only `.snd`: no bank reading, no FMOD, no audio encoding.
- Trigger conditions are preserved and copied to duplicates but there is no condition editor.
- Sound spaces can be moved, resized, created and extended; **deleting** a zone or volume is
  not implemented — edit the text for that.
- Geometry overlay is optional: import the OBJ8 yourself with `io_scene_xplane_obj`; this
  add-on never calls it.
