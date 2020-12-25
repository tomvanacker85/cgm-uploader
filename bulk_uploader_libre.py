# A script to upload Libre data to Nightscout.
#
# Use the Libre desktop app to transfer data from your Libre to a tsv file, then run this script.
#
# Inspired by https://github.com/cjo20/ns-api-uploader
# Requires Python 3

import argparse
import csv
from datetime import datetime, timezone
import glob
import hashlib
import json
import os
from shutil import copyfile

import requests # pip3 install requests

entries = []


def url_and_headers(base_url, api_secret):
    url = "%s/api/v1/entries" % base_url
    hashed_secret = hashlib.sha1(api_secret.encode('utf-8')).hexdigest()
    headers = {'API-SECRET' : hashed_secret,
               'Content-Type': "application/json",
               'Accept': 'application/json'}
    print(url)
    print(headers)
    return url, headers


def find_last_nightscout_entry(url, headers):
    r = requests.get(url, headers=headers)
    entries = r.json()
    if len(entries) == 0:
        last_timestamp = 0
        print("No entries found in Nightscout")
    else:
        last_timestamp = entries[0]['date'] / 1000
        dt = datetime.fromtimestamp(last_timestamp)
        print("Last timestamp in Nightscout: %s" % dt)
    return last_timestamp
    

def upload_to_nightscout(libre_csv, base_url, api_secret, max_size=100, max_attempts=5):

    current_timestamp = int(datetime.now().timestamp())
    print("Current time: %s" % datetime.fromtimestamp(current_timestamp))
    tz = datetime.now(timezone.utc).astimezone().tzinfo # the local timezone

    url, headers = url_and_headers(base_url, api_secret)
    last_timestamp = find_last_nightscout_entry(url, headers)
    
    with open(libre_csv, 'r') as csvfile:
        # See format of Libre tsv file discussed here: https://github.com/nahog/freestyle-libre-parser-viewer
        reader = csv.reader(csvfile)
        next(reader, None)  # skip the first line (patient name)
        next(reader, None)  # skip the headers
        i = 0
        for row in reader:
            if len(row) > 2: # omdat registratie van insuline een error veroorzaakt
                time = row[2]
                dt = datetime.strptime(time, "%m-%d-%Y %I:%M %p")
                dt = dt.replace(tzinfo=tz)
                timestamp = dt.timestamp()
                if timestamp <= last_timestamp:
                    continue
                if timestamp >= current_timestamp:
                    continue # ignore times in the future
                date = int(timestamp * 1000)
                date_string = dt.isoformat()
                record_type = int(row[3])
                if record_type == 0: # historic glucose
                    entry = dict(type='sgv', sgv=float(row[4]), date=date, dateString=date_string)
                    #print(entry)
                    entries.append(entry)
                elif record_type == 1: # scan glucose
                    entry = dict(type='sgv', sgv=float(row[5]), date=date, dateString=date_string)
                    entries.append(entry)
                if (len(entries) == int(max_size)):
                    #write entries to nightscout to avoid overflow
                    upload_entries(i, entries, url, headers, max_attempts)
                    i += 1
            
        #write the last part to nightscout
        if len(entries)>0:
            upload_entries(i, entries, url, headers, max_attempts)
        
        #print("Number of entries: %d" % len(entries))

        #for entry in entries:
        #    print(entry)
        
        if len(entries) == 0:
            print("No new entries")
            return
 

def upload_entries(i, entries, url, headers, max_attempts):
    
    attempts = 0
    #print(len(entries))
    while attempts < int(max_attempts):
        r = requests.post(url, headers=headers, data=json.dumps(entries))
        if r.status_code == 200:
            print("Uploaded package %d successfully" % i)
            #print(r.text)
            break
        else:
            attempts += 1
            print("Uploading package %d FAILED" % i)
            print("%d" % r.status_code)
            print(r.text)
    entries.clear()
    
        



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--api_secret', help="API-SECRET for uploading", required=True)
    parser.add_argument('--base_url', help="Base URL of Nightscout site", required=True)
    parser.add_argument('--libre_csv', help="Export data file from FreeStyle Libre website", required=True)
    parser.add_argument('--max_size', default=100, help="Maximum number of entries to upload at once", required=False)
    parser.add_argument('--max_attempts', default=5, help="Maximum number of attempts to upload data to Nightscout site", required=False)
    args = parser.parse_args()

    upload_to_nightscout(args.libre_csv, args.base_url, args.api_secret, args.max_size, args.max_attempts)
