import os
import boto3
import json
import random
import urllib3
import base64
import traceback
from datetime import datetime

# Environment Variables
REGION = os.environ.get('REGION', 'us-east-1')
OS_HOST = os.environ['OS_HOST']
INDEX = os.environ.get('INDEX', 'restaurant_list')
QUEUE_URL = os.environ['QUEUE_URL']
DYNAMO_TABLE_DATA = os.environ.get('DYNAMO_TABLE_DATA', 'yelp-restaurants')
SENDER_EMAIL = os.environ['SENDER_EMAIL']
OS_USERNAME = os.environ['OS_USERNAME']
OS_PASSWORD = os.environ['OS_PASSWORD']

def lambda_handler(event, context):
    sqs = boto3.client('sqs')
    
    # 1. Receive message from SQS
    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20, 
        AttributeNames=['All']
    )
    
    if 'Messages' not in response or not response['Messages']:
        print("SQS: No messages available in the queue.")
        return {"statusCode": 200, "body": "No messages found"}
    
    message = response['Messages'][0]
    receipt_handle = message['ReceiptHandle']
    print(f"SQS: Received message ID: {message['MessageId']}")

    try:
        # 2. Parse Body - No defaults used to ensure strict data presence
        body = json.loads(message['Body'])
        print(f"DEBUG: Parsed Body: {body}")
        
        cuisine = body['Cuisine']
        email = body['Email']
        count = body['GuestCount']
        date = body['Date']
        time = body['Time']
        
        # 3. Step 1: Query OpenSearch for Business IDs
        business_ids = get_ids_from_opensearch(cuisine)
        print(f"DEBUG: OpenSearch IDs found: {business_ids}")
        
        if not business_ids:
            print(f"WARNING: No restaurants found for cuisine: {cuisine}. Deleting message.")
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
            return

        # 4. Step 2: Query DynamoDB for restaurant details
        restaurants = get_details_from_dynamo(business_ids)
        print(f"DEBUG: Retrieved {len(restaurants)} restaurant details from DynamoDB.")
        
        if not restaurants:
            print("WARNING: Could not find details in DynamoDB for the IDs found. Deleting message.")
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
            return

        # 5. Step 3: Send Email via SES
        send_email(email, cuisine, count, date, time, restaurants)
        print(f"SUCCESS: Email sent successfully to {email}")

        # 6. Final Step: Delete from SQS only if processing succeeded
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        print("SQS: Message deleted from queue.")

    except KeyError as e:
        print(f"ERROR: Missing required key in message body: {str(e)}")
        # Delete malformed messages to prevent infinite loops
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
    except Exception as e:
        print("ERROR: An unexpected error occurred. Message will remain in queue for retry.")
        print(traceback.format_exc())
        
    return {"statusCode": 200, "body": "Process completed"}

def get_ids_from_opensearch(cuisine):
    auth_str = f"{OS_USERNAME}:{OS_PASSWORD}"
    encoded_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
    
    clean_host = OS_HOST.replace('https://', '').replace('http://', '')
    url = f"https://{clean_host}/{INDEX}/_search"
    
    # Note: Ensure the 'Cuisine' case matches your OpenSearch index data
    query = {
        "size": 15,
        "query": {
            "match": {
                "Cuisine": cuisine.strip()
            }
        }
    }
    
    http = urllib3.PoolManager()
    encoded_data = json.dumps(query).encode('utf-8')
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {encoded_auth}'
        }
        r = http.request('POST', url, body=encoded_data, headers=headers)
        
        if r.status != 200:
            print(f"ERROR: OpenSearch status {r.status}. Data: {r.data.decode()}")
            return []

        res_json = json.loads(r.data.decode('utf-8'))
        hits = res_json.get('hits', {}).get('hits', [])
        
        all_ids = [h.get('_source', {}).get('BusinessID') for h in hits if h.get('_source', {}).get('BusinessID')]
        
        if not all_ids:
            return []
            
        return random.sample(all_ids, min(len(all_ids), 3))
        
    except Exception as e:
        print(f"ERROR: OpenSearch connection error: {str(e)}")
        return []

def get_details_from_dynamo(ids):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(DYNAMO_TABLE_DATA)
    results = []
    
    for bid in ids:
        try:
            response = table.get_item(Key={'BusinessID': bid})
            item = response.get('Item')
            if item:
                results.append(item)
            else:
                print(f"WARNING: BusinessID {bid} not found in DynamoDB.")
        except Exception as e:
            print(f"ERROR: DynamoDB GetItem failed for {bid}: {str(e)}")
            continue
    return results

def send_email(to_email, cuisine, count, date, time, restaurants):
    ses = boto3.client('ses', region_name=REGION)
    
    recommendations = ""
    for i, r in enumerate(restaurants, 1):
        name = r.get('Name', 'Unknown Restaurant')
        address = r.get('Address', 'No address provided')
        recommendations += f"{i}. {name}, located at {address}\n"
    
    body_text = (
        f"Hello! Here are my {cuisine} restaurant suggestions for {count} people, "
        f"for {date} at {time}:\n\n"
        f"{recommendations}\n"
        f"Enjoy your meal!"
    )

    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': 'Your Restaurant Recommendations'},
                'Body': {'Text': {'Data': body_text}}
            }
        )
    except Exception as e:
        print(f"ERROR: SES failed to send email to {to_email}: {str(e)}")
        raise e # Raise to prevent SQS deletion so it can retry