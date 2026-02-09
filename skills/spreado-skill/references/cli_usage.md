# Spreado CLI Commands Reference

## Authentication (Login)
Login to platforms to save cookies.
```bash
spreado login <platform> [--cookies <path>]
```
**Platforms**: `douyin`, `xiaohongshu`, `kuaishou`, `shipinhao`

## Status Check (Verify)
Check if credentials are still valid.
```bash
spreado verify <platform|all> [--parallel]
```

## Video Upload
Upload videos with metadata and scheduling.
```bash
spreado upload <platform|all> \
    --video <file> \
    --title "Title" \
    [--content "Description"] \
    [--tags "tag1,tag2"] \
    [--cover <image>] \
    [--schedule <hours|timestamp>] \
    [--parallel]
```

## Platform Specifics
- **Xiaohongshu**: Requires a cover image (`--cover`).
- **Douyin**: Supports detailed tags and location.
- **Shipinhao**: Supports description and scheduling.
