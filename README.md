# cloud-computing-chatbot-concierge

## Architecture Overview
The system is built using a decoupled, asynchronous architecture on AWS:

Frontend: A simple chat interface hosted on Amazon S3 (Static Website Hosting).

API Layer: Amazon API Gateway acts as the entry point, triggering a Lambda function to communicate with the chatbot.

Bot Logic: Amazon Lex handles Natural Language Understanding (NLU) and slot filling.

Messaging Queue: Amazon SQS decouples the Lex fulfillment from the recommendation engine to handle asynchronous processing.

Recommendation Engine: A second Lambda function (LF2) is triggered periodically by Amazon EventBridge. It:

Pulls user requests from SQS.

Queries Amazon OpenSearch to find restaurant IDs matching the cuisine.

Fetches detailed restaurant metadata from Amazon DynamoDB.

Sends the final recommendation via Amazon SES.

Data Ingestion: A dedicated script (other-scripts/) was used to scrape data from Yelp and populate DynamoDB and OpenSearch.