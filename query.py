# query.py

"""
- gets all users in jamf via api
- write email, first, last, fullname, username to .json
"""

import json
import os
import re
import requests
import time
import urllib3

from jamf_credential import JAMF_URL, check_token_expiration, get_token, invalidate_token

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIMESTAMP_PATH = os.path.join(SCRIPT_DIR, "last_run.timestamp")
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "lookup.json")

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
  return int(time.time()) - last_epoch > 604800

def get(endpoint, access_token, token_expiration_epoch):
  access_token, token_expiration_epoch = check_token_expiration(access_token, token_expiration_epoch)

  url = f"{JAMF_URL}{endpoint}"
  headers = {
    "accept": "application/json",
    "authorization": f"Bearer {access_token}"
  }
  response = requests.get(url, headers=headers, verify=False)
  return response, access_token, token_expiration_epoch

def get_first_last(full):
  parts = full.split()
  return parts[0], parts[-1] if len(parts) > 1 else ""

def parse(user):
  username = user.get("username", "")
  if username and (re.search(r"@", username) or re.search(r"-\d", username)):
    return None

  return {
    "email": user.get("email"),
    "first": user.get("realname").split()[0] if user.get("realname") else "",
    "last": user.get("realname").split()[-1] if user.get("realname") else "",
    "full": user.get("realname"),
    "username": user.get("email").split("@")[0] if user.get("email") else user.get("username"),
    "EGY": user.get("position").split("EGY")[-1] if "EGY" in user.get("position") else "",
    # "building": user.get("building").split("Rundle")[-1]
  }

def dedup(users):
  seen = set()
  unique_users = []
  for u in users:
    identifier = (u["email"], u["first"], u["last"])
    if identifier not in seen:
      seen.add(identifier)
      unique_users.append(u)
  users = unique_users
  return users

def create_timestamp():
  epoch = int(time.time())
  epoch_str = str(epoch)
  try:
    with open(TIMESTAMP_PATH, "w") as f:
      f.write(epoch_str)
    print("Succesfully created last_run.timestamp")
  except Exception as e:
    print(f"Error writing .timestamp: {e}")
  return

# ============================================================================================================================================================

def main():
  if not run_check() and TESTING_MODE == False:
    return

  # create jamf access token
  access_token, expires_in = get_token()
  token_expiration_epoch = int(time.time()) + expires_in
  print(f"Token valid for {expires_in} seconds")

  # print jamf pro version
  version_url = f"{JAMF_URL}/api/v1/jamf-pro-version"
  headers = {"Authorization": f"Bearer {access_token}"}
  version = requests.get(version_url, headers=headers, verify=False)
  print("Jamf Pro version:", version.json()["version"])

  # get all users + handle pagination
  raw = { "total": 0, "responses": [] }
  page = 0
  endpoint = f"/api/v1/users?page={page}&page-size=1000&sort=realname%3Aasc&platform=false"
  response, access_token, token_expiration_epoch = get(endpoint, access_token, token_expiration_epoch)
  # do while hasNext is true
  while True:
    raw["responses"].extend(response.json()["results"])
    if not response.json()["hasNext"]:
      break
    page += 1
    endpoint = f"/api/v1/users?page={page}&page-size=1000&sort=realname%3Aasc&platform=false"
    response, access_token, token_expiration_epoch = get(endpoint, access_token, token_expiration_epoch)

  # write raw
  for _ in raw["responses"]:
    raw["total"] += 1
  with open("raw.json", "w") as f:
    json.dump(response.json(), f, indent=2, sort_keys=True)

  # cleanup raw
  users = [parse(u) for u in raw["responses"]]
  users = [u for u in users if u and u["email"] and u["first"] and u["last"]]
  users_final = dedup(users)

  # write cleaned
  with open("lookup.json", "w") as f:
    json.dump(users_final, f, indent=2, sort_keys=False)
  print(f"Successfully created lookup.json with {len(users_final)} entries")

  create_timestamp()
  print("Done query.py\n")

# ============================================================================================================================================================

if __name__ == "__main__":
  urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
  main()
