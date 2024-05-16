from boto3.session import Session
from zipfile import ZipFile
from teams_notification import post_to_teams

import os
import json
import boto3
import zipfile
import tempfile
import botocore
import traceback
import time


codepipeline_client = boto3.client('codepipeline')

codedeploy = boto3.client('codedeploy')
ecs_client = boto3.client('ecs')
s3 = boto3.client('s3')
blue_green_deployment = ['production', 'staging', 'development']
auto_traffic_switch = ['development']

# Main handler of the script
def lambda_handler(event, context):
    print(event)
    try:
        if 'CodePipeline.job' in event:
            # Extract the Job ID
            job_id = event['CodePipeline.job']['id']

            # Extract the Job Data
            job_data = event['CodePipeline.job']['data']

            environmentName = job_data['actionConfiguration']['configuration']['UserParameters']
            print(f"Environment Name = {environmentName}")

            if not environmentName:
                raise Exception('Environment name is missing.')

            if environmentName not in blue_green_deployment:
                raise Exception('Given pipeline env is not a valid one - ' +environmentName)

            post_to_teams('Common pipeline started..', environmentName)
            post_to_teams('Checking for any Inprogress deployments..', environmentName)

            # Check whether is already any stage is in progress
            deploymentData = check_pipeline_is_already_inprogress(job_id, environmentName)
            print(deploymentData)
            
            # Bypass the exception for auto traffic switch process
            if deploymentData['status'] == False and environmentName in auto_traffic_switch:
                retryCount = 0
                while retryCount < 5:
                    post_to_teams('Checking the pipeline progress again...', environmentName)
                    time.sleep(60)
                    deploymentData = check_pipeline_is_already_inprogress(job_id, environmentName)
                    print(deploymentData)
                    if deploymentData['status'] == True:
                        post_to_teams('Deployment got completed. Making way for next deployment..', environmentName)
                        break
                    retryCount += 1
                    
            # Stop the running deployment and build new deployment details
            if deploymentData['status'] == True and 'deploymentId' in deploymentData:
                post_to_teams('Found a deployment which is waiting for shift traffic.', environmentName)
                post_to_teams('Stopping the deployment #' + deploymentData['deploymentId'] + ' and building a new combined deployment', environmentName)
                stop_deployment(deploymentData['deploymentId'])
            else:
                post_to_teams('No InProgress deployments found.', environmentName)            

            # Get the artifact details
            artifact_data = get_artifact(job_data, 'SourceArtifact')
            
            # Build deploy artifcat
            builddeployArtifact(artifact_data, environmentName, deploymentData)
            
            # Upload the json artifcats to S3
            upload_artifacts_to_s3(job_data, 'DeploymentArtifact', environmentName)

            put_job_success(job_id, 'Build artifacts successfully generated.')

        else:
            raise Exception('Not a valid invocation.')
    except Exception as e:
        # If any other exceptions which we didn't expect are raised
        # then fail the job and log the exception message.
        print('Function failed due to exception.')
        print(e)
        traceback.print_exc()
        if 'CodePipeline.job' in event:
            post_to_teams('Combined pipeline failed - ' + str(e), environmentName)
            put_job_failure(job_id, 'Function exception: ' + str(e))

    print('Function complete.')
    return "Complete."


# Checks pipeline is already inprogress
# and fails the job if another deployment is inprogress
def check_pipeline_is_already_inprogress(job_id, environmentName):

    job_details = codepipeline_client.get_job_details(
        jobId=job_id
    )

    # Check recent pipeline executions is InProgress
    # IF yes, put the job failure
    if 'jobDetails' in job_details:
        pipeline_details = job_details['jobDetails']['data']['pipelineContext']
        pipelineName = pipeline_details['pipelineName']
        pipelineExecutionId = pipeline_details['pipelineExecutionId']
        executions = codepipeline_client.list_pipeline_executions(
            pipelineName=pipelineName,
            maxResults=5,
        )

        if 'pipelineExecutionSummaries' in executions:
            for execution in executions['pipelineExecutionSummaries']:
                if pipelineExecutionId != execution['pipelineExecutionId']:
                    if execution['status'] == 'InProgress':                        
                        deployStatus = get_deployment_status(pipelineName, execution['pipelineExecutionId'], environmentName)
                        print(deployStatus)
                        if deployStatus['status'] == False:
                            post_to_teams('Another deployment which just started/crossed traffic-switch is already in progress.', environmentName)
                            if environmentName not in auto_traffic_switch:
                                raise Exception('Another deployment which just started/crossed traffic-switch is already in progress.')
                            else:
                                return deployStatus
                        else:
                            return deployStatus
                        

    # If it is a first time deployment, returning default status
    return {"status": True}

# Download artifcat from S3
def download_artifact_from_S3(artifactDetails):
    tmp_file = tempfile.NamedTemporaryFile()
    bucket = artifactDetails['bucket']
    key = artifactDetails['key']

    with tempfile.NamedTemporaryFile() as tmp_file:
        s3.download_file(bucket, key, tmp_file.name)
        with zipfile.ZipFile(tmp_file.name, 'r') as zip:
            return zip.read('taskdef.json')

# Get current deployment status
def get_deployment_status(pipelineName, pipelineExecutionId, environmentName):
    deployStatus = {"status": False }

    if environmentName == 'production':
        appName = os.environ['PROD_APPLICATION_NAME']
        deploymentGroup = os.environ['PROD_DEPLOYMENT_GROUP']
    elif environmentName == 'staging':
        appName = os.environ['STAGING_APPLICATION_NAME']
        deploymentGroup = os.environ['STAGING_DEPLOYMENT_GROUP']
    elif environmentName == 'development':
        appName = os.environ['DEV_APPLICATION_NAME']
        deploymentGroup = os.environ['DEV_DEPLOYMENT_GROUP']
    else:
        raise Exception('Not a valid Environment Name')


    print(appName)
    print(deploymentGroup)
    print(pipelineName)
    print(pipelineExecutionId)
    print(environmentName)

    actionExecutions = codepipeline_client.list_action_executions(
        pipelineName=pipelineName,
        filter={
            'pipelineExecutionId': pipelineExecutionId
        }
    )
    print(actionExecutions)
    if 'actionExecutionDetails' in actionExecutions:
        for execution in actionExecutions['actionExecutionDetails']:
            if execution['actionName'] == 'Deploy':
                post_to_teams('Found an already running deployment...', environmentName)
                post_to_teams('Fetching the deployment details...', environmentName)
                inputArtifact = execution['input']['inputArtifacts']
                deploymentArtifact = {
                    "bucket": inputArtifact[0]['s3location']['bucket'],
                    "key": inputArtifact[0]['s3location']['key'],
                }

                listDeployments = wait_for_deploy_to_run_tasks(appName, deploymentGroup, environmentName)
                print(listDeployments)

                if 'deployments' in listDeployments:
                    if len(listDeployments['deployments']) > 0:
                        deploymentId = listDeployments['deployments'][0]
                        artifactJson = download_artifact_from_S3(deploymentArtifact)
                        deployStatus = {'status': True, 'deploymentId': deploymentId, 'imageDetails': json.loads(artifactJson)}
                        return deployStatus
    return deployStatus


# Waiting for the tasks to get deployed for Blue environment
def wait_for_deploy_to_run_tasks(appName, deploymentGroup, environmentName):
    retryTime = 0
    listDeployments = {}
    
    while retryTime < 3:
        post_to_teams("Waiting for the CodeDeploy to get the replacement ECS tasks to running state..", environmentName)
        listDeployments = codedeploy.list_deployments(
            applicationName=appName,
            deploymentGroupName=deploymentGroup,
            includeOnlyStatuses=[
                'Ready',
            ],
        )
        
        if 'deployments' in listDeployments:
            if len(listDeployments['deployments']) > 0:
                break;
        time.sleep(60)
        retryTime += 1
    return listDeployments
    

# Stop the current deployment
def stop_deployment(deploymentId):
    deploymentStatus = 'Pending'
    codedeploy.stop_deployment(
        deploymentId=deploymentId,
        autoRollbackEnabled=True
    )

    while deploymentStatus != 'Stopped':
        getDeploymentDetails = codedeploy.get_deployment(
            deploymentId=deploymentId
        )
        if 'deploymentInfo' in getDeploymentDetails:
            deploymentStatus = getDeploymentDetails['deploymentInfo']['status']
            time.sleep(5)
        print(deploymentStatus)
    return deploymentStatus


def get_artifact(job_data, name):
    """Finds the artifact 'name' among the 'artifacts'

    Args:
        artifacts: The list of artifacts available to the function
        name: The artifact we wish to use
    Returns:
        The artifact dictionary found
    Raises:
        Exception: If no matching artifact is found

    """
    s3_session_client = setup_artifact_s3_client(job_data)
    for artifact in job_data['inputArtifacts']:
        if artifact['name'] == name:
            tmp_file = tempfile.NamedTemporaryFile()
            bucket = artifact['location']['s3Location']['bucketName']
            key = artifact['location']['s3Location']['objectKey']
            with tempfile.NamedTemporaryFile() as tmp_file:
                s3_session_client.download_file(bucket, key, tmp_file.name)
                with open(tmp_file.name) as f:
                    data = json.load(f)
                    print(data)
                    return data
    raise Exception('Input artifact named "{0}" not found in event'.format(name))


# Builds the deployArtifcat
def builddeployArtifact(source_artifact, environmentName, deploymentData):
    imagedefinition = source_artifact
    imageDetails = imagedefinition[0]
    containerNames = {'whitewell-api': '', 'whitewell-admin-portal': ''}
    if "name" not in imageDetails or "imageUri" not in imageDetails:
        raise Exception('Not a valid image.')
        
    containerNames[imageDetails['name']] = imageDetails['imageUri']
    print(containerNames)
    
    if deploymentData['status'] and 'imageDetails' in deploymentData:
        finalImages = get_previous_deploy_image(deploymentData['imageDetails'], containerNames)
    else:
        finalImages = get_running_prod_image(containerNames, environmentName)    
    
    for container in containerNames:
        if bool(finalImages[container]) == False:
            raise Exception('Unable to fetch the right images for the container - .' + container)
    
    print(finalImages)
    #replace the image and task definition in taskdef and appspec json
    replace_placeholder_and_create_artifacts(finalImages, environmentName)


# Return image from the deployment data
def get_previous_deploy_image(deploymentData, containerNames):
    if deploymentData:
        for container in deploymentData['containerDefinitions']:
            if container['name'] in containerNames and containerNames[container['name']] == '':
                containerNames[container['name']] = container['image']

    return containerNames


def upload_artifacts_to_s3(job_data, name, environmentName):
    """Uploads the deployment artifact to S3'

    Args:
        job_data: Codepipeline job data
        name: The artifact we wish to use
    Returns:
        Void. Uploads the artifcat to S3
    Raises:
        Exception: If no matching artifact is found
    """
    s3_session_client = setup_artifact_s3_client(job_data)
    for artifact in job_data['outputArtifacts']:
        if artifact['name'] == name:
            bucket = artifact['location']['s3Location']['bucketName']
            key = artifact['location']['s3Location']['objectKey']
            file_name = '/tmp/artifact.zip'
            with ZipFile(file_name, 'w') as zipObj:                
                # Add multiple files to the zip
                zipObj.write('/tmp/taskdef.json', 'taskdef.json')
                zipObj.write('/tmp/appspec.json', 'appspec.json')                
            response = s3_session_client.upload_file(file_name, bucket, key, ExtraArgs={'ServerSideEncryption':'aws:kms', 'SSEKMSKeyId':'alias/aws/s3'})

def setup_artifact_s3_client(job_data):
    """Creates an S3 client

    Uses the credentials passed in the event by CodePipeline. These
    credentials can be used to access the artifact bucket.

    Args:
        job_data: The job data structure

    Returns:
        An S3 client with the appropriate credentials

    """
    key_id = job_data['artifactCredentials']['accessKeyId']
    key_secret = job_data['artifactCredentials']['secretAccessKey']
    session_token = job_data['artifactCredentials']['sessionToken']

    session = Session(aws_access_key_id=key_id,
        aws_secret_access_key=key_secret,
        aws_session_token=session_token)
    return session.client('s3', config=botocore.client.Config(signature_version='s3v4'))


# Describe the services based on the cluster and service name
def describe_services_from_cluster(cluster_name, service_name):
    describe_service = ''
    if cluster_name and service_name:
        describe_service = ecs_client.describe_services(
            cluster=cluster_name,
            services=[service_name],
        )
    return describe_service


# Replace the placeholders in json files
def replace_placeholder_and_create_artifacts(containerImages, environmentName):
    post_to_teams('Version to be deployed', environmentName)
    post_to_teams('API image - ' + containerImages['whitewell-api'], environmentName)
    post_to_teams('Admin Portal image - ' + containerImages['whitewell-admin-portal'] , environmentName)

    with open('ecs-taskdef-template.json') as taskdef_template:
        taskdef = json.load(taskdef_template)
        taskdef['family'] = "whitewell-{}".format(environmentName)
        for container in taskdef['containerDefinitions']:
            container['logConfiguration']['options']['awslogs-group'] = "/ecs/whitewell-{}".format(environmentName)
            if container['name'] in containerImages:
                container['image'] = containerImages[container['name']]

    # Create taskdef and appspec file and upload to Deployartifact
    with open('/tmp/taskdef.json', 'w') as file:
        json.dump(taskdef, file, indent=2)
    with open('ecs-appspec-template.json') as appspec_template:
        appspec = json.load(appspec_template)
        with open('/tmp/appspec.json', 'w') as file:
            json.dump(appspec, file, indent=2)


# Returns running production image based on environment
def get_running_prod_image(containerNames, environmentName):
    prod_image = ''
    cluster_name = os.environ['DEV_WEB_CLUSTER']
    # if environmentName in rolling_update_deployment:
    #     cluster_name = os.environ['DEV_WEB_CLUSTER']
    prod_service = describe_services_from_cluster(cluster_name, environmentName)
    valid_containers = ['whitewell-api', 'whitewell-admin-portal']

    #if container_name not in valid_containers:
        #raise Exception('Not a valid container')

    if 'services' in prod_service:
        taskDefinition = prod_service['services'][0]['taskDefinition']
        prod_taskdef = ecs_client.describe_task_definition(
            taskDefinition=taskDefinition
        )

        if 'taskDefinition' in prod_taskdef:
            containerDefinitions = prod_taskdef['taskDefinition']['containerDefinitions']
            for container in containerDefinitions:
                if container['name'] in containerNames and containerNames[container['name']] == '':
                    containerNames[container['name']] = container['image']

    return containerNames

def put_job_success(job, message):
    """Notify CodePipeline of a successful job

    Args:
        job: The CodePipeline job ID
        message: A message to be logged relating to the job status

    Raises:
        Exception: Any exception thrown by .put_job_success_result()

    """
    print('Putting job success')
    print(message)
    codepipeline_client.put_job_success_result(jobId=job)

def put_job_failure(job, message):
    """Notify CodePipeline of a failed job

    Args:
        job: The CodePipeline job ID
        message: A message to be logged relating to the job status

    Raises:
        Exception: Any exception thrown by .put_job_failure_result()

    """
    print('Putting job failure')
    print(message)
    codepipeline_client.put_job_failure_result(jobId=job, failureDetails={'message': message, 'type': 'JobFailed'})

