import boto3
import json
import re

s3_client = boto3.client('s3')
dynamodb_client = boto3.client('dynamodb')
kms_client = boto3.client('kms')
sqs_client = boto3.client("sqs")
lambda_client = boto3.client("lambda")
events_client = boto3.client('events')
cfn_client = boto3.client('cloudformation')
cw_client = boto3.client('logs')

MAX_ITEMS = 1000

def list_s3_buckets():
    bucket_list=[]
    response = s3_client.list_buckets()
    for bucket in response["Buckets"]:
        if "do-not-delete" in bucket["Name"]:
            continue
        else:
            bucket_list.append(bucket["Name"])
    return bucket_list

def list_ddb_tables():
    table_list = []
    response = dynamodb_client.list_tables()
    table_list = response["TableNames"]
    return table_list

def list_kms_keys(max_items):
    key_id_list=[]
    try:
        # creating paginator object for list_keys() method
        paginator = kms_client.get_paginator('list_keys')

        # creating a PageIterator from the paginator
        response_iterator = paginator.paginate(
            PaginationConfig={'MaxItems': max_items})

        full_result = response_iterator.build_full_result()
        for page in full_result['Keys']:
            key_id_list.append(page["KeyId"])

        # Check for AWS Managed Keys
        paginator = kms_client.get_paginator('list_aliases')

        # creating a PageIterator from the paginator
        response_iterator = paginator.paginate(
            PaginationConfig={'MaxItems': max_items})

        full_result = response_iterator.build_full_result()
        for page in full_result['Aliases']:
            if "alias/aws" in page["AliasName"]:
                if "TargetKeyId" in page:
                    key_id_list.remove(page["TargetKeyId"])

    except ClientError:
        logger.exception('Could not list KMS Keys.')
        raise
    else:
        return key_id_list   

def list_sqs_queues():
    queue_list=[]
    response = sqs_client.list_queues(
        QueueNamePrefix="wfm-"
    )
    if ("QueueUrls" in response):
        queue_urls = response["QueueUrls"]
        for queue in queue_urls:
            queue_list.append(queue)
    return queue_list

def list_lambda_layers():
    layer_list=[]
    response = lambda_client.list_layers()
    for layer in response["Layers"]:
        layer_list.append(
            {
                "layerName":layer["LayerName"], 
                "version":layer["LatestMatchingVersion"]["Version"]
            }
        )
    return layer_list

def list_rules():
    rule_list=[]
    response = events_client.list_rules(
        NamePrefix='wfm-'
    )
    for rule in response["Rules"]:
        rule_list.append(rule["Name"])
    return rule_list

def list_cfn_template():
    stack_list=[]
    response = cfn_client.list_stacks(
        StackStatusFilter=['CREATE_COMPLETE','ROLLBACK_COMPLETE','UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
    )
    for stack in response["StackSummaries"]:
        if re.match("orion-[a-zA-Z0-9]*-instance-[a-zA-Z0-9_.-]*", stack["StackName"]):
            stack_list.append(stack["StackName"])
        else:
            continue
    return stack_list

def list_cw_logs():
    cw_log_list=[]
    try:
        # creating paginator object for describe_log_groups() method
        paginator = cw_client.get_paginator('describe_log_groups')

        # creating a PageIterator from the paginator
        response_iterator = paginator.paginate(
            PaginationConfig={'MaxItems': MAX_ITEMS})

        full_result = response_iterator.build_full_result()
        for page in full_result['logGroups']:
            cw_log_list.append(page["logGroupName"])

    except ClientError:
        logger.exception('Could not list CloudWatch Logs.')
        raise
    else:
        return cw_log_list  


if __name__ == "__main__":
    try:  
        print("Collecting Resources to Delete")
        resources={}
        bucket_list = list_s3_buckets()
        resources["s3"]=bucket_list

        ddb_table_list = list_ddb_tables()
        resources["ddb"]=ddb_table_list

        kms_key_list = list_kms_keys(MAX_ITEMS)
        resources["kms"]=kms_key_list

        sqs_list = list_sqs_queues()
        resources["sqs"]=sqs_list

        lambda_layer_list=list_lambda_layers()
        resources["lambdaLayer"]=lambda_layer_list

        rules_list = list_rules()
        resources["eventbridge"]=rules_list

        cfn_template_list = list_cfn_template()
        resources["cloudformation"]=cfn_template_list

        cw_logs_list = list_cw_logs()
        resources["cwlogs"]=cw_logs_list

        print("Writing Items to Delete to JSON File: delete_file.json")
        with open("delete_file.json", "w+") as delete_file:
            json.dump(resources,delete_file)
        
    except Exception as e:
        print(f"Error: {e}")