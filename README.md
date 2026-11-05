# AI Physical Engine
https://clock-board-ui.onrender.com
render slow 30s start

## Give AI a body. Let physics decide.

**An AI-controlled physical simulation engine that turns model decisions into movement, collisions, and measurable outcomes.**

Most AI demos stop when a model returns text. This project keeps going.

An AI receives a description of a physical body and its situation. It chooses motor rotations. The Python physics engine applies those motor commands and calculates what happens under gravity, contact, friction, collisions, and damage. The result becomes the AI's next observation.

**The AI chooses. Physics decides. Every result can be inspected.**

This project explores two applications of the same technology:

1. **AI robotics physical testing** — a virtual place to explore and evaluate AI body-control decisions before moving toward real hardware.
2. **A new kind of gaming engine** — physics-driven characters whose actions are chosen by AI rather than played from fixed animation scripts.

---

## 1. AI robotics physical testing

### Give AI a body before giving it a machine

Robots must do more than choose an action. Their movements must work under physical limits. A command can fail, lose balance, hit something, or produce an unexpected result.

This project explores a test loop for those problems:

- Give an AI a body and a set of motor controls.
- Let it choose motor rotations from the current situation.
- Let physics calculate what actually happens.
- Show the AI the new situation so it can make its next decision.
- Save and replay runs to compare different approaches.

This is a starting point for testing AI control strategies in a repeatable virtual environment. The longer-term direction is to support different robot body designs, control systems, and test scenarios before moving toward real machines.

**Current scope:** the supplied prototype is a virtual stick-fighter simulation. It does not yet connect to or control a physical robot, ROS, or a hardware test rig. Results are not yet validated against real machines. Moving toward real-world robotics will require robot-specific body models, calibrated physical properties, hardware integration, and separate safety testing.

## 2. A new kind of gaming engine

### Characters that act through physics, not prewritten animations

Many games use animation clips or prewritten actions to control character movement. This project explores a different approach: an AI chooses motor rotations, and the physics engine determines how the character actually moves.

This creates room for:

- AI-controlled characters that choose their own actions.
- Practice sessions for one AI-controlled character.
- Fights between two independent AI controllers.
- Movement routines that can be saved and reused.
- Physical outcomes such as falls, impacts, contact, and damage.
- Saved rounds that can be replayed and studied.

The current demonstration is a fighting simulation. The broader opportunity is a game engine where character behavior emerges from the combination of AI decisions and physical rules.

### Zero animation scripts drive character movement

**There are no character-animation scripts driving movement: no animation clips, no keyframed poses, and no prewritten motion sequences.** The AI controls motor rotations only. It does not choose the body's next position or tell the engine where a body part should appear.

The physics engine calculates the resulting movement, balance, contact, collisions, and damage. The 3D viewer displays the resulting physical states; it does not replace the physics with an animation.

```text
Animation-driven character:  animation script -> preset pose / motion
This project:               AI -> motor rotations -> physics -> calculated movement
```

The AI's motor commands are subject to the simulation's existing motor and force rules. A command does not guarantee a movement; the physical result depends on the simulated world.

---

## How the engine works

```text
             PHYSICAL WORLD
                   |
                   v
          AI-readable observation
                   |
                   v
               META AI
          chooses motor rotations
                   |
                   v
           Python control layer
          reads and applies commands
                   |
                   v
             PHYSICS ENGINE
       gravity | forces | contact
       collisions | friction | damage
                   |
                   v
           UPDATED BODY STATE
                   |
                   +-----------> back to the AI

            Saved round / replay
```

The live simulation advances at **7 physics frames per second** on the current hosted demo. AI decisions happen at their configured decision intervals; physics continues advancing between AI calls. Replay reconstruction and replay viewing use a **30 FPS** frame timeline.

The AI does not directly write body-part positions. It sends motor-rotation instructions. The physics engine calculates the resulting positions and movement.

## AI-friendly 3D spatial language

The project uses a compact word-based position description to help an AI understand where body parts are without receiving a large dump of raw coordinate numbers.

The position translator calculates each ball's location relative to the fighter's chest center, then turns the calculated direction into words:

- **24 horizontal direction values** around a full 360° circle, in 15° steps.
- **13 vertical direction values** from straight down to straight up, in 15° steps.
- **5 distance words:** `VERY-CLOSE`, `CLOSE`, `MID`, `FAR`, and `VERY-FAR`.

That is **37 directional values plus 5 distance words**. Combining one horizontal direction, one vertical direction, and one distance band creates **1,560 possible spatial descriptions** (`24 × 13 × 5`).

Example:

```text
FIST: FAR FRONT DIAGONAL RIGHT SLIGHT UPPER
HEAD: MID BACK LEVEL
ELBOW: CLOSE RIGHT LOWER
```

When a physical ball is touching the floor, the special word `GROUND` can replace its distance word.

The intent is to give the AI understandable natural-language descriptions rather than bloated numerical position data. The physics engine still performs all calculations using numerical coordinates; the word system is the AI-facing description layer. Motor commands remain rotation-only and use the project's 15° rotation steps.

---

## Materials, mass, and forces

**Materials are part of the physical model, not just visual appearance.** Each ball and connection is assigned a material. Material properties affect mass, friction, bounce, and how parts respond to impacts.

The current prototype uses two materials:

| Property | Iron | Wood |
|---|---:|---:|
| Material density used by the model | 7,000 kg/m³ | 600 kg/m³ |
| Friction coefficient | 0.50 | 0.40 |
| Bounce coefficient | 0.50 | 0.40 |
| Damage behavior | Iron parts do not break | Wooden parts and links can be damaged and destroyed |

### How mass and weight are handled

- Each physical ball has a defined mass in the body model.
- Wooden connections also add mass. Their mass is calculated from density and their cylindrical dimensions: `density × π × radius² × length`.
- The mass of each wooden connection is shared between its two connected end balls.
- Gravity acts on the resulting masses at **9.81 m/s²**.

### How forces and impacts affect the body

The physics loop applies gravity and air drag, drives motors within their existing force limits, maintains connections between body parts, and resolves contact using bounce and friction. It does not teleport parts into requested positions.

Impact damage is based on the energy absorbed during a collision, measured in joules. In the current rules, an iron-on-wood impact uses a **1.5× damage multiplier**; wood-on-wood damage uses **0.5×**. Iron parts are not destroyed by the current damage rules, while wooden parts and links can break when their damage limit is reached.

Material assignments are defined in the backend body model. The current demo demonstrates material-based physical behavior; it does not yet include a separate in-app material editor.

---

## What makes the physics workload meaningful

A simulation frame is more than a simple position update. In the supplied physics implementation, each frame is divided into **8 internal substeps**, and each substep runs **8 connection/contact solver passes**. That is **64 solver passes per frame**, in addition to motor-force calculations, gravity, drag, contact detection, collision response, and damage checks.

At 7 live frames per second, the engine is still calculating these physical interactions for every processed frame. This is a deliberately resource-conscious way to run the hosted demonstration on a small free backend. The hosted service, rather than the visual viewer, is the main performance constraint.

---

## Meta models and API integration

Meta models are central to the project's AI control loop. The engine retains direct Meta provider configurations, and the working hosted demonstration currently uses a Meta model through Baseten.

### Direct Meta API integration issue

I first tried sending requests directly to the Meta AI API for **Muse Spark 1.3** and **Muse Spark 1.3 Contributor**. Those requests returned a **`model not found`** error. I raised the issue with the CV team, and they told me it was an unresolved problem at that time.

To keep development moving and demonstrate the complete AI-to-physics loop, I used **`meta-models/muse-spark-open-1026` through Baseten** for the working demo.

I have **kept the direct Meta provider configurations in the engine** rather than removing them. This documents that direct Meta API integration was attempted and allows it to be retried when the model-availability issue is resolved.

| Integration route | Status in this project |
|---|---|
| Direct Meta API — Muse Spark 1.3 and Muse Spark 1.3 Contributor | Attempted; requests returned `model not found`. The CV team said the issue was unresolved. Configurations remain in the engine. |
| Baseten — `meta-models/muse-spark-open-1026` | Used for the working hosted demo. |

The responsibilities are separate:

- **AI model:** reads the current situation and chooses actions.
- **Python engine:** applies motor commands and calculates the physical result.
- **Replay system:** reconstructs the round for inspection.

The model makes decisions; the physics engine remains responsible for the simulated physical world.

---

## How to use the judge demo

The hosted demo is intended for the hackathon judges and authorised reviewers. **I will provide the admin token privately with the submission.** The token is required to launch new practice and fight simulations; it is not included in this public README or repository.

### 1. Open the demo

Open the frontend demo link included with the submission. The frontend is hosted separately from the Python backend. The backend must be awake for actions that need simulation processing or saved replay data.

**First-visit note:** Render's free web service may spin down after 15 minutes without inbound traffic. If it has been idle, the first backend request can take about one minute while the service wakes up. This is normal free-tier behavior.

### 2. Enter the admin token

Find the **Admin token** field in the **New simulation** panel and enter the token supplied privately with the submission. The backend verifies the token when a new simulation is submitted. An incorrect token is rejected.

The token is not included in the source code or this README. Do not publish it in screenshots, public messages, or repository files. Without the token, reviewers can still inspect available saved runs and replays when the backend is online, but they cannot launch new simulations.

### 3. Run an AI practice session

1. Select **Practice**.
2. Choose **Fighter A** or **Fighter B** for the AI memory slot.
3. Select the provider configured for the working demo. Use **Baseten** for the hosted demo's working model route.
4. Set the **Think interval**. This controls how often the AI makes a new decision; physics continues between AI decisions.
5. Select **Start practice**.

Watch the job status while the backend runs the simulation. Once the run is saved, it becomes available in replay history.

### 4. Run an AI-versus-AI fight

1. Select **Fight**.
2. Choose the AI provider and reasoning effort separately for **Fighter A** and **Fighter B**.
3. Set the **Think interval**.
4. Select **Start fight**.

Both AI controllers make decisions from the same world snapshot. The backend applies their motor commands and advances the physics simulation.

### 5. Inspect the physical result

1. In **Saved replays**, select **Fights** or **Practice**.
2. Select a saved run.
3. Use **Play/Pause**, the timeline, and the 5-second back/forward controls to inspect the result.
4. Change replay speed to **0.25×, 0.5×, 1×, 1.5×, 2×, or 4×** to examine an event more closely.

The viewer displays the recorded physical simulation. It does not create character movement with animation scripts.

**Recommended judge walkthrough:** start with a practice session, run an AI-versus-AI fight, then open a replay and inspect how the AI's motor commands played out in the physics engine. The complete cycle is **observation → AI decision → motor rotation → physical result → replay**.

---

## Hosted demo: performance and infrastructure

The public demonstration is deployed as two separate Render services:

| Part | Render service | Role |
|---|---|---|
| Python backend | **Render Web Service — Free plan** | Runs AI requests, motor commands, physics, round processing, and replay reconstruction |
| React / Three.js frontend | **Render Static Site** | Serves the browser interface and 3D replay viewer |

The backend's current free-plan allocation is **0.1 CPU and 512 MB RAM**. The static frontend is served separately and does not consume the backend's web-service CPU allocation. See [Render compute plans](https://render.com/docs/compute-plans).

### Performance in this demo

| Stage | Current demo configuration |
|---|---:|
| Live round processing | Approximately **7 physics frames per second** on the hosted service |
| Replay reconstruction frame timeline | **30 FPS** |
| Replay viewer playback/rendering | **30 FPS** |
| Internal physics work | **8 substeps × 8 solver passes = 64 solver passes per frame** |

The live pace reflects the available compute budget and the work required for each physics frame, alongside external AI model requests. The engine has been optimized for the resources available, but a free-tier service is not intended to provide the same throughput as a dedicated compute instance.

### Why this demo uses lightweight 3D visuals

The submission prioritizes the AI control loop, physical interactions, saved rounds, and replay inspection. To keep the hosted demo within its resource budget, it uses lightweight 3D balls and connecting shapes rather than detailed full 3D character and environment models.

Continuous high-detail live 3D scene streaming and AI camera-based visual perception are not included in this demo. They are potential next-stage extensions that would require additional compute capacity and a dedicated vision pipeline. This is a conscious scope and hosting choice for an early-stage demonstration—not a limit on the broader direction of the technology.

### Render free-service cold starts

Render automatically spins down a free web service after **15 minutes without inbound traffic**. The next request wakes the Python backend, and startup can take **about one minute**. The frontend static site can still load while the backend is waking; actions that need the backend may take longer on the first request.

This is normal Render free-tier behavior, not a physics-engine error. For the judge demo, allow the backend a short moment to wake up if it has been idle. See [Render's free-service documentation](https://render.com/docs/free) and [Render's FAQ](https://render.com/docs/faq).

---

## Current capabilities and next steps

The supplied prototype demonstrates:

- A Python-based physical simulation.
- Gravity, body connections, motor control, friction, and collision handling.
- Contact with the ground, arena walls, and other body parts.
- Material-based mass and impact-damage rules.
- **Practice mode:** one AI-controlled body.
- **Fight mode:** two AI controllers making independent decisions from the same world snapshot.
- A command format for defining and reusing named moves and move chains.
- Saved practice and fight runs.
- Replay reconstruction from saved actions and simulation setup.
- A React, TypeScript, and Three.js viewer for inspecting saved replays in 3D.
- SQLite for local storage, with a PostgreSQL connection path available.

This is an experimental prototype, not yet a general-purpose robotics simulator or a finished commercial game engine. The current body and arena are specialised for the stick-fighter experiment.

The next development steps are to support configurable body designs, robot-specific models and calibration, repeatable comparisons against real measurements, and a broader game-development toolkit. These are future goals, not features claimed to be complete today.

---

## Project layout

After extracting the supplied archives, the files can be arranged like this:

```text
project/
├── backend/                 Python simulation and API
│   ├── server.py
│   ├── sim.py
│   ├── physics.py
│   ├── body.py
│   ├── observe.py
│   ├── moves.py
│   └── ...
│
└── fighter-frontend/        React, TypeScript, and Three.js viewer
    ├── src/
    ├── package.json
    ├── index.html
    └── ...
```

The backend and frontend run as separate applications. The frontend connects to the backend through its HTTP API.

---

## Run locally

The backend and frontend run as separate applications.

### 1. Start the Python backend

Extract `backend.zip` into a folder named `backend`:

```bash
cd backend
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Set the required environment variables. For the direct Meta provider:

```bash
# macOS / Linux
export ADMIN_TOKEN="your-private-token"
export MODEL_API_KEY="your-meta-api-key"
```

```powershell
# Windows PowerShell
$env:ADMIN_TOKEN="your-private-token"
$env:MODEL_API_KEY="your-meta-api-key"
```

For the Baseten provider, also set `BASETEN_API_KEY`. Only the key for the provider you select is needed. `DATABASE_URL` is optional; without it, the backend uses local SQLite storage.

Start the backend:

```bash
python server.py
```

The backend listens on port `8000` by default.

### 2. Start the 3D viewer

Extract `fighter-frontend.zip`, then open a terminal in the `fighter-frontend` folder:

```bash
cp .env.example .env
```

On Windows, copy `.env.example` to `.env` using File Explorer or PowerShell. Set `VITE_API_BASE_URL` in `.env` to the URL of the Python backend.

Install dependencies and start the development server:

```bash
npm install
npm run dev
```

Open the local URL printed by Vite.

### 3. Build the frontend

```bash
npm run typecheck
npm run build
```

The production site files are created in `dist/`.

---

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check backend status |
| `POST` | `/practice` | Start a practice run |
| `POST` | `/fight` | Start a two-AI fight |
| `GET` | `/jobs/{id}` | Check a running job |
| `GET` | `/runs/practice` | List practice runs |
| `GET` | `/runs/fight` | List fight runs |
| `GET` | `/replay/{kind}/{n}` | Request a saved replay |
| `GET` | `/memory/{slot}` | Read the saved move library for fighter slot A or B |

Starting practice or fight runs requires the `X-Token` header with the backend's `ADMIN_TOKEN` value.

---

## Security

- Keep `ADMIN_TOKEN`, `MODEL_API_KEY`, and `BASETEN_API_KEY` on the backend only.
- Never put provider keys or the admin token in frontend variables or commit them to the project.
- The current token check is for trusted operator access. It is not a complete public user-account system.
- A public multi-user release would need proper authentication, access control, and deployment security.

---

## Why this fits the Meta Global AI Developer Hackathon

The project's primary direction is AI applied to physical systems: a model observes a body, chooses motor rotations, and receives the result calculated by a physics engine. This connects to the **Push the Frontier** ambition of exploring new AI applications, including robotics and physical-system control. Its second direction explores what the same technology could make possible in interactive entertainment.

The project is designed to demonstrate more than a concept: an AI-to-motor-to-physics loop, two-controller simulation, material-based physical interactions, saved runs, and replay inspection. Those concrete pieces make the technical idea observable and testable.

[Meta Global AI Developer Hackathon](https://dev.meta.ai/events/global-hackathon)

---

## The vision

**Today:** AI-controlled bodies in a physics-based fighting simulation.

**Next:** a configurable environment for testing AI movement and control strategies.

**Long term:** one physical engine that can support both intelligent machines and intelligent game characters.

**Give AI a body. Let physics decide what it can really do.**
