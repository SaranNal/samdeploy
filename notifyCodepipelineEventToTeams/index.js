var https = require('https');
var util = require('util');
var AWS = require("aws-sdk");
exports.handler = async (event) => {
    console.log(event)
    var branchName, teams_text, environment = ''
    if ('Records' in event) {
        var data = JSON.parse(event['Records'][0]['Sns']['Message'])
        // branchName = data['detail']['pipeline'].toLowerCase().replace('whitewell-', '').replace('ex-', 'expedited-').replace(/prod$/, 'production-deploy-only').replace('prod-web', 'production-web-deploy-only').replace('prod-jobs', 'production-jobs-deploy-only').replace(/-/g, ' ');
        branchName = data['detail']['pipeline'].toLowerCase()
        var status = ucwords(data['detail']['state'].toLowerCase());
        branchName = ucwords(branchName)
        
        teams_text = '<b>Pipeline status</b> - ' + status + "\n";
        
        if (status == 'Failed') {
            teams_text += 'Check here for more info - ' + process.env.PIPELINE_URL + data['detail']['pipeline'] + '/view?region=us-east-1'
        }
    }
    // else {
    //     branchName = ucwords(event['detail']['referenceName'].toLowerCase().replace('ex-', 'expedited-').replace(/prod$/, 'production-deploy-only').replace('prod-web', 'production-web-deploy-only').replace('prod-jobs', 'production-jobs-deploy-only').replace(/-/g, ' '));
    //     environment = 'Ad';
    //     if (event['detail']['repositoryName'] == 'whitewell-buildArtifacts') {
    //         environment = 'whitewell-buildArtifacts';
    //     }
    //     branchName = branchName + " " + environment;
    //     var commitId = event['detail']['commitId'];
    //     var triggeringUser = event['detail']['callerUserArn'].split('/').pop();
    //     teams_text = "Deployment with Commit ID: " + commitId.substring(0, 10) + " on " + branchName + " initiated by " + triggeringUser;
    // }
    
    
    return new Promise((resolve, reject) => {
        var postData = {
            "channel": process.env.TEAMS_CHANNEL,
            "text": "<b>CodePipeline: </b>(" + branchName + ")<br>" + teams_text
        };
        
        var options = {
            method: 'POST',
            hostname: 'knackforge.webhook.office.com',
            port: 443,
            path: '/webhookb2/b59b6d0e-c4fc-4e9a-b5ff-f098d415593b@196eed21-c67a-4aae-a70b-9f97644d5d14/IncomingWebhook/bd9dc73e327045839fe0fc90e9c47abb/02c96413-1377-45e8-a483-58a3d3bc0a20'
        };
    
        const req = https.request(options, (res) => {
          resolve('Success');
        });

        req.on('error', (e) => {
          console.log('problem with request: ' + e.message);
          reject(e.message);
        });

        req.write(util.format("%j", postData));
        req.end();
    });

    function ucwords (str) {
        return (str + '').replace(/^([a-z])|\s+([a-z])/g, function ($1) {
            return $1.toUpperCase();
        });
    }
};