# lookup.py

"""
- search users by email or name from .json created by query.py
- print results as df
"""

import argparse
import json
import os
import pandas as pd
import query

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOOKUP_PATH = os.path.join(SCRIPT_DIR, "lookup.json")

def lookup(first, last, all_users):
  results = []
  if not all_users:
    return results

  # 2 args provided
  if last:
    query1 = first.lower()
    query2 = last.lower()
    for entry in all_users:
      first_name = entry.get("first", "").lower()
      last_name = entry.get("last", "").lower()
      if query1 in first_name and query2 in last_name:
        results.append(entry)

  # 1 arg provided
  else:
    q = first.lower()
    for entry in all_users:
      first_name = entry.get("first", "").lower()
      last_name = entry.get("last", "").lower()
      email = entry.get("email", "").lower()
      uname = entry.get("username", "").lower()
      if q in first_name or q in last_name or q in email or q in uname:
        results.append(entry)

  return results

def main():
  # update lookup table if last_run >= 7 days ago
  query.main()

  with open(LOOKUP_PATH, "r") as f:
    all_users = json.load(f)

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "firstname",
    metavar="identifier/firstname",
    nargs="?",
    help="identifier to lookup (first / last / email) OR first name if 2nd arg provided"
  )
  parser.add_argument(
    "lastname",
    metavar="lastname",
    nargs="?",
    help="[optional] last name to lookup"
  )
  parser.add_argument(
    "-r",
    action="store_true",
    help="refresh cached user list"
  )

  args = parser.parse_args()
  if not args.r and not args.firstname:
    parser.print_help()
    return

  if args.r:
    if os.path.isfile(LOOKUP_PATH):
      os.remove(LOOKUP_PATH)
      print("Cleared cache")

  if not args.firstname:
    return

  print(f"Looking up [ {args.firstname}, {args.lastname if args.lastname else 'None'} ]")
  results = lookup(args.firstname, args.lastname, all_users)
  if not results:
    print("No entries found")
  else:
    df = pd.DataFrame(results).sort_values("last")
    print(df)

if __name__ == "__main__":
  main()
