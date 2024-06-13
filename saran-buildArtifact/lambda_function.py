import json
import boto3
import os
import http.client
from datetime import datetime

sm_client = boto3.client('secretsmanager')

def lambda_handler(event, context):
    print(event)

    try:
        if 'source' in event and event['source'] == 'aws.secretsmanager':
            details = event['detail']
            
            if "Boto3" not in details['userAgent']:
                if 'requestParameters' in details:
                    if 'secretId' in details['requestParameters']:
                        
                        secretId = details['requestParameters']['secretId']
                        getLatestSecret = response = sm_client.get_secret_value(
                            SecretId=secretId,
                        )
                        
                        # Delete older versions
                        deleteVersionStages(secretId)
                        
                        if 'SecretString' in getLatestSecret:
                            deleteVersionStages(secretId)
                            now = datetime.now()
                            current_date = now.strftime("%Y_%m_%d_%H_%M_%S")
                            versionStage = 'REBLIE_VERSION_' + current_date
                            addVersion = sm_client.put_secret_value(
                                SecretId=secretId,
                                SecretString=getLatestSecret['SecretString'],
                                ClientRequestToken=versionStage,
                                VersionStages=[
                                    'CREATED_ON_' + current_date,
                                ]
                            )
                            
                            prev_secret = sm_client.get_secret_value(
                                SecretId=secretId,
                                VersionStage='AWSPREVIOUS'
                            )
                            
                            if prev_secret and 'SecretString' in prev_secret and json.loads(getLatestSecret['SecretString']) != json.loads(prev_secret['SecretString']):
                                currentValue = json.loads(getLatestSecret['SecretString'])
                                pastValue = json.loads(prev_secret['SecretString'])
                                diff = dictDiff(currentValue, pastValue)
                                splitARN = secretId.split(":")
                                message = 'SECRET MANAGER (' + splitARN[-1] + '): Detected secrets change. INFO: '
                                
                                for action in diff:
                                    if len(diff[action]) > 0:
                                        arr_test = list(diff[action].keys())
                                        message += action.capitalize() + " key(s) " + ', '.join(arr_test) + '. '
                                    
                                if 'userIdentity' in details:
                                    if 'userName' in details['userIdentity']:
                                        message += 'Updated by the user - ' + details['userIdentity']['userName']
                                    elif details['userIdentity']['type'] == 'AssumedRole':
                                        message += 'Updated by the user - ' + details['userIdentity']['principalId'].split(':')[1]
                                    
                                post_to_slack(message)
                        
                        else:
                            raise Exception("No secret string available.")
                else:
                    raise Exception("Not a valid event.")
            else:
                raise Exception('Not a valid call from SecretsManager')
        else:
            raise Exception("Not a valid event.")
    except Exception as err:
        print('Failed to update version - ' + str(err))


# Check the diff between previous and current secrets
def dictDiff(newDict, oldDict):
    d1_keys = set(newDict.keys())
    d2_keys = set(oldDict.keys())
    shared_keys = d1_keys.intersection(d2_keys)
    added = dict.fromkeys(d1_keys - d2_keys, 0)
    removed = dict.fromkeys(d2_keys - d1_keys, 0)
    updated = {o : (newDict[o], oldDict[o]) for o in shared_keys if newDict[o] != oldDict[o]}
    
    return { 'added': added, 'removed': removed, 'updated': updated }

# Delete versions that are gerater than 20    
def deleteVersionStages(secretId):
    response = sm_client.list_secret_version_ids(SecretId=secretId)
    print(response)
    if 'Versions' in response:
        versions = response['Versions']
        while 'NextToken' in response:
            response = sm_client.list_secret_version_ids(SecretId=secretId, NextToken=response['NextToken'])
            versions += response['Versions']
        print(versions)
        if len(versions) >= 20:
            print('More than 20 versions.. Deleting old versions.')
            getDateList = []
            for version in versions:
              if 'REBLIE_VERSION' in version['VersionId']:
                dateValue = version['VersionId'].replace("REBLIE_VERSION_", "")
                getDateList.append(dateValue)
            
            
            if len(getDateList) > 0:
                getDateList.sort(key = lambda date: datetime.strptime(date, '%Y_%m_%d_%H_%M_%S'))
                oldVersions = getDateList[0:5]
                for oldversion in oldVersions:
                    removeOldVersion = sm_client.update_secret_version_stage(
                        SecretId=secretId,
                        VersionStage='CREATED_ON_' + oldversion,
                        RemoveFromVersionId='REBLIE_VERSION_' + oldversion,
                    )
        else:
            print('Versions list is less than 20.')
            

# Notify in slack about secret manager value update
def post_to_slack(text):
    print(text)
        
    payload = {
        "channel": os.environ['SLACK_CHANNEL'],
        "text": text
    }

    payload['username'] = "SecretsManager"
    payload['icon_emoji'] = ":rocket:"

    headers = {"Content-type": "application/json"}
    conn = http.client.HTTPSConnection('hooks.slack.com')
    conn.request("POST", os.environ['SLACK_WEBHOOK_PATH'], json.dumps(payload), headers)
    response = conn.getresponse()

    if response.status == 200:
        conn.close()
    else:
        response_text = response.read()
        conn.close()