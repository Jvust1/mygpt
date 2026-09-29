# Skin Full-Utilization Plan

Updated: 2026-09-29

## 1. Goal

From this point forward, a skin package is not considered "integrated" merely because one skeleton, one atlas, one texture, or one idle animation can be displayed.

The integration target is **full package utilization**:

> inventory everything first, reconstruct the package capability graph, then expose as much of the skin's authored behavior as is technically valid, useful, and permitted.

For mygpt, the visible companion should use the full expressive capacity of a Live skin rather than flattening a rich package into one default pose.

## 2. Core rule

For every new skin package, the integration process MUST:

1. enumerate every file in the package;
2. identify every renderable model / skeleton / atlas / texture set;
3. identify every animation, expression, costume, alternate state, effect, physics/config file and transition rule;
4. parse configuration files before choosing a "main" runtime path;
5. build a **Skin Capability Manifest**;
6. build a **Skin State Graph** describing legal transitions;
7. implement all supported, useful states before declaring the skin "fully integrated";
8. explicitly record anything intentionally unsupported and why;
9. test each declared capability on the target runtime;
10. keep Live as the asset authority and let mygpt consume a normalized capability contract.

A renderer that only loads the first valid skeleton is an **initial compatibility probe**, not a completed skin integration.

## 3. Responsibility split

### Live

Live owns:

- original skin packages;
- decrypted/private runtime packages where authorized;
- package inspection;
- resource inventories;
- runtime-family detection;
- variant/costume/state discovery;
- animation inventory;
- transition discovery;
- authoritative Skin Capability Manifest;
- asset hashes and identity;
- runtime-specific asset adapters.

### mygpt

mygpt owns:

- companion intent;
- conversation state;
- supervision state;
- emotion/interaction cues;
- mapping those semantic cues to Live capabilities;
- graceful fallback when a capability is unavailable.

mygpt must not hard-code one texture or one animation as the meaning of a whole skin when Live exposes richer capabilities.

## 4. Mandatory package inspection

Before renderer implementation, produce a machine-readable inventory containing at least:

- package ID;
- package SHA-256;
- package format/version;
- all files and sizes;
- per-file SHA-256;
- likely role of every file;
- all skeleton/model files;
- all atlas files;
- all texture files;
- all config/manifest files;
- all effect/shader files;
- all alternate model sets;
- orphan/unreferenced files;
- duplicate resources;
- declared and discovered runtime versions.

No resource may be labeled "misc/unused" merely because its filename is opaque.

Opaque filenames must be resolved through config references, atlas references, binary metadata and cross-file relations.

## 5. Skin Capability Manifest

Each skin should eventually expose a normalized manifest similar to:

```json
{
  "skin_id": "example",
  "runtime": "spine",
  "runtime_version": "4.1",
  "forms": {
    "default": {},
    "aim": {},
    "cover": {}
  },
  "animations": {},
  "expressions": {},
  "transitions": {},
  "effects": {},
  "fallbacks": {},
  "unsupported": []
}
```

The exact schema may evolve, but the normalized concepts should stay stable.

### Capability classes

A capability can be one of:

- **form** — alternate model/costume/loadout;
- **animation** — idle/action/reaction/loop;
- **expression** — facial or parameter state;
- **transition** — form-to-form or mode-to-mode animation;
- **effect** — particle/shader/attachment behavior;
- **interaction** — tap/drag/hover/reaction;
- **camera/layout** — authored bounds, scale or anchor rules;
- **metadata** — names, groups, tags and semantic hints.

## 6. Skin State Graph

Skins with multiple forms must not be represented as independent unrelated models.

Live should construct a graph such as:

```
default
  ├─ to_aim   → aim
  └─ to_cover → cover

aim
  ├─ aim_idle
  ├─ aim_fire
  └─ to_cover → cover

cover
  ├─ cover_idle
  ├─ cover_reload
  └─ to_aim → aim
```

The graph should distinguish:

- persistent states;
- transient actions;
- looping animations;
- one-shot reactions;
- legal transitions;
- fallback transitions;
- return-to-idle behavior.

If the package config declares transition logic, that configuration is authoritative over filename guessing.

## 7. 3714430278 correction and target

The first Android integration treated the `c610_00` resource set as the primary runtime and treated `misc_*` files as secondary/opaque resources.

That is no longer sufficient.

For `3714430278`, the package must be treated as a multi-state skin with at least the following discovered sets:

### Default form

- `skeleton.bin`
- `c610_00.atlas`
- `c610_00.png`
- associated `model.json`
- idle and tap/reaction animation inventory

### Aim form

- `misc_01.bin`
- `misc_02.atlas`
- `misc_04.png`
- `misc_06.json`
- known behaviors include `aim_idle` and `aim_fire`

### Cover form

- `misc_08.bin`
- `misc_03.atlas`
- `misc_05.png`
- `misc_07.json`
- known behaviors include `cover_idle` and `cover_reload`

### Known transitions

Configuration references indicate state-changing behavior including:

- `to_aim`
- `to_cover`
- `change_cos`

The implementation target is therefore:

```
default <-> aim <-> cover
```

with the actual legal edges determined from package config rather than assumptions.

The current default-only renderer remains useful as a compatibility proof, but it is not considered full skin integration.

## 8. Runtime architecture

Introduce a renderer-neutral capability interface.

Conceptually:

```
SkinRuntime
  loadSkin(capabilityManifest)
  listForms()
  setForm(formId)
  play(animationId)
  setExpression(expressionId)
  trigger(interactionId)
  transition(targetForm)
  resetToIdle()
  getCurrentState()
```

Runtime-specific implementations may include:

- Spine;
- Live2D/Cubism;
- static image;
- future formats.

mygpt should talk only to normalized semantic capabilities, not raw Spine filenames.

## 9. Semantic mapping in mygpt

mygpt cues should map to capabilities through a configurable policy.

Example for 3714430278:

| mygpt meaning | preferred skin behavior | fallback |
|---|---|---|
| Silent Presence | current-form idle | default idle |
| Listening | smile / attentive idle | idle |
| Needs Input | smile / surprise | idle |
| Gentle Check-in | action | idle |
| Positive Feedback | smile / special | action |
| Error / Concern | sad | idle |
| User says no | no | idle |
| Surprise | surprise | action |
| Active task mode | aim form + aim_idle | default idle |
| Focus / defensive mode | cover form + cover_idle | default idle |

These mappings are examples, not immutable product decisions. They should be editable without rewriting the renderer.

## 10. Interaction mapping

Every skin integration should evaluate:

- tap head;
- tap body;
- drag;
- double tap;
- long press;
- wake;
- sleep;
- app foreground;
- app background;
- Book session start/end;
- user help request;
- praise/success;
- repeated error;
- idle timeout.

Only interactions actually supported by the package should be exposed.

Unsupported interactions should degrade gracefully rather than inventing animation names.

## 11. Variant and costume policy

If a package contains multiple full model sets, they should be classified before deciding whether they are:

- costumes;
- poses;
- combat states;
- equipment states;
- camera-specific variants;
- alternate resolutions;
- fallback resources.

Do not assume a second texture is "unused".

If a config contains `change_cos` or equivalent, treat that as strong evidence of a deliberate authored variant and preserve the transition.

## 12. Animation inventory requirements

For every skeleton/model set:

- enumerate animation names from the runtime data;
- record duration;
- record loop suitability;
- record form/state compatibility;
- identify transition animations;
- identify reactions;
- identify idle candidates;
- identify duplicate aliases;
- identify animations referenced by config but absent from the binary;
- identify binary animations not referenced by config.

The manifest should clearly distinguish:

- discovered in binary;
- declared in config;
- verified on renderer;
- device-verified.

## 13. Texture and atlas utilization

For every texture:

- trace which atlas references it;
- trace which skeleton/model references that atlas;
- record PMA mode;
- record dimensions;
- detect unused atlas regions if practical;
- detect alternate atlases/resolutions;
- do not discard opaque textures until the dependency graph proves they are unreachable.

## 14. Effects utilization

Visual effects may be inventoried and used when they contribute to the character presentation. **Audio is explicitly out of scope for skin integration.** Voice, BGM and SFX are not loaded, not played, not required for coverage, and do not affect skin completion status.

## 15. Coverage metric

Every integrated skin receives a utilization report.

Example:

```
files discovered:          13 / 13
model sets classified:      3 / 3
model sets renderable:      3 / 3
animations discovered:     18 / 18
animations renderer-tested: 16 / 18
transitions implemented:    4 / 4
textures mapped:            3 / 3
unknown resources:          0
device verified:            partial
```

A skin should not be called "fully utilized" while substantial resources remain classified as unknown.

## 16. Integration maturity levels

### L0 — Package detected
Format and package identity known.

### L1 — First frame
At least one model renders.

### L2 — Primary animation
Primary idle/action works.

### L3 — Full inventory
All package resources classified.

### L4 — Full capability implementation
All supported forms, animations and transitions are wired.

### L5 — Semantic companion mapping
mygpt cues use the skin's expressive capabilities.

### L6 — Device acceptance
All declared capabilities tested on the target device.

### L7 — Optimized production profile
Memory, battery, loading, caching and lifecycle behavior meet release requirements.

**Future work must not treat L1/L2 as completion.**

## 17. Loading strategy

For rich skins:

1. parse the manifest/config first;
2. lazy-load expensive alternate forms when appropriate;
3. pre-load transition-critical assets where latency would be visible;
4. cache decoded runtime state in app-private storage;
5. release unused GPU resources under memory pressure;
6. preserve current form/state across ordinary Activity recreation when safe;
7. fall back to default form if a secondary form fails.

Full utilization does not mean all resources must remain resident in RAM simultaneously.

## 18. Error handling

When one form fails:

- keep the skin usable through another verified form;
- report the failing resource and hash;
- mark capability degraded;
- do not mark the whole package invalid unless core identity fails.

When the package is repacked:

- verify authoritative core resource hashes;
- distinguish container hash from content identity;
- preserve the exact origin/provenance record.

## 19. Testing matrix

Each skin should be tested for:

- package identity;
- all model sets loading;
- first frame for every form;
- idle loop for every form;
- every transition;
- every mygpt semantic cue;
- rapid transition cancellation;
- repeated tap/action calls;
- Activity background/foreground;
- screen rotation if supported;
- process recreation;
- low-memory reload;
- invalid package recovery;
- fallback behavior;
- no stale resources after skin change.

## 20. Android acceptance for 3714430278

The next 3714430278 acceptance should no longer stop at "default idle appears".

Required evidence should include:

- default first frame;
- default idle;
- aim first frame;
- aim_idle;
- aim_fire;
- transition into aim;
- cover first frame;
- cover_idle;
- cover_reload;
- transition into cover;
- return transition(s);
- existing tap/reaction animations;
- background/reopen while preserving a valid state;
- fallback to default if an alternate form fails;
- no manual ZIP selection in the normal bundled path.

## 21. Governance rule

From this plan forward:

> A skin integration is complete only when the package has been fully inventoried, all meaningful capabilities are either implemented or explicitly documented as unsupported, and the implemented capability set has acceptance evidence.

"One model renders" is compatibility evidence, not completion evidence.

## 22. Deliverables for every future skin

Each future skin should produce:

1. `skin_inventory.json`
2. `skin_capabilities.json`
3. `skin_state_graph.json`
4. runtime adapter configuration
5. semantic cue mapping
6. utilization report
7. device acceptance receipt

These may eventually be generated automatically by Live tooling.

## 23. Immediate implementation order

For `3714430278`:

1. fully parse `model.json`, `misc_06.json`, `misc_07.json`;
2. validate which skeleton/atlas/texture each config controls;
3. enumerate every Spine animation from all three skeleton binaries;
4. build the normalized capability manifest;
5. implement multi-form loading;
6. implement `change_cos` / transition state machine;
7. map mygpt cues to the richer animation set;
8. keep all skin audio disabled and outside the runtime contract;
9. test default / aim / cover on Xiaomi 14;
10. record coverage and remaining unsupported capabilities;
11. only then mark the skin fully integrated.

