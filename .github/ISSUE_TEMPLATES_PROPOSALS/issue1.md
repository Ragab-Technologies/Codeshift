## 🎯 Overview

Add an interactive mode that allows developers to preview changes file-by-file and create rollback checkpoints during migration.

## 💡 Value Proposition

**For Users:**
- **Reduced Risk**: See exactly what will change before committing
- **Granular Control**: Accept, skip, or edit changes on a per-file basis  
- **Easy Recovery**: Create checkpoints and rollback to any point
- **Confidence**: Interactive approval process builds trust in automated migrations

**For Business:**
- Increases conversion from `scan` → `apply` (currently a drop-off point)
- Reduces support requests about "broken" migrations
- Key differentiator from other migration tools

## ✨ Features

### Core Functionality
- Interactive TUI (Terminal UI) with rich formatting using existing `rich` dependency
- File-by-file preview and approval workflow
- Side-by-side diff visualization with syntax highlighting
- Multi-level undo/redo functionality
- Checkpoint system for creating named rollback points
- Git integration for automatic checkpointing

### User Actions Per File
- **Accept**: Apply the migration to this file
- **Skip**: Leave this file unchanged
- **Edit**: Open file in editor to make manual adjustments
- **Create Checkpoint**: Save current state with a name
- **View Full Diff**: See complete diff with more context
- **Quit**: Exit and save progress for later

## 🎨 User Experience Example

```bash
$ codeshift upgrade pydantic --target 2.5.0 --interactive

╭────────────────── File 1/23 ──────────────────╮
│ src/models/user.py - 5 changes                 │
╰────────────────────────────────────────────────╯

📄 Change 1/5: Replace .dict() with .model_dump()

   Before                    │   After
─────────────────────────────┼─────────────────────────────
  45 │ def serialize(self):  │  45 │ def serialize(self):
  46 │     return self.dict() │  46 │     return self.model_dump()

Confidence: HIGH

Actions: [A]ccept  [S]kip  [C]heckpoint  [Q]uit
> 
```

## 🏗️ Technical Implementation

### New Commands
```bash
codeshift upgrade <lib> --interactive        # Start interactive migration
codeshift checkpoint create "name"           # Create named checkpoint
codeshift checkpoint list                    # List checkpoints
codeshift checkpoint restore <name>          # Restore to checkpoint
```

### Architecture
```
codeshift/
├── interactive/
│   ├── __init__.py
│   ├── tui.py                   # Terminal UI using rich
│   ├── diff_viewer.py           # Diff visualization
│   ├── checkpoint_manager.py    # Checkpoint operations
│   └── session_state.py         # Track user decisions
└── utils/
    └── git_helper.py            # Git operations
```

### State Storage
State stored in `.codeshift/` directory:
```
.codeshift/
├── sessions/
│   └── session-abc123.json
├── checkpoints/
│   ├── after-models.json
│   └── after-api.json
```

## 📋 Implementation Tasks

### Phase 1: Core Interactive Mode (Week 1)
- [ ] Create `codeshift/interactive/` module
- [ ] Implement session state management
- [ ] Build TUI with rich
- [ ] Add `--interactive` flag to upgrade command
- [ ] Implement file-by-file review loop
- [ ] Add session persistence

### Phase 2: Checkpoint System (Week 2)
- [ ] Implement CheckpointManager
- [ ] Git integration (stash/branches)
- [ ] Checkpoint commands
- [ ] Checkpoint restoration
- [ ] Write tests

## 📊 Success Metrics

- **Adoption**: 40%+ of users try interactive mode
- **Conversion**: 80%+ interactive sessions result in apply (vs 60% non-interactive)
- **Support**: 30% reduction in "broken migration" issues

## 📦 Server-Side Requirements

**None** - Runs entirely client-side

Optional cloud features for Pro tier:
- Checkpoint cloud backup
- Session sharing

## 💰 Monetization

Core feature is free. Advanced features for paid tiers:
- Cloud checkpoint backup (Pro)
- AI-powered suggestions (Pro)
- Team session sharing (Team)

---

**Priority**: 🔴 High  
**Effort**: 📊 2 weeks  
**Impact**: 📈 High  
**Dependencies**: None
