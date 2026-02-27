import boto3
import uuid
import json

lex_client = boto3.client('lexv2-runtime', region_name='us-east-1')

def lambda_handler(event, context):
    # 1. Parse Input
    try:
        if 'body' in event and isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event
            
        if 'messages' in body:
            user_input = body['messages'][0]['unstructured']['text']
            user_id = body['messages'][0]['unstructured'].get('userId', 'default-user')
        else:
            user_input = body.get('message')
            user_id = 'default-user'
    except Exception as e:
        user_input = None

    if not user_input:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Message missing'}) # Stringify this!
        }

    # 2. Call Lex
    try:
        response = lex_client.recognize_text(
            botId='RCXMTJ5CLQ',
            botAliasId='TSTALIASID',
            localeId='en_US',
            # sessionId="default-user",
            sessionId=user_id,
            text=user_input
        )

        bot_messages = response.get('messages', [])
        final_text = bot_messages[0]['content'] if bot_messages else "No response"

        result_payload = {
            'messages': [
                {
                    'type': 'unstructured',
                    'unstructured': {
                        'text': final_text # Lex response text
                    }
                }
            ],
            'intent': response['sessionState']['intent']['name']
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # Added for CORS if needed
            },
            'body': json.dumps(result_payload)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}) # Stringify this too!
        }