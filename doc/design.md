# Design notes

Why the add-on looks the way it does. Numbers here were measured on this machine (Blender
5.2.2 LTS, X-Plane 12 install) and are quoted with the file they came from.

See also: [`usage.md`](usage.md), [`sound-space.md`](sound-space.md).

## Why Speaker objects, not Empties

| Speaker gives | Used for |
|---|---|
| object location | `VEH_XYZ` (origin offset applied) |
| cone + rotation | `VEH_THE` / `VEH_PSI` / `VEH_PHI` — the cue's facing direction |
| `sound` datablock | auditioning: attach an `Assets/*.ogg` and play it |
| `muted` | muted by default; `Solo selected` auditions one cue |

A Speaker's own volume/attenuation fields have no counterpart in `.snd` (FMOD owns those), so
the truth stays in custom properties: `snd_event`, `snd_conds`, `snd_part`, `snd_xyz`,
`snd_line`.

## Why custom properties live on the Object, not on the Speaker datablock

One `.snd` attachment is **one placement** (a sound, at this position, under these conditions),
not "a kind of sound". Speaker datablocks are shareable:

```python
dup = bpy.data.objects.new("copy", src.data)
dup.data == src.data          # True — Alt+D, or any manual data sharing
```

Metadata on `obj.data` would then be shared by both objects and export would fight itself.
On the Object it is per instance, which is what an attachment is.

Other reasons: position already lives on the Object (`obj.location`), so splitting name and
conditions onto the datablock would force the user to jump between two panels to edit one
attachment; swapping the Speaker datablock keeps the metadata; and
`Object ▸ Custom Properties` is where script-facing per-instance data conventionally lives.

The cost is real: a `Shift+D` copy inherits `snd_uid`. Import therefore records
`uid → object name` in the scene property `xplane_snd_owners`, and export **claims the
original by name** — objects whose name does not match are appended as new attachments
(`tests/duplicate.py` covers it).

## Why export patches lines instead of regenerating

`.snd` files are hand-laid-out documents — a C90B file is 2993 lines of which 288 are
comments and 272 are blank. Regenerating them destroys the author's layout and makes the diff
useless. So the file is kept as raw lines (`splitlines(keepends=True)`, read and written with
`newline=''`), and only lines whose values actually changed are rewritten, reusing their
original indentation.

Guards that make this safe:

- values are compared before writing, so an untouched file is written back byte for byte;
- inserted lines shift every later line index (`_shift_after()` maintains attachments,
  volumes, `BLEND_DEPTH`/`SOUND_INDEX` and general directives);
- the scene keeps the source text, so reopening a saved `.blend` still has a baseline to patch
  against; after a successful export that baseline is refreshed to the written content.

Measured: 56 `.snd` files from a full X-Plane 12 installation round-trip byte-identically.

## Coordinate model

`VEH_XYZ` and sound-space volumes are metres in aircraft axes relative to an origin that is
either `REF_POINT_ACF` or the aircraft's default CG from the `.acf`. Axis conversion is a pure
rotation (`(x, y, z) → (x, -z, y)`, determinant +1), and export applies the inverse. The
inverse is computed from the mapping itself, never by "undoing the transform we applied",
because float32 does not cancel a rotation and its inverse exactly.

Sound-space editing uses the same path: world bounds → inverse axis mapping → subtract origin.

## Events are 1:N and conditions stay per object

A C90B carries 436 attachments across 96 distinct `EVENT_NAME`s: mean 4.54 positions per
event, median 1, max 39 (`garmin`, one per button). Of the 38 multi-member groups, **none** has
identical conditions across members — each position carries its own parameter index. That is
why grouping is only a navigation aid (one collection per event) and every condition stays on
its own object.

## Sound space drawing

Covered in [`sound-space.md`](sound-space.md): two nested wire volumes (boundary + inset
core), solid faces with a `Wireframe` modifier so the colour survives Solid shading, and
`show_in_front` so the boxes remain visible through the fuselage.
