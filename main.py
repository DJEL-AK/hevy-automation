import os
import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
HEVY_API_KEY = os.environ.get("HEVY_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")
HEVY_API_URL = 'https://api.hevyapp.com/v1'

# Global Progression Settings
DEFAULT_GOAL_REPS = 12
DEFAULT_INCREMENT = 5
PROGRESSION_RPE_TRIGGER = 9

# ==========================================
# EXERCISE DATABASE (Optimization)
# ==========================================
# We map keywords to specific increment rules.
# If an exercise name contains the keyword, it uses that rule.
EXERCISE_CONFIG = {
    # TIER 1: HEAVY COMPOUNDS (Legs/Back) -> Larger Jumps
    "Deadlift": {"inc": 10, "goal_reps": 8},
    "Squat":    {"inc": 5,  "goal_reps": 10},
    "Leg Press":{"inc": 10, "goal_reps": 12},
    
    # TIER 2: MEDIUM COMPOUNDS (Push/Pull) -> Standard Jumps
    "Bench Press":    {"inc": 5, "goal_reps": 12},
    "Overhead Press": {"inc": 2.5, "goal_reps": 12}, # OHP is hard to progress!
    "Row":            {"inc": 5, "goal_reps": 12},
    "Pull Up":        {"inc": 2.5, "goal_reps": 10},
    "Dip":            {"inc": 2.5, "goal_reps": 10},

    # TIER 3: ISOLATION (Arms/Shoulders) -> Micro Jumps or High Reps
    "Lateral Raise":  {"inc": 0, "goal_reps": 15}, # Force 15 reps before jumping
    "Curl":           {"inc": 2.5, "goal_reps": 12},
    "Extension":      {"inc": 2.5, "goal_reps": 12},
    "Fly":            {"inc": 2.5, "goal_reps": 15},
    "Face Pull":      {"inc": 2.5, "goal_reps": 15},
    "Calf":           {"inc": 5, "goal_reps": 15},
}

def get_config(exercise_title):
    """Finds the config for an exercise based on name matching."""
    for key, config in EXERCISE_CONFIG.items():
        if key.lower() in exercise_title.lower():
            return config
    # Default fallback
    return {"inc": 5, "goal_reps": 12}

def get_latest_workout():
    headers = {'api-key': HEVY_API_KEY, 'accept': 'application/json'}
    try:
        # Fetch last 3 to find one with actual data
        response = requests.get(f"{HEVY_API_URL}/workouts", headers=headers, params={'page': 1, 'pageSize': 3})
        response.raise_for_status()
        workouts = response.json().get('workouts', [])
        
        for w in workouts:
            if w.get('exercises'):
                return w
        return None
    except Exception as e:
        print(f"Error fetching Hevy data: {e}")
        return None

def calculate_next_target(exercise_name, sets):
    if not sets: return None

    last_set = sets[-1]
    reps = last_set.get('reps', 0)
    weight_kg = last_set.get('weight_kg', 0)
    if weight_kg is None: weight_kg = 0
    
    # Convert to LBS
    weight_lbs = round(weight_kg * 2.20462, 1)

    # Handle RPE
    rpe = last_set.get('rpe')
    if rpe is None: rpe = 8.0

    # GET CUSTOM RULES
    config = get_config(exercise_name)
    goal_reps = config['goal_reps']
    increment = config['inc']

    recommendation = {}
    
    # --- LOGIC ENGINE ---
    
    # 1. PASSED: Hit the rep goal with good form
    if reps >= goal_reps and rpe <= PROGRESSION_RPE_TRIGGER:
        if increment == 0:
             # Special case for Lateral Raises etc: "Double Progression"
             # If increment is 0, it means we don't add weight, we just say "Great job, maybe try next dumbbell up?"
             # or we force a huge rep jump.
             recommendation = {
                "action": "MASTERED",
                "detail": f"You hit {reps} reps! Try the next dumbbell up if you feel ready, or aim for {reps+2} reps.",
                "color": "green"
            }
        else:
            new_weight = weight_lbs + increment
            recommendation = {
                "action": "INCREASE WEIGHT",
                "detail": f"Add {increment} lbs. New Target: {int(new_weight)} lbs.",
                "color": "green"
            }

    # 2. BUILDING: Under rep goal, but feeling good
    elif reps < goal_reps and rpe < 9:
        recommendation = {
            "action": "ADD REPS",
            "detail": f"Keep weight ({int(weight_lbs)} lbs). Push for {min(reps + 2, goal_reps)} reps.",
            "color": "blue"
        }

    # 3. STRUGGLING: Performance dipped significantly
    elif reps < (goal_reps - 4) and rpe >= 9.5:
        new_weight = weight_lbs * 0.90
        recommendation = {
            "action": "DELOAD",
            "detail": f"Performance dip. Drop to {int(new_weight)} lbs to rebuild volume.",
            "color": "red"
        }
    
    # 4. GRINDING: Close to limit
    else:
        recommendation = {
            "action": "MAINTAIN",
            "detail": f"Keep weight ({int(weight_lbs)} lbs). Squeeze out 1 more rep.",
            "color": "black"
        }

    return {"exercise": exercise_name, "last": f"{reps} reps @ {int(weight_lbs)} lbs (RPE {rpe})", **recommendation}

def send_email(html_content, text_content, workout_title):
    msg = MIMEMultipart("alternative")
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"💪 Next Workout Targets: {workout_title}"

    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    if not HEVY_API_KEY:
        print("Error: HEVY_API_KEY is missing.")
        exit()

    workout = get_latest_workout()
    
    if workout:
        print(f"Analyzing workout: {workout.get('title')}")
        html_list_items = ""
        text_list_items = ""
        
        for ex in workout.get('exercises', []):
            res = calculate_next_target(ex.get('title'), ex.get('sets', []))
            if res:
                html_list_items += f"""
                <li style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #eee;">
                    <strong style="font-size: 16px;">{res['exercise']}</strong><br>
                    <span style="color:#666; font-size:14px;">Last: {res['last']}</span><br>
                    <strong style="color:{res['color']}; font-size:14px;">👉 {res['action']}</strong>: {res['detail']}
                </li>
                """
                text_list_items += f"[{res['exercise']}]\nLast: {res['last']}\nACTION: {res['action']} - {res['detail']}\n\n"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">🚀 Smart Targets (Optimized)</h2>
            <p>Based on: <strong>{workout.get('title')}</strong></p>
            <hr>
            <ul style="list-style-type: none; padding: 0;">
                {html_list_items}
            </ul>
        </div>
        """
        text_content = f"SMART TARGETS\nBased on: {workout.get('title')}\n\n{text_list_items}"

        print("--- PREVIEW ---")
        print(text_content)
        
        send_email(html_content, text_content, workout.get('title'))
    else:
        print("No workout found.")
