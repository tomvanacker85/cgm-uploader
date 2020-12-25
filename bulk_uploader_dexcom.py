# A script to upload Dexcom data to Nightscout.
#
# Use the Dexcom desktop app to transfer data from your Dexcom to a tsv file, then run this script.
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
    return url, headers


def upload_to_nightscout(dexcom_csv, base_url, api_secret, max_size=100, max_attempts=5):

    current_timestamp = int(datetime.now().timestamp())
    print("Current time: %s" % datetime.fromtimestamp(current_timestamp))
    tz = datetime.now(timezone.utc).astimezone().tzinfo # the local timezone

    url, headers = url_and_headers(base_url, api_secret)
    
    with open(dexcom_csv, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for k in range(10):
            next(reader, None)  # skip the first lines
        i = 0
        for row in reader:
            time = row[1]
            dt = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S")
            dt = dt.replace(tzinfo=tz)
            timestamp = dt.timestamp()
            date = int(timestamp * 1000)
            date_string = dt.isoformat()
            record_type = row[2]
            if record_type == "EGV": # historic glucose
                if row[7] == "Laag":
                    entry = dict(type='sgv', sgv=float(39), date=date, dateString=date_string)
                else:
                    entry = dict(type='sgv', sgv=float(row[7]), date=date, dateString=date_string)
                entries.append(entry)
            elif record_type == "Kalibratie": # scan glucose
                entry = dict(type='sgv', sgv=float(row[7]), date=date, dateString=date_string)
                entries.append(entry)
            
            if (len(entries) == max_size):
                #write entries to nightscout to avoid overflow
                upload_entries(i, entries, url, headers, max_attempts)
                i += 1
            
        #write the last part to nightscout
        upload_entries(i, entries, url, headers, max_attempts)



def upload_entries(i, entries, url, headers, max_attempts):
    
    attempts = 0
    while attempts < int(max_attempts):
        r = requests.post(url, headers=headers, data=json.dumps(entries))
        if r.status_code == 200:
            print("Uploaded package %d successfully" % i)
            #print(r.text)
            break
        else:
            attempts += 1
            print("Uploaded package %d FAILED" % i)
            print("%d" % r.status_code)
            #print(r.text)
    entries.clear()
    
        
print("Number of entries: %d" % len(entries))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--api_secret', help="API-SECRET for uploading", required=True)
    parser.add_argument('--base_url', help="Base URL of Nightscout site", required=True)
    parser.add_argument('--dexcom_csv', help="Export data file from  Dexcom website", required=True)
    parser.add_argument('--max_size', default=100, help="Maximum number of entries to upload at once", required=False)
    parser.add_argument('--max_attempts', default=5, help="Maximum number of attempts to upload data to Nightscout site", required=False)
    args = parser.parse_args()

    upload_to_nightscout(args.dexcom_csv, args.base_url, args.api_secret, args.max_size, args.max_attempts)
