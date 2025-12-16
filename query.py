# query.py

"""
- gets all users via assetsonar (which pulls from azure connector)
- saves email, first, last, fullname, username to .json
"""

from dotenv import load_dotenv
import requests
import urllib3
import sys
import os
import json
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIMESTAMP_PATH = os.path.join(SCRIPT_DIR, "last_run.timestamp")
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "lookup.json")

load_dotenv()
ASSETSONAR_TOKEN = os.getenv("AS_TOKEN")
ASSETSONAR_URL = os.getenv("AS_URL")

TESTING_MODE = False

# ==================================================================================

def run_check():
  current_epoch = int(time.time())
  if os.path.isfile(TIMESTAMP_PATH):
    with open(TIMESTAMP_PATH, "r") as f:
      last_epoch = int(f.read())
      # print(f"Current run:\t{datetime.fromtimestamp(current_epoch)}")
      # print(f"Last run:\t{datetime.fromtimestamp(last_epoch)}")
      if current_epoch - last_epoch < 604800:
        # only postpone run if lookup table exists
        if os.path.isfile(LOOKUP_PATH):
          # print("Lookup table exists")
          return False
        else:
          # print("QUERYING - lookup.json not found")
          return True
  else:
    # print("QUERYING - last_run.timestamp not found")
    return True
  return False

def get_members(page_num):
  url = f"{ASSETSONAR_URL}/members.api?page={page_num}"
  headers = {
    "token": ASSETSONAR_TOKEN,
    "content-type": "application/x-www-form-urlencoded"
  }
  params = {
    "page": page_num
  }

  try:
    response = requests.get(url, headers=headers, params=params, timeout=30, verify=False)
    response.raise_for_status()
    return response.json()
  except:
    print(f"Error fetching members page {page_num}: {sys.stderr}", file=sys.stderr)
    if response is not None:
      print(f"Response content: {response.text}", file=sys.stderr)
  return

def extract_entry(member):
  entry = {}
  entry["email"] = member.get("email")
  entry["first"] = member.get("first_name")
  entry["last"] = member.get("last_name")
  entry["full"] = member.get("full_name")
  entry["username"] = member.get("email").split("@")[0]
  return entry

def update_progress_bar(current, total, bar_length=40):
  if total == 0:
    return

  current = min(current, total)
  progress = current / total
  filled_blocks = int(round(bar_length * progress))
  bar = '=' * filled_blocks + '-' * (bar_length - filled_blocks)
  percent = round(progress * 100, 1)
  sys.stdout.write(f'\rFetching pages... [{bar}] {percent}% ({current}/{total} pages)')
  sys.stdout.flush()
  return

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


# ==================================================================================

def main():
  global TESTING_MODE

  if TESTING_MODE:
    print("=== TESTING MODE ENABLED: Getting 5 pages max ===")

  # check time since last run
  if run_check():
    # get all members from assetsonar
    members = []
    current_page = 1
    total_pages = 1
    while current_page <= total_pages:
      # print(f"Fetching page {current_page}...")
      page_data = get_members(current_page)

      if page_data is None:
        print("Failed to retrieve members page data, aborting")
        break

      # validate and add to output list
      members_on_page = page_data.get("members", [])
      if not isinstance(members_on_page, list):
        break
      for member in members_on_page:
        members.append(member)

      # handle pagination
      total_pages = page_data.get("total_pages", current_page)
      current_page += 1
      update_progress_bar(current_page - 1, total_pages)

      if TESTING_MODE:
        if current_page > 5:
          print("No subsequent pages found")
          break
      else:
        if not members_on_page and current_page > 1:
          print("No subsequent pages found")
          break

    # extract name + email to clean list
    members_clean = []
    for member in members:
      members_clean.append(extract_entry(member))

    # write to json
    # with open("raw.json", "w") as f:
      # json.dump(members, f, indent=2, sort_keys=True)
    with open(LOOKUP_PATH, "w") as f:
      json.dump(members_clean, f, indent=2, sort_keys=False)

    print(f"Saved {len(members_clean)} users to ./clean.json")

    create_timestamp()

    print("Done\n")

# ==================================================================================

if __name__ == "__main__":
  urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
  main()
