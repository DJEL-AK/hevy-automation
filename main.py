# ==============================================================================
# 1. IMPORTATIONS / LIBRARIES
# ==============================================================================
import os
import requests
import resend
from datetime import datetime, timedelta, timezone

# ==============================================================================
# 2. CONFIGURATION & SÉCURITÉ
# ==============================================================================
# Récupération des secrets depuis GitHub
HEVY_API_KEY = os.environ.get("HEVY_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

# URL de base de l'API Hevy
HEVY_API_URL = 'https://api.hevyapp.com/v1'

# Initialisation du client Resend
resend.api_key = RESEND_API_KEY

# ==============================================================================
# 3. PARAMÈTRES DE PROGRESSION (EN KG)
# ==============================================================================
GOAL_REPS = 12                  # Objectif de répétitions
PROGRESSION_RPE_TRIGGER = 9     # Seuil RPE pour augmenter la charge

# Poids à ajouter en KG quand l'objectif est atteint
# 2.5 kg correspond aux petits disques de 1.25 de chaque côté
WEIGHT_INCREMENT_KG = 2.5       

# ==============================================================================
# 4. FONCTION : RÉCUPÉRER L'HISTORIQUE (FETCH DATA)
# ==============================================================================
def get_weekly_workouts():
    """Récupère les entraînements des 7 derniers jours via l'API Hevy."""
    headers = {'api-key': HEVY_API_KEY, 'accept': 'application/json'}
    all_workouts = []
    
    # Date limite : il y a 7 jours
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
    print(f"Filtering for workouts after: {cutoff_date.strftime('%Y-%m-%d')}")

    # On parcourt jusqu'à 3 pages d'historique pour être sûr de tout avoir
    for page_num in range(1, 4):
        try:
            params = {'page': page_num, 'pageSize': 10}
            response = requests.get(f"{HEVY_API_URL}/workouts", headers=headers, params=params)
            
            if response.status_code != 200: break
            data = response.json()
            workouts = data.get('workouts', [])
            if not workouts: break
            
            for w in workouts:
                # Gestion du format de date (ISO 8601)
                w_date_str = w.get('start_time', '')
                if w_date_str.endswith('Z'):
                    w_date_str = w_date_str.replace('Z', '+00:00')
                try:
                    w_date = datetime.fromisoformat(w_date_str)
                except ValueError:
                    continue 

                # Si l'entraînement est récent, on l'ajoute
                if w_date >= cutoff_date:
                    all_workouts.append(w)
                else:
                    return all_workouts
        except Exception as e:
            print(f"Error fetching page {page_num}: {e}")
            break     
    return all_workouts

# ==============================================================================
# 5. FONCTION : GROUPER PAR ROUTINE
# ==============================================================================
def group_by_routine(workouts):
    """Ne garde que la dernière session de chaque routine (ex: Push A)."""
    routines = {}
    for w in workouts:
        title = w.get('title', 'Unknown Workout')
        # On écrase les anciennes versions pour ne garder que la plus récente
        if title not in routines:
            routines[title] = w
    return routines

# ==============================================================================
# 6. FONCTION : CALCULER LA PROCHAINE CIBLE (LOGIQUE COEUR)
# ==============================================================================
def calculate_next_target(exercise_name, sets):
    """Analyse les séries et détermine : Augmenter, Maintenir ou Deload."""
    if not sets: return None

    # --- ÉTAPE A : TROUVER LA MEILLEURE SÉRIE ---
    # On cherche la série avec le poids le plus élevé (max weight)
    working_set = max(sets, key=lambda s: s.get('weight_kg') or 0)
    
    reps = working_set.get('reps') or 0
    weight_kg = working_set.get('weight_kg') or 0
    
    # On garde le poids brut en KG
    current_weight = round(weight_kg, 2)

    # Logique d'affichage propre (ex: 20 kg au lieu de 20.0 kg)
    if current_weight % 1 == 0:
        display_weight = int(current_weight)
    else:
        display_weight = current_weight

    rpe = working_set.get('rpe')
    if rpe is None: rpe = 8.0 # Valeur par défaut si RPE manquant

    recommendation = {}
    if reps == 0: return None

    # --- ÉTAPE B : ARBRE DE DÉCISION (ALGORITHME) ---
    
    # CAS 1 : SUCCÈS (Objectif atteint, RPE correct) -> Augmenter Poids
    if reps >= GOAL_REPS and rpe <= PROGRESSION_RPE_TRIGGER:
        new_weight = current_weight + WEIGHT_INCREMENT_KG
        
        # Formatage du nouveau poids cible
        if new_weight % 1 == 0:
            disp_new = int(new_weight)
        else:
            disp_new = new_weight

        recommendation = {
            "action": "INCREASE WEIGHT",
            "detail": f"Add {WEIGHT_INCREMENT_KG} kg",
            "target_display": f"Target: {disp_new} kg",
            "badge_color": "#d4edda", # Vert
            "text_color": "#155724"   
        }
    
    # CAS 2 : CONSTRUCTION (Reps manquantes mais RPE facile) -> Ajouter Reps
    elif reps < GOAL_REPS and rpe < 9:
        recommendation = {
            "action": "ADD REPS",
            "detail": f"Keep {display_weight} kg",
            "target_display": f"Target: {min(reps + 2, GOAL_REPS)} reps",
            "badge_color": "#cce5ff", # Bleu
            "text_color": "#004085"   
        }
    
    # CAS 3 : DIFFICULTÉ (Échec ou trop dur) -> Deload (-10%)
    elif reps < (GOAL_REPS - 4) and rpe >= 9.5:
        new_weight = round(current_weight * 0.90, 2)
        
        if new_weight % 1 == 0:
            disp_new = int(new_weight)
        else:
            disp_new = new_weight

        recommendation = {
            "action": "DELOAD",
            "detail": "Performance Dip",
            "target_display": f"Reset to: {disp_new} kg",
            "badge_color": "#f8d7da", # Rouge
            "text_color": "#721c24"   
        }
    
    # CAS 4 : MAINTIEN (Cas par défaut)
    else:
        recommendation = {
            "action": "MAINTAIN",
            "detail": f"Keep {display_weight} kg",
            "target_display": "Squeeze 1 more rep",
            "badge_color": "#e2e3e5", # Gris
            "text_color": "#383d41"   
        }

    return {"exercise": exercise_name, "last": f"{reps} @ {display_weight} kg (RPE {rpe})", **recommendation}

# ==============================================================================
# 7. FONCTION : ENVOI DE L'EMAIL (VIA RESEND)
# ==============================================================================
def send_email_resend(html_body, text_body, start_date, end_date):
    print("Sending email via Resend...")
    
    try:
        # Configuration de l'email
        params = {
            "from": "onboarding@resend.dev", # Adresse obligatoire pour le mode gratuit
            "to": [EMAIL_RECEIVER],          # Ton email (doit être le même que ton compte Resend)
            "subject": f"Weekly Training Plan ({start_date} - {end_date})",
            "html": html_body,
            "text": text_body,
        }

        email = resend.Emails.send(params)
        print("Email sent successfully!")
        print(email)
    except Exception as e:
        print(f"Failed to send email: {e}")

# ==============================================================================
# 8. EXÉCUTION PRINCIPALE (MAIN)
# ==============================================================================
if __name__ == "__main__":
    # Vérification de la présence des clés API
    if not HEVY_API_KEY:
        print("Error: HEVY_API_KEY is missing.")
        exit()
    if not RESEND_API_KEY:
        print("Error: RESEND_API_KEY is missing.")
        exit()

    print("Fetching last 7 days of workouts...")
    workouts = get_weekly_workouts()
    latest_routines = group_by_routine(workouts)
    
    if not latest_routines:
        print("No workouts found in the last 7 days.")
        exit()

    print(f"Found {len(latest_routines)} routines from this week.")

    # Préparation des dates pour le titre de l'email
    end_date = datetime.now().strftime('%b %d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%b %d')

    # --- GÉNÉRATION DU HEADER HTML ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; padding:0; background-color:#f6f9fc; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#f6f9fc; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                        <tr>
                            <td style="background-color:#212529; padding: 30px 40px; text-align:center;">
                                <h1 style="margin:0; color:#ffffff; font-size:24px; font-weight:700;">Next Week's Targets</h1>
                                <p style="margin:10px 0 0 0; color:#adb5bd; font-size:14px;">Review of {start_date} - {end_date}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px;">
    """
    
    text_content = f"WEEKLY TRAINING PLAN ({start_date} - {end_date})\n\n"

    # Boucle sur chaque Routine (ex: Push, Pull...)
    for title, data in latest_routines.items():
        raw_date = data['start_time'].replace('Z', '+00:00')
        display_date = datetime.fromisoformat(raw_date).strftime('%A')

        # Ajout du titre de la routine dans le HTML
        html_content += f"""
        <div style="margin-bottom: 30px;">
            <div style="border-bottom: 2px solid #eee; padding-bottom: 10px; margin-bottom: 15px;">
                <h2 style="margin:0; color:#333; font-size:18px;">{title}</h2>
                <span style="font-size:12px; color:#888; text-transform:uppercase; letter-spacing:1px; font-weight:bold;">Last Session: {display_date}</span>
            </div>
        """
        text_content += f"=== {title} ({display_date}) ===\n"

        # Boucle sur chaque Exercice de la routine
        for ex in data.get('exercises', []):
            res = calculate_next_target(ex.get('title'), ex.get('sets', []))
            if res:
                # Définition du style CSS pour le badge de recommandation
                # (Divisé en plusieurs lignes pour éviter les erreurs de copier-coller)
                badge_style = (
                    f"background-color:{res['badge_color']}; "
                    f"color:{res['text_color']}; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; "
                    "font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;"
                )
                
                # Création du bloc HTML pour l'exercice
                html_content += f"""
                <div style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                    <table width="100%" border="0">
                        <tr>
                            <td width="60%" valign="top">
                                <strong style="color:#222; font-size:15px; display:block; margin-bottom:4px;">{res['exercise']}</strong>
                                <span style="color:#999; font-size:13px;">Top Set: {res['last']}</span>
                            </td>
                            <td width="40%" align="right" valign="top">
                                <span style="{badge_style}">{res['action']}</span>
                                <div style="margin-top:5px; font-size:13px; color:#444; font-weight:600;">{res['target_display']}</div>
                            </td>
                        </tr>
                    </table>
                </div>
                """
                text_content += f"[{res['exercise']}] {res['action']} -> {res['target_display']}\n"
        
        html_content += "</div>"
        text_content += "\n"

    # --- PIED DE PAGE HTML (FOOTER) ---
    html_content += """
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color:#f8f9fa; padding: 20px; text-align:center; border-top: 1px solid #eee;">
                                <p style="margin:0; color:#999; font-size:12px;">Generated by Hevy Automation Script</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Envoi final
    send_email_resend(html_content, text_content, start_date, end_date)
