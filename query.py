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

# departments that pass through as-is (after stripping "Rundle "), everything else is "Society"
PASSTHROUGH_DEPARTMENTS = {"Academy", "College", "Studio", "IT"}

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

def get_all(endpoint, token, session):
  # page through a jamf pro api inventory endpoint, endpoint must end with "page="
  page = 0
  results = []
  while True:
    data = jamf_get(f"{endpoint}{page}", token, session).json()
    results.extend(data["results"])
    if not data["results"] or len(results) >= data["totalCount"]:
      return results
    page += 1

def build_department_map(token, session):
  # email/username -> department names across every computer and mobile device assigned to that user
  response = jamf_get("/api/v1/departments?page=0&page-size=200&sort=id%3Aasc", token, session)
  departments_by_id = {d["id"]: d["name"] for d in response.json()["results"]}

  records = []
  computers = get_all("/api/v3/computers-inventory?section=USER_AND_LOCATION&page-size=1000&sort=id%3Aasc&page=", token, session)
  for c in computers:
    ual = c.get("userAndLocation") or {}
    # computers only carry the department id
    records.append((ual.get("email"), ual.get("username"), departments_by_id.get(ual.get("departmentId"))))
  devices = get_all("/api/v2/mobile-devices/detail?section=USER_AND_LOCATION&page-size=1000&sort=deviceId%3Aasc&page=", token, session)
  for d in devices:
    ual = d.get("userAndLocation") or {}
    # mobile devices carry the department name directly
    records.append((ual.get("emailAddress"), ual.get("username"), ual.get("department") or departments_by_id.get(ual.get("departmentId"))))

  department_map = {}
  for email, username, department in records:
    if not department:
      continue
    for key in {k.strip().lower() for k in (email, username) if k and k.strip()}:
      names = department_map.setdefault(key, [])
      if department not in names:
        names.append(department)
  return department_map

def get_school(user, department_map):
  # department on the user's computers/devices, "Rundle College" -> "College", "Rundle Academy" -> "Academy"
  # users whose devices are in more than one department get all of them, e.g. "Academy/College"
  departments = []
  for key in (user.get("email"), user.get("username")):
    if key and key.strip():
      departments = department_map.get(key.strip().lower(), [])
      if departments:
        break
  # every other department (Heads, Facilities, HR, ...) is society staff -> "Society"
  schools = set()
  for d in departments:
    name = re.sub(r"^Rundle\s+", "", d.strip(), flags=re.IGNORECASE)
    if name:
      schools.add(name if name in PASSTHROUGH_DEPARTMENTS else "Society")
  return "/".join(sorted(schools)) or None

def is_excluded(user):
  username = user.get("username", "")
  return bool(username and ("@" in username or re.search(r"-\d", username)))

def parse(user, department_map):
  if is_excluded(user):
    return None

  username = user.get("username", "")
  realname = user.get("realname") or ""
  parts = realname.split()

  return {
    "email": user.get("email"),
    "first": parts[0] if parts else "",
    "last": parts[-1] if len(parts) > 1 else parts[0] if parts else "",
    "full": realname or None,
    "username": user.get("email").split("@")[0] if user.get("email") else username,
    "grade": get_grade(user),
    "school": get_school(user, department_map),
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

    # build email/username -> device department map for get_school()
    department_map = build_department_map(token, session)

    # cleanup raw
    users = [parse(u, department_map) for u in raw["responses"]]
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
