var https = require('https');
var util = require('util');
var AWS = require("aws-sdk");
exports.handler = async (event) => {
    // var verification_url = "https://devapi.whitewellapp.com:9443/healty"
    // var operation = "deployment"
    
    console.log(event);
    console.log(event['Records']['0']['Sns']);
    const defaultResponse = {
        statusCode: 200,
        body: JSON.stringify("No response available in SNS messages."),
    };

    // Build data based on status message
    var status_to_notify = ["created", "failed", "ready", "succeeded", "aborted"];
    var details = '';
    if (typeof event.Records[0].Sns.Message != 'object') {
         details = JSON.parse(event.Records[0].Sns.Message);
    } else {
        details = event.Records[0].Sns.Message.detail;
    }
    console.log(typeof details)

    if (typeof details.applicationName === 'undefined') {
        console.log("No response avalable");
        return defaultResponse;
    }

    var operation = 'Deployment';
    if (typeof details.rollbackInformation !== 'undefined') {
        operation = 'Rollback';
    }

    // Build Branch name based on deployment application
    var branchName = 'AWS';
    var verification_url = process.env.VERIFICATION_DOMAIN_URL;
    if (details.applicationName == 'AppECS-whitewell-production') {
        branchName = 'production';
        verification_url = process.env.VERIFICATION_DOMAIN_URL;
    }
    else if (details.applicationName == 'AppECS-whitewell-staging') {
        branchName = 'staging';
        verification_url = process.env.VERIFICATION_STAGING_WEB_DOMAIN_URL;
    }
    else if (details.applicationName == 'AppECS-whitewell-development') {
        branchName = 'development';
        verification_url = process.env.VERIFICATION_DEVELOPMENT_WEB_DOMAIN_URL;
    }
    else {
        console.log('Not a valid env');
        return defaultResponse;
    }

    // Build message based on the application status
    var status = details.status.toLowerCase();
    var message = 'Code ' + operation + ' ' + status + '.';
    var verifyStatus = status_to_notify.indexOf(status);
    var approval_link = '';
    if (verifyStatus !== -1) {
        if (status == 'aborted') {
            message = 'Code ' + operation + " aborted. \n Reason: " + JSON.stringify(details['errorInformation']);
        }
        if (status == 'failed') {
            message = 'Code ' + operation + " failed. \n Reason: " + JSON.stringify(details);
        }
        if (status == 'ready') {
            message = 'Code ' + operation + ' ready to switch traffic. <br> Please <a href="' + verification_url + '"> click here </a> to check  test-route and approve or deny using below buttons';
            message += '<br><a href="' + process.env.APPROVAL_URL + details['deploymentId'] + '">Approve</a>   <a href="' + process.env.APPROVAL_URL + details['deploymentId'] + '">Deny</a>';
        }
        if (status == 'succeeded') {
            message = 'Code ' + operation + ' successful.';
        }
    }
    else {
        console.log("Skipping sending notification for status: " + status);
        return defaultResponse;
    }

    console.log(branchName);
    console.log(message);

    return new Promise((resolve, reject) => {
        var postData = {
            "channel": process.env.TEAMS_CHANNEL,
            "text": "<b>CodePipeline: </b>(" + branchName + ")<br>" + message 

        };

        
        var options = {
            method: 'POST',
            header: {
              'Content-Type': 'application/json'
            },
            hostname: process.env.TEAMS_HOSTNAME,
            port: 443,
            path: process.env.TEAMS_WEBHOOK_PATH
        };

        const req = https.request(options, (res) => {
          resolve('Success');
        });

        req.on('error', (e) => {
          console.log('problem with request: ' + e.message);
          reject(e.message);
        });

        req.write(JSON.stringify(postData));
        req.end();
    });

    function ucwords (str) {
        return (str + '').replace(/^([a-z])|\s+([a-z])/g, function ($1) {
            return $1.toUpperCase();
        });
    }
};

