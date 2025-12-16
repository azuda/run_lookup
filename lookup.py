# lookup.py

"""
cli tool for searching all users by email or name
"""

import os
import query
import json
import argparse
import re
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "lookup.json")

if not os.path.isfile(LOOKUP_PATH):
  query.main()
with open(LOOKUP_PATH, "r") as f:
  ALL_USERS = json.load(f)



def lookup(first, last):
  global ALL_USERS

  results = []
  if not ALL_USERS:
      return results

  # 2 args provided
  if last:
    # re_first = re.compile(r"\b" + re.escape(first) + r"\b", re.IGNORECASE)
    # re_last = re.compile(r"\b" + re.escape(last) + r"\b", re.IGNORECASE)
    query1 = first.lower()
    query2 = last.lower()
    for entry in ALL_USERS:
      first_name = entry.get("first", "").lower()
      last_name = entry.get("last", "").lower()
      if query1 in first_name and query2 in last_name:
        results.append(entry)

  # 1 arg provided
  else:
    query = first.lower()
    for entry in ALL_USERS:
      first_name = entry.get("first", "").lower()
      last_name = entry.get("last", "").lower()
      email = entry.get("email", "").lower()
      uname = entry.get("username", "").lower()
      if query in first_name or query in last_name or query in email or query in uname:
        results.append(entry)

  return results

def main():
  # update lookup table if last_run >= 7 days ago
  query.main()

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "firstname",
    metavar="identifier/firstname",
    help="identifier to lookup (first / last / email) OR first name if 2nd arg provided"
  )
  parser.add_argument(
    "lastname",
    metavar="lastname",
    nargs="?",
    help="[optional] last name to lookup"
  )

  args = parser.parse_args()
  print(f"Looking up [ {args.firstname}, {args.lastname if args.lastname else 'None'} ]")
  results = lookup(args.firstname, args.lastname)
  if results == []:
    print("No entries found")
  else:
    df = pd.DataFrame(results).sort_values("last")
    print(df)



if __name__ == "__main__":
  main()
