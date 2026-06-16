# Route 29 Manual Tree Labeling

## Goal

Create independent ground truth for individual visual headbutt trees.

## Files

- `route29_tree_label_sheet.svg`: printable/drawable coordinate sheet.
- `route29_tree_labels_template.csv`: machine-readable tile template.

## Labeling Rules

- Blank tile means not part of a tree.
- A number means this tile belongs to that individual tree.
- All tiles with the same number are one tree.
- Different trees must use different numbers.
- Do not label canopy/top tiles separately yet.
- Do not use the Headbutt archive to choose labels.
- Do not use permission-grid shapes as proof of tree identity.

## Preferred Data Entry

The most reliable format is the CSV:

```text
x,y,tree_id,tile_note,permission_value_hex,permission_class
```

Fill `tree_id` only. Leave `permission_*` columns unchanged; they are coordinate/debug context only.

If labels are drawn on the SVG/image instead, convert them back into the CSV before verification.

The interactive labeler and blank sheet include one padding row north of Route 29 (`y=383`) and one south padding row (`y=416`) so edge trees can be labeled without fighting the page border. Existing labels are keyed by world coordinate, so changing the crop does not move them.
