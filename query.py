# query.py

"""
- gets all users in jamf via api
- write email, first, last, fullname, username to .json
"""

from datetime import date
import jamf_client
from jamf_client import jamf_get, jamf_session
import json
import os
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIMESTAMP_PATH = os.path.join(SCRIPT_DIR, "last_run.timestamp")
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "lookup.json")
RAW_PATH = os.path.join(SCRIPT_DIR, "raw.json")
CACHE_TTL = 604800

TESTING_MODE = False

# ============================================================================================================================================================

def run_check():
  try:
    with open(TIMESTAMP_PATH, "r") as f:
      last_epoch = int(f.read().strip())
  except (OSError, ValueError):
    return True
  if not os.path.isfile(LOOKUP_PATH):
    return True
  return int(time.time()) - last_epoch > CACHE_TTL

def get_grade(full):
  pos = full.get("position")
  email = full.get("email")
  if email and re.search(r"@rundle\.ab\.ca$", email, re.IGNORECASE):
    return "Staff"
  if not pos:
    return None
  match = re.search(r'EGY(\d{4})', pos, re.IGNORECASE)
  if match:
    egy = int(match.group(1))
    today = date.today()
    current_grad_year = today.year if today.month < 7 else today.year + 1
    grade = 12 - (egy - current_grad_year)
    if grade == 0:
      return "K"
    if 1 <= grade <= 12:
      return f"Grade {grade}"
    return "Alumni"
  match = re.search(r'Grade\s*0*(\d{1,2})', pos, re.IGNORECASE)
  if match:
    return f"Grade {match.group(1)}"
  return None

def build_location_map(token, session):
  location_map = {}

  response = jamf_get("/api/v1/buildings?page=0&page-size=100&sort=id%3Aasc", token, session)
  buildings_by_id = {b["id"]: b["name"] for b in response.json()["results"]}

  # computers-inventory: building only carries an id, resolve via the lookup above
  page = 0
  endpoint = f"/api/v3/computers-inventory?section=GENERAL&section=USER_AND_LOCATION&page={page}&page-size=1000&sort=id%3Aasc"
  response = jamf_get(endpoint, token, session)
  computers = []
  while True:
    data = response.json()
    computers.extend(data["results"])
    if len(computers) >= data["totalCount"]:
      break
    page += 1
    endpoint = f"/api/v3/computers-inventory?section=GENERAL&section=USER_AND_LOCATION&page={page}&page-size=1000&sort=id%3Aasc"
    response = jamf_get(endpoint, token, session)
  for c in computers:
    ual = c.get("userAndLocation") or {}
    email = ual.get("email")
    if not email:
      continue
    location_map[email.lower()] = {
      "position": ual.get("position"),
      "building": buildings_by_id.get(ual.get("buildingId")),
    }

  # mobile-devices: building name is embedded directly
  page = 0
  endpoint = f"/api/v2/mobile-devices/detail?section=GENERAL&section=USER_AND_LOCATION&page={page}&page-size=1000&sort=deviceId%3Aasc"
  response = jamf_get(endpoint, token, session)
  devices = []
  while True:
    data = response.json()
    devices.extend(data["results"])
    if len(devices) >= data["totalCount"]:
      break
    page += 1
    endpoint = f"/api/v2/mobile-devices/detail?section=GENERAL&section=USER_AND_LOCATION&page={page}&page-size=1000&sort=deviceId%3Aasc"
    response = jamf_get(endpoint, token, session)
  for d in devices:
    ual = d.get("userAndLocation") or {}
    email = ual.get("emailAddress")
    if not email:
      continue
    location_map[email.lower()] = {
      "position": ual.get("position"),
      "building": ual.get("building"),
    }

  return location_map

def _match_school(text):
  if not text:
    return None
  if re.search(r"College Society", text, re.IGNORECASE):
    return "Society"
  if re.search(r"College (Junior|Senior) High", text, re.IGNORECASE):
    return "Conklin"
  if re.search(r"College (Elementary|Primary)", text, re.IGNORECASE):
    return "Collett"
  if re.search(r"Academy", text, re.IGNORECASE):
    return "Academy"
  return None

def get_school(user, location_map):
  email = user.get("email")
  if not email:
    return None
  location = location_map.get(email.lower())
  if not location:
    return None
  for field in ("position", "building"):
    school = _match_school(location.get(field))
    if school:
      return school
  return None

def parse(user, location_map):
  username = user.get("username", "")
  if username and ("@" in username or re.search(r"-\d", username)):
    return None

  realname = user.get("realname") or ""
  parts = realname.split()

  return {
    "email": user.get("email"),
    "first": parts[0] if parts else "",
    "last": parts[-1] if len(parts) > 1 else parts[0] if parts else "",
    "full": realname or None,
    "username": user.get("email").split("@")[0] if user.get("email") else username,
    "grade": get_grade(user),
    "school": get_school(user, location_map),
  }

def dedup(users):
  seen = set()
  unique_users = []
  for u in users:
    identifier = (u["email"], u["first"], u["last"])
    if identifier not in seen:
      seen.add(identifier)
      unique_users.append(u)
  return unique_users

def create_timestamp():
  try:
    with open(TIMESTAMP_PATH, "w") as f:
      f.write(str(int(time.time())))
    print("Successfully created last_run.timestamp")
  except OSError as e:
    print(f"Error writing .timestamp: {e}")

# ============================================================================================================================================================

def main():
  if not run_check() and not TESTING_MODE:
    return

  jamf_client.init()

  with jamf_session() as (token, session):
    # get all users + handle pagination
    raw = { "total": 0, "responses": [] }
    page = 0
    endpoint = f"/api/v1/users?page={page}&page-size=1000&sort=realname%3Aasc&platform=false"
    response = jamf_get(endpoint, token, session)
    # do while hasNext is true
    while True:
      data = response.json()
      raw["responses"].extend(data["results"])
      if not data["hasNext"]:
        break
      page += 1
      endpoint = f"/api/v1/users?page={page}&page-size=1000&sort=realname%3Aasc&platform=false"
      response = jamf_get(endpoint, token, session)

    # write raw
    raw["total"] = len(raw["responses"])
    with open(RAW_PATH, "w") as f:
      json.dump(raw, f, indent=2, sort_keys=True)

    # build email -> position/building map for get_school()
    location_map = build_location_map(token, session)

    # cleanup raw
    users = [parse(u, location_map) for u in raw["responses"]]
    users = [u for u in users if u and u["email"] and u["first"] and u["last"]]
    users_final = dedup(users)

    # write cleaned
    with open(LOOKUP_PATH, "w") as f:
      json.dump(users_final, f, indent=2, sort_keys=False)
    print(f"Successfully created lookup.json with {len(users_final)} entries")

    create_timestamp()
    print("Done query.py\n")

# ============================================================================================================================================================

if __name__ == "__main__":
  main()
