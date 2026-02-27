import boto3
import json
import random
import urllib3
import base64
from datetime import datetime

# === Configuration ===
REGION = 'us-east-1'
OS_HOST = 'search-restaurant-domain-l3mm4srslyxrindmlnp2ggr4gy.aos.us-east-1.on.aws'
INDEX = 'restaurant_list'
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/898147176601/DiningRequestsQueue'
DYNAMO_TABLE_DATA = 'yelp-restaurants'
SENDER_EMAIL = 'Jamiemai0210@gmail.com'
# OpenSearch 
OS_USERNAME = 'jm11065'
OS_PASSWORD = '*******'

def lambda_handler(event, context):
    sqs = boto3.client('sqs')
    
    print(f"Connecting to Queue: {QUEUE_URL}")
    
    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20, 
        AttributeNames=['All']
    )
    
    print(f"Full SQS Response: {json.dumps(response, default=str)}")
    
    if 'Messages' not in response or not response['Messages']:
        print("SQS says: The queue is currently empty.")
        return {"statusCode": 200, "body": "No messages found"}
    
    message = response['Messages'][0]
    print(f"Success! Captured Message ID: {message['MessageId']}")
    
    try:
        body = json.loads(message['Body'])
        print(f"Received user request: {body}")
        
        cuisine = body.get('Cuisine', 'chinese')
        email = body.get('Email')
        
        if not email:
            print("No email address found in message.")
            return

        business_ids = get_ids_from_opensearch(cuisine)
        
        if not business_ids:
            print(f"No restaurants found for {cuisine}")
        else:
            restaurants = get_details_from_dynamo(business_ids)
            
            if restaurants:
                send_email(email, cuisine, restaurants)
                print(f"Email sent successfully to {email}")
            
        message = response['Messages'][0]
        receipt_handle = message['ReceiptHandle']
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        print("Message deleted from queue.")

    except Exception as e:
        print(f"Critical error: {str(e)}")
        
    return {"statusCode": 200, "body": "Process completed"}

        
def get_ids_from_opensearch(cuisine):
    auth_str = f"{OS_USERNAME}:{OS_PASSWORD}"
    encoded_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
    
    clean_host = OS_HOST.replace('https://', '').replace('http://', '')
    url = f"https://{clean_host}/{INDEX}/_search"
    
    query = {
        "size": 15,
        "query": {
            "match": {
                "Cuisine": cuisine.lower() 
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
        
        print(f"OpenSearch Status: {r.status}")
        if r.status != 200:
            print(f"OpenSearch Error Data: {r.data.decode('utf-8')}")
            return []

        res_json = json.loads(r.data.decode('utf-8'))
        hits = res_json.get('hits', {}).get('hits', [])
        
        all_ids = []
        for h in hits:
            bid = h.get('_source', {}).get('BusinessID')
            if bid:
                all_ids.append(bid)
        
        return random.sample(all_ids, min(len(all_ids), 3))
        
    except Exception as e:
        print(f"OpenSearch query error: {e}")
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
        except Exception as e:
            print(f"DynamoDB lookup error for ID {bid}: {e}")
            
    return results

def send_email(to_email, cuisine, restaurants):
    ses = boto3.client('ses', region_name=REGION)
    
    recommendations = ""
    for i, r in enumerate(restaurants, 1):
        name = r.get('Name', 'Unknown Restaurant')
        address = r.get('Address', 'No address provided')
        recommendations += f"{i}. {name}, at {address}\n"
    
    body_text = (
        f"Hello! Based on your preference for {cuisine}, "
        f"here are my recommendations:\n\n"
        f"{recommendations}\n"
        f"Enjoy your meal!"
    )

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {'Data': 'Your Restaurant Recommendations'},
            'Body': {'Text': {'Data': body_text}}
        }
    )