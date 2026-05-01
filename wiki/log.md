# Wiki Log

Append-only timeline of wiki events.

The wiki-maintainer appends one entry only when it changes wiki memory.

## Template

```markdown
## [YYYY-MM-DD HH:MM] finding_added | <finding_id_or_page>

- Summary: <one sentence describing the reusable guidance added or updated>
- Sources: <task_id, task_id or none>
- Pages touched: <wiki/general/page.md or wiki/categories/label.md>
```

Copy the template and fill the bracketed fields. Do not edit old entries.

## Event Types

- `annotation_round`
- `finding_added`
- `finding_updated`
- `index_refresh`
- `bbox_overlay`
- `manual`

## Entries

## [2026-05-01 01:48] finding_added | categories/amputation_arm/004

- Summary: Added guidance that blood-like fluid supports arm amputation only when visually tied to an abrupt arm termination.
- Sources: amputation_arm__4916_c130_crash_P2D4_A1_S2_frame_000478_p3_69d34a5b3306c5fa2a0aaff0, amputation_arm__0537_y2_extracted_rosbag2_2025_01_01-06_13_29_combined__vehicle_9_vio_eo_image_compressed_frame_000421_p1_69d34a5c3306c5fa2a0abaf8
- Pages touched: wiki/categories/amputation_arm.md

## [2026-05-01 06:22] finding_added | categories/amputation_leg/004

- Summary: RGB trauma cues at the termination point
- Sources: amputation_leg__4673_c130_crash_P2D4_A7_S2_frame_000264_p9_69d34a5c3306c5fa2a0ab31e
- Pages touched: wiki/categories/amputation_leg.md
