#!/bin/bash

main() {
    # ignore trigger workaround for atlassian bug
    # https://jira.atlassian.com/browse/JRASERVER-64216
    if [ ${TRIGGER} = "issue_commented" ] \
        || [ ${TRIGGER} = "issue_comment_edited" ] \
        || [ ${TRIGGER} = "issue_comment_deleted" ]; then return 0 ; fi

    # remote repo where submissions are pushed for review
    REPO_URL="github.com/${GITHUB_USERNAME}/workspace-microapps-test-bundles.git"
    REPO_NAME="workspace-microapps-test-bundles"

    # clone workspace microapps bundles repo and enter
    git clone "https://${REPO_URL}" --branch master
    cd $REPO_NAME

    # create new or checkout existing branch
    git fetch origin -a
    if git branch -a | grep $JIRA_ISSUEID ; then
        git checkout --track origin/$JIRA_ISSUEID
    else
        git checkout -b $JIRA_ISSUEID
    fi

    # manipulate the files via python script
    python3 ../format-submission.py \
    --svcacctName "${SVCACCT_NAME}" \
    --svcacctPwd "${SVCACCT_PWD}" \
    --issueId "${JIRA_ISSUEID}" || return 0

    # add and push files to remote branch
    git add *
    git commit -sm "microapp submission - see issue ${JIRA_ISSUEID} on issues.citrite.net"
    git push "https://${GITHUB_USERNAME}:${GITHUB_API_KEY}@${REPO_URL}" HEAD:${JIRA_ISSUEID}

    # create pull request using GitHub API
    url="https://${GITHUB_USERNAME}:${GITHUB_API_KEY}@api.github.com/repos/${GITHUB_USERNAME}/${REPO_NAME}/pulls"
    header="Content-Type: application/json"
    data="{
        \"title\": \"microapps submission\",
        \"body\": \"Check submission before merging to master\",
        \"head\": \"${JIRA_ISSUEID}\",
        \"base\": \"master\"
    }"
    curl --request POST --url "${url}" --header "${header}" --data "${data}"
}

# parse command line parameters
while getopts n:p:i:k:u:t: option
do
case "${option}"
in
n) SVCACCT_NAME=${OPTARG};;
p) SVCACCT_PWD=${OPTARG};;
i) JIRA_ISSUEID=${OPTARG};;
k) GITHUB_API_KEY=${OPTARG};;
u) GITHUB_USERNAME=${OPTARG};;
t) TRIGGER=${OPTARG};;
esac
done

main "${SVCACCT_NAME}" "${SVCACCT_PWD}" "${JIRA_ISSUEID}" "${GITHUB_API_KEY}" "${GITHUB_USERNAME}" "${TRIGGER}"