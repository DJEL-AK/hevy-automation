
```markdown
# 🏋️ Hevy Progressive Overload Automator

A Python-based "Virtual Coach" that analyzes your [Hevy](https://hevy.com/
 workout history and emails you a weekly progressive overload plan.

**Stop guessing your weights.** This script looks at your last week of training,
finds your heaviest sets, and tells you exactly what to do next (Add Weight, Add Reps, or Deload).

---

## 🚀 Features

* **Weekly Workout Menu:** Scans your last 7 days of history and creates a plan for *every* active routine (Push, Pull, Legs, etc.).
* **Smart Analysis:** Ignores warmups and back-off sets. It automatically finds your **Heaviest Set** to calculate true progression.
* **Auto-Emailer:** Sends a beautiful, mobile-friendly HTML email every Sunday night (9:00 PM CST) via GitHub Actions.
* **Crash-Proof:** Handles missing RPE data, null reps, and bodyweight exercises without failing.

## 🧠 The Logic

The script uses a standardized **Linear Progression** model:
* **Goal:** 12 Reps @ RPE 10 (Failure).
* **Progression Trigger:** 12 Reps @ RPE 9 (1 Rep in Reserve).

| Condition | Logic | Recommendation |
| :--- | :--- | :--- |
| **Success** | `Reps ≥ 12` AND `RPE ≤ 9` | 🟢 **INCREASE WEIGHT** (+5 lbs) |
| **Building** | `Reps < 12` AND `RPE < 9` | 🔵 **ADD REPS** (Keep weight) |
| **Struggling** | `Reps < 8` AND `RPE ≥ 9.5` | 🔴 **DELOAD** (Drop 10% weight) |
| **Grinding** | Any other case | ⚫ **MAINTAIN** (Squeeze 1 more rep) |

---

## 🛠️ Setup Guide

### Prerequisites
1.  **Hevy Pro Subscription:** Required to access the [Hevy API](https://api.hevyapp.com/).
2.  **Gmail Account:** To send the emails (using an App Password).
3.  **GitHub Account:** To host and run the automation for free.

### Step 1: Get Your Keys
1.  **Hevy API Key:** Go to [Hevy Developer Settings](https://hevy.com/settings?developer) and generate a key.
2.  **Gmail App Password:**
    * Go to Google Account > Security > 2-Step Verification.
    * Scroll to the bottom and select **App Passwords**.
    * Create a new one named "HevyScript" and copy the 16-character code.

### Step 2: Configure GitHub
1.  **Fork** this repository to your own GitHub account.
2.  Go to **Settings** > **Secrets and variables** > **Actions**.
3.  Click **New repository secret** and add the following 4 secrets:

| Secret Name | Value |
| :--- | :--- |
| `HEVY_API_KEY` | Your Hevy API Key |
| `EMAIL_SENDER` | Your Gmail address (e.g., `you@gmail.com`) |
| `EMAIL_PASSWORD` | The 16-character App Password (NOT your login password) |
| `EMAIL_RECEIVER` | The email address where you want to receive the report |

### Step 3: Schedule
The script is pre-configured to run every **Sunday at 9:00 PM CST** (Monday 03:00 UTC).
To change this, edit the `.github/workflows/daily_run.yml` file:

```yaml
on:
  schedule:
    - cron: '0 3 * * 1' # Change this cron expression to your liking

```

---

## ⚙️ Customization

You can tweak the progression rules at the top of `main.py`:

```python
# Global Progression Settings
GOAL_REPS = 12                # The rep target you are aiming for
PROGRESSION_RPE_TRIGGER = 9   # The RPE limit to qualify for a weight jump
WEIGHT_INCREMENT_LBS = 5      # How much weight to add (e.g., 2.5 for micro-loading)

```

---

## ⚠️ Disclaimer

This is a personal DIY project and is not affiliated with or endorsed by Hevy. Use the API responsibly.

```

```
