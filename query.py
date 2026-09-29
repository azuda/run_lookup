# query.py

"""
- gets all users in jamf via api
- write email, first, last, fullname, username to .json
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import jamf_client
from jamf_client import jamf_get, jamf_session
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIMESTAMP_PATH = os.path.join(SCRIPT_DIR, "last_run.timestamp")
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "lookup.json")
RAW_PATH = os.path.join(SCRIPT_DIR, "raw.json")
CACHE_TTL = 604800

TESTING_MODE = False

token_lock = threading.Lock()

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

def get_sites(user_id, token, session):
  # the classic API's JSON output always returns sites as null, so this has to read the XML
  with token_lock:
    if int(time.time()) > token.expiration - 15:
      token.access_token, expires_in = jamf_client.get_token()
      token.expiration = int(time.time()) + expires_in
  response = session.get(
    f"{jamf_client.get_jamf_url()}/JSSResource/users/id/{user_id}",
    headers={"accept": "application/xml", "authorization": f"Bearer {token.access_token}"},
    timeout=30,
  )
  if not response.ok:
    return []
  root = ET.fromstring(response.content)
  return [name.text for name in root.findall("./sites/site/name") if name.text]

def build_site_map(users, token, session):
  # site assignments only exist on the classic per-user record, so fetch them concurrently
  with ThreadPoolExecutor(max_workers=8) as pool:
    sites = pool.map(lambda u: get_sites(u["id"], token, session), users)
    return {u["id"]: s for u, s in zip(users, sites)}

def get_school(user, site_map):
  # "Rundle College Elementary" -> "College", "Rundle Academy Senior High" -> "Academy"
  # "Rundle College Society" is its own school -> "Society"
  # users assigned to sites in more than one school get all of them, e.g. "Academy/College"
  schools = []
  for site in site_map.get(user.get("id"), []):
    if re.search(r"College Society", site, re.IGNORECASE):
      school = "Society"
    else:
      words = re.sub(r"^Rundle\s+", "", site.strip(), flags=re.IGNORECASE).split()
      school = words[0] if words else None
    if school and school not in schools:
      schools.append(school)
  return "/".join(sorted(schools)) or None

def is_excluded(user):
  username = user.get("username", "")
  return bool(username and ("@" in username or re.search(r"-\d", username)))

def parse(user, site_map):
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
    # "school": get_school(user, site_map),
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

    # build user id -> site name map for get_school(), skipping users parse() drops anyway
    site_map = build_site_map([u for u in raw["responses"] if not is_excluded(u)], token, session)

    # cleanup raw
    users = [parse(u, site_map) for u in raw["responses"]]
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
