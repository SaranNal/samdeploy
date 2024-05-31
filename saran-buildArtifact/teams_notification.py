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
    conn.request("POST", "/webhookb2/93eea688-6368-4c47-8d54-92a7ba364b30@196eed21-c67a-4aae-a70b-9f97644d5d14/IncomingWebhook/b33092ade4844d969f3031df68fd25b4/73c1d036-08b9-4dd3-8346-afa964097b0a" , json.dumps(payload), headers)
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
        'prod': 'Production',
        'stage': 'Staging',
        'dev': 'Development'
    }
    
    if environmentName in environments:
        username = environments[environmentName]
    return username
    
