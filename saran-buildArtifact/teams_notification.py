import json
import http.client

def post_to_teams(text, environmentName=None):
    print(text)
    branchName = teams_username_based_on_env(environmentName)
    payload = {
        "text": "<b>CodePipeline: </b>(" + branchName + ")<br>" + text
    }
    headers = {"Content-type": "application/json"}
    conn = http.client.HTTPSConnection('knackforge.webhook.office.com')
    conn.request("POST", "/webhookb2/b59b6d0e-c4fc-4e9a-b5ff-f098d415593b@196eed21-c67a-4aae-a70b-9f97644d5d14/IncomingWebhook/bd9dc73e327045839fe0fc90e9c47abb/02c96413-1377-45e8-a483-58a3d3bc0a20" , json.dumps(payload), headers)
    response = conn.getresponse()
    if response.status == 200:
        conn.close()
    else:
        response_text = response.read()
        conn.close()
        raise ValueError(
            'Request to teams returned an error %s, the response is:\n%s'
            % (response.status, response_text)
        )

def teams_username_based_on_env(environmentName=None):
    username = ''
    environments = {
        'production': 'Production',
        'staging': 'Staging',
        'development': 'Development'
    }
    
    if environmentName in environments:
        username = environments[environmentName]
    return username
    