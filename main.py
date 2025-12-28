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
PROGRESSION_RPE_TRIGGER = 9

# Exercise Customizations
EXERCISE_CONFIG = {
    # Heavy Compounds
    "Deadlift": {"inc": 10, "goal_reps": 8},
    "Squat":    {"inc": 5,  "goal_reps": 10},
    "Leg Press":{"inc": 10, "goal_reps": 12},
    # Medium Compounds
    "Bench Press":    {"inc": 5, "goal_reps": 12},
    "Overhead Press": {"inc": 2.5, "goal_reps": 12},
    "Row":            {"inc": 5, "goal_reps": 12},
    # Isolation
    "Lateral Raise":  {"inc": 0, "goal_reps": 15}, # Force high reps
    "Curl":           {"inc": 2.5, "goal_reps": 12},
    "Extension":      {"inc": 2.5, "goal_reps": 12},
    "Fly":            {"inc": 2.5, "goal_reps": 15},
    "Calf":           {"inc": 5, "goal_reps": 15},
}

def get_config(exercise_title):
    for key, config in EXERCISE_CONFIG.items():
        if key.lower() in exercise_title.lower():
            return config
    return {"inc": 5, "goal_reps": 12} # Default

def get_recent_workouts():
    """Fetches the last 30 workouts to find your active routines."""
    headers = {'api-key': HEVY_API_KEY, 'accept': 'application/json'}
    try:
        response = requests.get(f"{HEVY_API_URL}/workouts", headers=headers, params={'page': 1, 'pageSize': 30})
        response.raise_for_status()
        return response.json().get('workouts', [])
    except Exception as e:
        print(f"Error fetching Hevy data: {e}")
        return []

def group_by_routine(workouts):
    """Groups workouts by their title (Routine Name) and keeps only the latest one."""
    routines = {}
    for w in workouts:
        title = w.get('title', 'Unknown Workout')
        # Only keep the most recent occurrence of each routine title
        if title not in routines:
            routines[title] = w
    return routines

def calculate_next_target(exercise_name, sets):
    if not sets: return None

    last_set = sets[-1]
    reps = last_set.get('reps', 0)
    weight_kg = last_set.get('weight_kg', 0)
    if weight_kg is None: weight_kg = 0
    weight_lbs = round(weight_kg * 2.20462, 1)

    rpe = last_set.get('rpe')
    if rpe is None: rpe = 8.0

    config = get_config(exercise_name)
    goal_reps = config['goal_reps']
    increment = config['inc']

    recommendation = {}
    
    # 1. PASSED
    if reps >= goal_reps and rpe <= PROGRESSION_RPE_TRIGGER:
        if increment == 0:
             recommendation = {
                "action": "MASTERED",
                "detail": f"You hit {reps} reps! Consider moving up a dumbbell size or aim for {reps+2} reps.",
                "color": "green"
            }
        else:
            new_weight = weight_lbs + increment
            recommendation = {
                "action": "INCREASE WEIGHT",
                "detail": f"Add {increment} lbs. New Target: {int(new_weight)} lbs.",
                "color": "green"
            }
    # 2. BUILDING
    elif reps < goal_reps and rpe < 9:
        recommendation = {
            "action": "ADD REPS",
            "detail": f"Keep weight ({int(weight_lbs)} lbs). Push for {min(reps + 2, goal_reps)} reps.",
            "color": "blue"
        }
    # 3. STRUGGLING
    elif reps < (goal_reps - 4) and rpe >= 9.5:
        new_weight = weight_lbs * 0.90
        recommendation = {
            "action": "DELOAD",
            "detail": f"Performance dip. Drop to {int(new_weight)} lbs to rebuild volume.",
            "color": "red"
        }
    # 4. GRINDING
    else:
        recommendation = {
            "action": "MAINTAIN",
            "detail": f"Keep weight ({int(weight_lbs)} lbs). Squeeze out 1 more rep.",
            "color": "black"
        }

    return {"exercise": exercise_name, "last": f"{reps} reps @ {int(weight_lbs)} lbs (RPE {rpe})", **recommendation}

def send_email(html_body, text_body):
    msg = MIMEMultipart("alternative")
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = "🏋️ Next Workout Menu (All Routines)"

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

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

    print("Fetching workout history...")
    workouts = get_recent_workouts()
    latest_routines = group_by_routine(workouts)
    
    if not latest_routines:
        print("No workouts found.")
        exit()

    print(f"Found {len(latest_routines)} active routines: {list(latest_routines.keys())}")

    html_content = """
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">📋 Your Workout Menu</h2>
        <p>Targets calculated for your next session of each routine.</p>
    """
    text_content = "YOUR WORKOUT MENU\nTargets calculated for next session:\n\n"

    # Iterate through every unique routine found
    for title, data in latest_routines.items():
        
        # Header for the Routine
        html_content += f"""
        <div style="background-color: #f4f4f4; padding: 10px; margin-top: 20px; border-radius: 5px;">
            <h3 style="margin: 0; color: #222;">{title}</h3>
            <span style="font-size: 12px; color: #666;">Last performed: {datetime.fromisoformat(data['start_time'].replace('Z', '+00:00')).strftime('%b %d')}</span>
        </div>
        <ul style="list-style-type: none; padding: 0;">
        """
        text_content += f"=== {title} ===\n"

        # Calculate targets for this routine
        for ex in data.get('exercises', []):
            res = calculate_next_target(ex.get('title'), ex.get('sets', []))
            if res:
                html_content += f"""
                <li style="padding: 10px 0; border-bottom: 1px solid #eee;">
                    <strong>{res['exercise']}</strong><br>
                    <span style="color:#666; font-size:13px;">Last: {res['last']}</span><br>
                    <strong style="color:{res['color']}; font-size:14px;">👉 {res['action']}</strong>: {res['detail']}
                </li>
                """
                text_content += f"[{res['exercise']}] {res['action']}: {res['detail']}\n"
        
        html_content += "</ul>"
        text_content += "\n"

    html_content += "</div>"

    # Send the Master Email
    send_email(html_content, text_content)
