import json
import datetime
import boto3

# Configuration
ALLOWED_CITIES = ['new york']
ALLOWED_CUISINES = ['chinese', 'italian', 'japanese', 'mexican', 'indian', 'american']
DYNAMO_TABLE_USER = 'UserLastSelection'
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/898147176601/DiningRequestsQueue'

db = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

def validate_booking(event, slots):
    user_id = event.get('sessionId')
    print(f"Validating booking for user {user_id}")

    # 1. Validate Location
    if slots.get('Location') and slots['Location'].get('value'):
        user_city = slots['Location']['value']['interpretedValue'].lower()
        if user_city not in ALLOWED_CITIES:
            return {
                'isValid': False,
                'violatedSlot': 'Location',
                'message': f"Sorry, we only have restaurants in {', '.join(ALLOWED_CITIES).title()}. "
            }

    # 2. Validate Cuisine 
    if slots.get('Cuisine') and slots['Cuisine'].get('value'):
        user_cuisine = slots['Cuisine']['value']['interpretedValue'].lower()
        # if user_cuisine in ['yes', 'no', 'yeah']: return {'isValid': True}
        
        if user_cuisine not in ALLOWED_CUISINES:
            return {
                'isValid': False,
                'violatedSlot': 'Cuisine',
                'message': f"I don't have recommendations for {user_cuisine} yet. How about {', '.join(ALLOWED_CUISINES)}?"
            }

    # 3. Validate Date
    if slots.get('Date') and slots['Date'].get('value'):
        booking_date_str = slots['Date']['value']['interpretedValue']
        try:
            booking_date = datetime.datetime.strptime(booking_date_str, '%Y-%m-%d').date()
            if booking_date < datetime.date.today():
                return {'isValid': False, 'violatedSlot': 'Date', 'message': 'We cannot book for a past date.'}
        except ValueError:
            return {'isValid': False, 'violatedSlot': 'Date', 'message': 'Date format seems wrong.'}

   # 4. Validate Time 
    if slots.get('Time') and slots['Time'].get('value'):
        user_time = slots['Time']['value'].get('interpretedValue')
        
        if not user_time or ":" not in user_time:
            return {
                'isValid': False, 
                'violatedSlot': 'Time', 
                'message': 'Please provide a specific time, for example 18:30 or 6:30 PM.'
            }
            
        try:
            t_hour, t_min = map(int, user_time.split(':'))
            if not (0 <= t_hour < 24 and 0 <= t_min < 60):
                return {'isValid': False, 'violatedSlot': 'Time', 'message': 'Invalid time range. Please use 24-hour format.'}
        except ValueError:
            return {
                'isValid': False, 
                'violatedSlot': 'Time', 
                'message': 'Please provide a valid time (e.g., 18:30).'
            }

    # 5. Validate Guest Count
    if slots.get('GuestCount') and slots['GuestCount'].get('value'):
        count_val = slots['GuestCount']['value']['interpretedValue']
        try:
            count = int(count_val)
            if count <= 0 or count > 10:
                return {'isValid': False, 'violatedSlot': 'GuestCount', 'message': 'We can only accommodate 1 to 10 guests.'}
        except ValueError:
            return {'isValid': False, 'violatedSlot': 'GuestCount', 'message': 'Please provide the number as a digit.'}

    return {'isValid': True}

def lambda_handler(event, context):
    print("FULL EVENT FROM API GATEWAY:", json.dumps(event))
    intent_name = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent']['slots']
    source = event['invocationSource'] 
    user_id = event['sessionId']
    session_attrs = event['sessionState'].get('sessionAttributes') or {}
    
    print(f"Received event from {source} for intent {intent_name}")
    
    if source == 'DialogCodeHook':
        # slots_are_empty = True
        # for v in slots.values():
        #     if v is not None and v.get('value') is not None:
        #         slots_are_empty = False
        #         break

        # if slots_are_empty and session_attrs.get('asked_history') != 'true':
        if (not slots.get('Location') or not slots['Location'].get('value')) and session_attrs.get('asked_history') != 'true':
            try:
                table = db.Table(DYNAMO_TABLE_USER)
                res = table.get_item(Key={'userId': user_id})
                if 'Item' in res:
                    h_cuisine = res['Item']['cuisine']
                    h_location = res['Item']['location']
                    session_attrs['asked_history'] = 'true'
                    
                    return {
                        "sessionState": {
                            "sessionAttributes": session_attrs,
                            "dialogAction": {"type": "ConfirmIntent"},
                            "intent": {
                                "name": intent_name,
                                "slots": {
                                    "Location": {"value": {"interpretedValue": h_location, "originalValue": h_location}},
                                    "Cuisine": {"value": {"interpretedValue": h_cuisine, "originalValue": h_cuisine}}
                                }
                            }
                        },
                        "messages": [{"contentType": "PlainText", "content": f"Welcome back! Last time you searched for {h_cuisine} in {h_location}. Use these details again?"}]
                    }
            except Exception as e: 
                print(f"DB Error: {e}")
                
        if event['sessionState']['intent'].get('confirmationState') == 'Denied':
            session_attrs['asked_history'] = 'true'
            return {
                "sessionState": {
                    "sessionAttributes": session_attrs,
                    "dialogAction": {"type": "ElicitSlot", "slotToElicit": "Location"},
                    "intent": {"name": intent_name, "slots": {k: None for k in slots}}
                },
                "messages": [{"contentType": "PlainText", "content": "OK, let's start fresh. Where are you looking to dine?"}]
            }

        validation_result = validate_booking(event, slots)
        if not validation_result['isValid']:
            return {
                "sessionState": {
                    "sessionAttributes": session_attrs,
                    "dialogAction": {
                        "slotToElicit": validation_result['violatedSlot'],
                        "type": "ElicitSlot"
                    },
                    "intent": {"name": intent_name, "slots": slots}
                },
                "messages": [{"contentType": "PlainText", "content": validation_result['message']}]
            }

        return {
            "sessionState": {
                "sessionAttributes": session_attrs,
                "dialogAction": {"type": "Delegate"},
                "intent": {"name": intent_name, "slots": slots}
            }
        }

    if source == 'FulfillmentCodeHook':
        booking_data = {k: slots[k]['value']['interpretedValue'] for k in slots if slots[k] and slots[k].get('value')}
        booking_data['userId'] = user_id

        # --- Add user last search to DynamoDB ---
        try:
            db.Table(DYNAMO_TABLE_USER).put_item(
                Item={
                    'userId': user_id, 
                    'location': booking_data['Location'], 
                    'cuisine': booking_data['Cuisine']
                }
            )
        except Exception as e: print(f"DB Save Error: {e}")

        # 2. Push to SQS
        sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(booking_data))

        session_attrs['asked_history'] = 'false'

        return {
                    "sessionState": {
                        "sessionAttributes": session_attrs, 
                        "dialogAction": {"type": "Close"},
                        "intent": {
                            "name": intent_name, 
                            "slots": slots, 
                            "state": "Fulfilled"
                        }
                    },
                    "messages": [{"contentType": "PlainText", "content": "I've received your request. I'll search for the best options and email you shortly!"}]
                }