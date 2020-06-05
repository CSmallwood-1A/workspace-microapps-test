#!/usr/bin/env python3

import argparse
import json
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
    errorMessage = 'Jenkins script failed: {}'.format(error)
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
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print('failed to write error to Jira: {}'.format(e))
    exit(1)


def get_mapp_file(issueJson):
    # only allow one attachment and must be a .mapp file
    mappFile = ""
    numAttachments = len(issueJson['fields']['attachment'])
    if numAttachments > 1:
        _error_writeback("only attach a single file")
    elif numAttachments < 1:
        _error_writeback("must attach a .mapp file")
    else:
        mappFile = issueJson['fields']['attachment'][0]['filename']
        if not mappFile.endswith('.mapp'):
            _error_writeback("attachment must be a .mapp file")
        url = issueJson['fields']['attachment'][0]['content']
        try:
            response = requests.get(
                url=url,
                auth=AUTH
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            _error_writeback('failed to download attachment: {}'.format(e))
        with open(mappFile, 'wb') as fout:
            fout.write(response.content)
    return mappFile


def get_issue():
    try:
        response = requests.get(
            url='{}/rest/api/2/issue/{}'.format(HOST, ISSUE_ID),
            headers=HEADERS,
            auth=AUTH,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        _error_writeback('failed to get Jira issue: {}'.format(e))
    else:
        return response.json()


def format_bundle(mappFile, privacyUrl, documentationUrl, termsOfUseUrl, supportUrl, vendor):
    # extract contents of .mapp file into temporary directory
    try:
        with zipfile.ZipFile(mappFile, 'r') as zin:
            tempDir = 'temp'
            subprocess.run('mkdir {}'.format(tempDir), shell=True, check=True)
            zin.extractall(tempDir)
    except IOError as e:
        _error_writeback('.mapp file not found: {}'.format(e))
    except subprocess.CalledProcessError as e:
        _error_writeback('failed to create {} directory: {}'.format(tempDir, e))
    
    # edit the metadata file
    exportId = ""
    try:
        with open('{}/{}'.format(tempDir, METADATA_FILE), 'r+') as fin:
            jsoncontents = json.load(fin)
            jsoncontents['vendor'] = vendor
            jsoncontents.pop('tags')
            jsoncontents.update({'metadata': []})
            jsoncontents['metadata'].append({'tag': 'privacyUrl', 'value': privacyUrl})
            jsoncontents['metadata'].append({'tag': 'documentationUrl', 'value': documentationUrl})
            jsoncontents['metadata'].append({'tag': 'termsOfUseUrl', 'value': termsOfUseUrl})
            jsoncontents['metadata'].append({'tag': 'supportUrl', 'value': supportUrl})
            exportId = jsoncontents['id']
            fin.seek(0)
            json.dump(jsoncontents, fin, indent=4)
            fin.truncate()
    except IOError as e:
        _error_writeback('{} file not found in .mapp file: {}'.format(METADATA_FILE, e))
    except KeyError as e:
        _error_writeback('malformed {} file. Missing key: {}'.format(METADATA_FILE, e))

    # place files in directory structure: ./http/<vendor>/<exportid> 
    try:
        httpDir = './http'
        vendorDir = '{}/{}'.format(httpDir, vendor)
        exportDir = '{}/{}/{}'.format(httpDir, vendor, exportId)
        subprocess.run('[ -d "{}" ] || mkdir "{}"'.format(httpDir, httpDir), shell=True, check=True)
        subprocess.run('[ -d "{}" ] || mkdir "{}"'.format(vendorDir, vendorDir), shell=True, check=True)
        subprocess.run('[ -d "{}" ] || mkdir "{}"'.format(exportDir, exportDir), shell=True, check=True)
        subprocess.run('rsync -a {}/ {}/'.format(tempDir, exportDir), shell=True, check=True)
        subprocess.run('mv {} {}'.format(mappFile, exportDir), shell=True, check=True)
    except subprocess.CalledProcessError as e:
        _error_writeback('failed to create directory structure: {}'.format(e))
    

def main():
    # get the issue in json format and extract the necessary metadata
    issueJson = get_issue()
    supportUrl = issueJson['fields'][SUPPORT_URL]
    documentationUrl = issueJson['fields'][DOCUMENT_URL]
    privacyUrl = issueJson['fields'][PRIVACY_URL]
    termsOfUseUrl = issueJson['fields'][TERMS_URL]
    vendor = issueJson['fields'][VENDOR]

    # download .mapp file from Jira issue and format
    mappFile = get_mapp_file(issueJson)
    format_bundle(mappFile, privacyUrl, documentationUrl, termsOfUseUrl, supportUrl, vendor)


if __name__ == "__main__":
    main()
