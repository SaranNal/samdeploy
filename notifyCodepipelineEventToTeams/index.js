var https = require('https');
var util = require('util');
var AWS = require("aws-sdk");
exports.handler = async (event) => {
    console.log(event)
    var branchName, teams_text, environment = ''
    if ('Records' in event) {
        var data = JSON.parse(event['Records'][0]['Sns']['Message'])
        // branchName = data['detail']['pipeline'].toLowerCase().replace('saran-', '').replace('ex-', 'expedited-').replace(/prod$/, 'production-deploy-only').replace('prod-web', 'production-web-deploy-only').replace('prod-jobs', 'production-jobs-deploy-only').replace(/-/g, ' ');
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
    //     if (event['detail']['repositoryName'] == 'saran-buildArtifacts') {
    //         environment = 'saran-buildArtifacts';
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
            // hostname: 'knackforge.webhook.office.com',
            hostname: 'knackforge.webhook.office.com',
            port: 443,
            path: '/webhookb2/93eea688-6368-4c47-8d54-92a7ba364b30@196eed21-c67a-4aae-a70b-9f97644d5d14/IncomingWebhook/b33092ade4844d969f3031df68fd25b4/73c1d036-08b9-4dd3-8346-afa964097b0a'
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
