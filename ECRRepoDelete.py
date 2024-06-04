import boto3
import cfnresponse

response_data = {}

def lambda_handler(event, context):
    print(event)
    try:
        if event['RequestType'] == 'Delete':
            ecr_client = boto3.client('ecr')
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data)
            return    
        repo_name = event['ResourceProperties']['repositoryName']
        account_id = event['ServiceToken'].split(":").pop(4)
        print(repo_name)
        print(account_id)
        list_images_response = ecr_client.list_images(registryId=account_id, repositoryName=repo_name)
        image_ids = list_images_response['imageIds']
        if len(image_ids) > 0:
            batch_delete_image_response = ecr_client.batch_delete_image(registryId=account_id,repositoryName=repo_name,imageIds=image_ids)
            print(batch_delete_image_response)
            print(f"{repo_name} repository images are Deleted")
        else:
            print(f'This is a empty repo : {repo_name}')
        
        cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data)
        return {
            'statusCode': 200,
            'body': 'ECR repositories deleted successfully'
        }

    except Exception as e:
        print(e)
        cfnresponse.send(event, context, cfnresponse.FAILED, response_data)
