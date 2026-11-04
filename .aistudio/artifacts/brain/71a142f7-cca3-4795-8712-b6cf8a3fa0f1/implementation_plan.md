# LLM System Prompt Update: Anatomy & Head Protection Notices

Update `backend/prompts.py` system prompts to incorporate two vital directives for the AI model:
1. **Upper-Body Anatomy Notice**: Inform the AI that it has **NO legs, knees, hips, ankles, or feet**, while keeping the existing official ASCII body structure tree strictly intact.
2. **Head & Neck Safety Directive**: Instruct the AI to explicitly **protect its head and neck at all times**, avoiding self-damage or slamming its head into the ground/wall during chest locomotion or punching routines.

> [!IMPORTANT]
> Confirmed user directives:
> - **ASCII Tree**: Keep the existing `_OFFICIAL_BODY_STRUCTURE` ASCII tree structure strictly untouched.
> - **Anatomy Clarification**: Append explicit notice informing the LLM that the body consists strictly of upper-body parts (CHEST, NECK, HEAD, RIGHT_ARM, LEFT_ARM) with zero lower-body parts (no knees, legs, hips, or feet).
> - **Head & Neck Safety Directive (NEW)**: Add explicit safety rules warning the AI that head/neck destruction causes instant loss, requiring it to avoid hitting its own head against the ground/wall or striking itself during movements.
> - **Tests**: Run Python backend tests (`test_official_spec.py` & `test_all.py`) to verify complete prompt and backend compatibility.

---

## 1. Overview & Core Concept

- **What It Does**: Enhances the system prompts in `backend/prompts.py` so LLMs understand their physical anatomy and critical head/neck vulnerabilities during practice and fight rounds.
- **Target Audience**: AI models generating 20-word thinking streams and motor commands for the biped simulation engine.
- **Key Value**: Eliminates leg/knee command hallucinations and prevents accidental self-inflicted head/neck damage against the ground or during arm swings.

---

## 2. Updated Prompt Specification

In `backend/prompts.py`, `_OFFICIAL_BODY_STRUCTURE` will be updated to append the explicit anatomy and head safety notices while preserving the exact ASCII tree:

```
OFFICIAL BODY STRUCTURE:
FIGHTER
└── CHEST (central ball, origin for all relative measurements)
    └── NECK (connecting link, not a ball)
        ├── HEAD (physical ball)
        ├── RIGHT_ARM
        │   ├── NECK_RIGHT_JOINT (connection force to chest/neck)
        │   └── RIGHT_SHOULDER (physical ball)
        │       └── SHOULDER_RIGHT_JOINT (connection force to shoulder)
        │           └── RIGHT_ELBOW (physical ball)
        │               └── ELBOW_RIGHT_JOINT (connection force to elbow)
        │                   └── RIGHT_FIST (physical ball)
        └── LEFT_ARM
            ├── NECK_LEFT_JOINT (connection force to chest/neck)
            └── LEFT_SHOULDER (physical ball)
                └── SHOULDER_LEFT_JOINT (connection force to shoulder)
                    └── LEFT_ELBOW (physical ball)
                        └── ELBOW_LEFT_JOINT (connection force to elbow)
                            └── LEFT_FIST (physical ball)

CRITICAL ANATOMY NOTICE:
- You are an upper-body bipedal torso only.
- You have NO LEGS, NO KNEES, NO HIPS, NO ANKLES, and NO FEET.
- Never attempt to issue commands, descriptions, or references to legs or knees.

CRITICAL HEAD & NECK PROTECTION DIRECTIVE:
- Protect your HEAD and NECK at all times. Head or neck destruction causes INSTANT DEFEAT.
- DO NOT damage your own head or neck when executing movements, punches, or rotation routines.
- DO NOT slam or drag your head into the ground or arena wall when crawling or shifting your chest.
- Keep shoulders and elbows positioned to shield your neck and head from ground impact and opponent strikes.
```

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: Direct Integration into `_OFFICIAL_BODY_STRUCTURE`**
  - *Chosen Approach*: Keep the exact ASCII tree structure unchanged and append both critical notices directly under it in `_OFFICIAL_BODY_STRUCTURE`.
  - *Why*: Ensures every prompt function (`practice_system` and `fight_system`) receives both the anatomical constraints and safety directives consistently.

---

## 4. Technical Architecture & Verification

```
┌─────────────────────────────────────────────────────────────┐
│                    backend/prompts.py                       │
├─────────────────────────────────────────────────────────────┤
│  _OFFICIAL_BODY_STRUCTURE                                   │
│  ├── ASCII Body Tree (CHEST, HEAD, ARMS) [UNTOUCHED]        │
│  ├── CRITICAL ANATOMY NOTICE (NO LEGS/KNEES) [ADDED]        │
│  └── HEAD & NECK PROTECTION DIRECTIVE [ADDED]              │
└──────────────────────────────┬──────────────────────────────┘
                               │ Imports
┌──────────────────────────────▼──────────────────────────────┐
│  practice_system() & fight_system() Prompt Generators       │
└──────────────────────────────┬──────────────────────────────┘
                               │ Execution
┌──────────────────────────────▼──────────────────────────────┐
│  python3 backend/test_official_spec.py (Backend Tests Pass) │
└─────────────────────────────────────────────────────────────┘
```

### Implementation & Verification Steps

1. Update `backend/prompts.py` to append both notices to `_OFFICIAL_BODY_STRUCTURE`.
2. Run `python3 backend/test_official_spec.py` and `python3 backend/test_all.py` to verify prompt generation and zero test regressions.
3. Run `compile_applet` to verify clean build state.
