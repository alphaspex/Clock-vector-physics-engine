# Implementation Plan - Restrict Practice & Fight Launchers to Baseten Provider

## Summary
To streamline simulation launching, we will remove Meta model selection choices (`meta_contrib`, `meta`) from the Practice and Fight mode launcher UI, restricting all new simulation launches to **Baseten** (`baseten`).
API diagnostic test calls (`check-api`) for Meta models will remain active in the **Live Control Room** diagnostic console so operators can still verify Meta endpoint connectivity.

---

## Target Changes

### 1. Launcher Panel Component (`/fighter-frontend/src/features/launcher/LauncherPanel.tsx`)
- **Remove Meta Provider Selection**:
  - Update `practicePreset`, `presetA`, and `presetB` state defaults to `'baseten'`.
  - Simplify `ProviderModelSelector` to display Baseten as the exclusive fixed provider (`meta-models/muse-spark-open-1026`) for practice and fight launches.

### 2. Live Control Room Console (`/fighter-frontend/src/features/monitoring/ControlRoomPanel.tsx`)
- **Preserve Diagnostic Tests**:
  - Keep the full API diagnostics grid intact so Meta (`meta_contrib`, `meta`) and Baseten (`baseten`) models can be pinged (`checkApi`) and configured.

---

## Verification Plan
1. Verify launcher component renders Baseten exclusively for Practice & Fight launches.
2. Confirm Live Control Room still renders diagnostic test cards for Meta and Baseten.
3. Run `compile_applet` to confirm overall applet build state.

## Progress Tracking & Status Reporting
For all completed changes, we will explicitly detail:
1. What was done and working 100%.
2. What was done and might not work 100%.
3. What was not done.
