#!/usr/bin/env python3

import argparse
import json
import os
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import subprocess
import zipfile

# submission process starts from MICROSUB project on issues.citrite.net
HOST = "https://issues.citrite.net"

# Submission issue type has multiple custom fields
SUPPORT_URL = "customfield_12635"
DOCUMENT_URL = "customfield_31030"
PRIVACY_URL = "customfield_31032"
TERMS_URL = "customfield_31031"
VENDOR = "customfield_31230"

# metadata for bundle is held in the METADATA_FILE
METADATA_FILE = "metadata.json"

# parse args to obtain credentials for Jira API
parser = argparse.ArgumentParser(description='Format the export to include extra metadata from third parties')
parser.add_argument('--issueId', type=str, required=True, help='id of the issue that triggered the build')
parser.add_argument('--svcacctPwd', type=str, required=True, help='password for the service account making call to Jira')
parser.add_argument('--svcacctName', type=str, required=True, help='service account name used for Jira API calls')
args = parser.parse_args()
SVCACCT_NAME = args.svcacctName
SVCACCT_PWD = args.svcacctPwd
ISSUE_ID = args.issueId
AUTH = HTTPBasicAuth(SVCACCT_NAME, SVCACCT_PWD)
HEADERS = {'Content-Type': 'application/json'}


def _error_writeback(error):
    errorMessage = "Jenkins script failed: " + error
    payload = json.dumps( {
        "body": errorMessage
    } )
    try:
        response = requests.post(
            url='{}/rest/api/2/issue/{}/comment'.format(HOST, ISSUE_ID),
            headers=HEADERS,
            auth=AUTH,
            data=payload
        )
    except:
        print(response.text)
    exit(1)


def download_attachments():
    params = {'fields': 'attachment'}
    attachments = []
    try:
        response = requests.get(
            url='{}/rest/api/2/issue/{}'.format(HOST, ISSUE_ID),
            headers=HEADERS,
            auth=AUTH,
            params=params
        )
        jsonData = response.json()
        for attachment in jsonData['fields']['attachment']:
            filename = attachment['filename']
            url = attachment['content']
            response = requests.get(
                url=url,
                auth=AUTH
            )
            with open(filename, 'wb') as fout:
                fout.write(response.content)
            attachments.append(filename)
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)
    return attachments


def get_issue():
    try:
        response = requests.get(
            url='{}/rest/api/2/issue/{}'.format(HOST, ISSUE_ID),
            headers=HEADERS,
            auth=AUTH,
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)


def find_mapp_file(attachments):
    index = 0
    mapIndex = 0
    mappNum = 0
    for attachment in attachments:
        if attachment.endswith('.mapp'):
            mappNum += 1
            mapIndex = index
        if mappNum > 1:
            _error_writeback("more than one .mapp file attached")
        index += 1
    if mappNum == 0:
        _error_writeback("no .mapp file attached")
    return attachments[mapIndex]


def format_bundle(mappFile, privacyUrl, documentationUrl, termsOfUseUrl, supportUrl, vendor):
    try:
        with zipfile.ZipFile(mappFile, 'r') as zin:
            # extract into temporary directory
            tempDir = 'temp'
            os.system('mkdir {}'.format(tempDir))
            zin.extractall(tempDir)

        with open(tempDir + '/' + METADATA_FILE, 'r+') as fin:
            jsoncontents = json.load(fin)
            jsoncontents['vendor'] = vendor
            jsoncontents.pop('tags')
            jsoncontents.update({'metadata': []})
            jsoncontents['metadata'].append({'tag': 'privacyUrl', 'value': privacyUrl})
            jsoncontents['metadata'].append({'tag': 'documentationUrl', 'value': documentationUrl})
            jsoncontents['metadata'].append({'tag': 'termsOfUseUrl', 'value': termsOfUseUrl})
            jsoncontents['metadata'].append({'tag': 'supportUrl', 'value': supportUrl})
            
            # create directory structure: ./http/<vendor>/<exportid> 
            exportId = jsoncontents['id']
            httpDir = 'http'
            vendorDir = '{}/{}'.format(httpDir, vendor)
            exportDir = '{}/{}/{}'.format(httpDir, vendor, exportId)
            os.system('mkdir {}'.format(httpDir))
            os.system('mkdir {}'.format(vendorDir))
            os.system('mkdir {}'.format(exportDir))        
            os.system('mv {}/* {}'.format(tempDir, exportDir))
            os.system('mv {} {}'.format(mappFile, exportDir))    

            fin.seek(0)
            json.dump(jsoncontents, fin, indent=4)
            fin.truncate()
    except: 
        _error_writeback("missing or malformed .mapp file")
    

def main():
    # get the issue in json format and extract the necassary metadata
    issueJson = get_issue()
    supportUrl = issueJson['fields'][SUPPORT_URL]
    documentationUrl = issueJson['fields'][DOCUMENT_URL]
    privacyUrl = issueJson['fields'][PRIVACY_URL]
    termsOfUseUrl = issueJson['fields'][TERMS_URL]
    vendor = issueJson['fields'][VENDOR]

    # download attachemnts from Jira issue
    attachments = download_attachments()
    mappFile = find_mapp_file(attachments)

    # format the microapp bundle
    format_bundle(mappFile, privacyUrl, documentationUrl, termsOfUseUrl, supportUrl, vendor)


main()
