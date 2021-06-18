import json
from urllib.parse import urlencode
import urllib3
import boto3
from botocore.exceptions import ClientError


endpoints = [
    {
        "name": "ALCF Theta",
        "uuid": "08925f04-569f-11e7-bef8-22000b9a448b"
    },
    {
        "name": "aps#clutch",
        "uuid": "b0e921df-6d04-11e5-ba46-22000b92c6ec"
    },
    {
        "name": "aps#data",
        "uuid": "9c9cb97e-de86-11e6-9d15-22000a1e3b52"
    },
    {
        "name": "NERSC Cori",
        "uuid": "9d6d99eb-6d04-11e5-ba46-22000b92c6ec"
    },
    {
        "name": "NERSC DTN",
        "uuid": "9d6d994a-6d04-11e5-ba46-22000b92c6ec"
    },
    {
        "name": "NERSC HPSS",
        "uuid": "9cd89cfd-6d04-11e5-ba46-22000b92c6ec"
    },
    {
        "name": "OLCF DTN",
        "uuid": "ef1a9560-7ca1-11e5-992c-22000b96db58"
    },
]


# General Client Id registered by lukasz@globusid.org
client_id = "6c1629cf-446c-49e7-af95-323c6412397f"
# speedpage Globus user refresh tokne for 'urn:globus:auth:scope:transfer.api.globus.org:all' scope
refresh_token = ""
endpoint_url = "https://transfer.api.globus.org/v0.10/endpoint/"


def log(error, suffix=""):
    bucket = "servicesmonitor"
    key = "endpoint_activation_error_timestamp" + suffix
    s3_client = boto3.client("s3")
    try:
        obj = s3_client.get_object(Bucket=bucket,
                                   Key=key)
        if not error:
            s3_client.delete_object(Bucket=bucket,
                                    Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey" and error:
            try:
                s3_client.put_object(Bucket=bucket,
                                 Key=key)
            except:
                # if for an undefined reason could not put the object
                pass
            return True
    except:
        # If for an undefined reason could not get or delete the object
        return True
    return False


def send_message(message):
    sns_client = boto3.client("sns")
    sns_client.publish(TopicArn="arn:aws:sns:us-east-1:648233944672:myChannel",
                       Subject="Dashboard endpoint activation error",
                       Message=message)


def lambda_handler(event, context):
    http = urllib3.PoolManager()
    # get an access token
    access_token = None
    headers = {
        "content-type": "application/x-www-form-urlencoded"
    }
    data = {
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "client_id": client_id
    }
    body = urlencode(data)
    try:
        response = http.request("POST", "https://auth.globus.org/v2/oauth2/token",
                                headers=headers, body=body, timeout=5)
        if response.status != 200:
            message = f"Error when renewing an access token. Status: {response.status}"
            if log(True):
                send_message(message)
            return {
                'statusCode': 200,
                'body': json.dumps(message)
            }
        data = json.loads(response.data.decode("utf-8"))
        access_token = data.get("access_token")
    except Exception as e:
        # send an sms notification if the service is down
        message = "Globus Auth token refresh error: ".format(e)
        if log(True):
            send_message(message)
        return {
            'statusCode': 200,
            'body': json.dumps(message)
        }

    # check endpoint status
    summary = ""
    headers = {
        "Authorization": "Bearer " + access_token
    }
    for endpoint in endpoints:
        name = endpoint.get("name")
        uuid = endpoint.get("uuid")
        try:
            response = http.request("GET", endpoint_url + uuid, headers=headers, timeout=10)
            data = json.loads(response.data.decode("utf-8"))
            expires_in = int(data.get("expires_in") / 3600)
            if expires_in < 24:
                message = f"{name} activation expires in {expires_in} hours"
                summary += message + "\n"
                if log(True, "-" + uuid):
                    send_message(message)
            elif log(False, uuid):
                send_message("Dashboard Endpoint Activation test problem with S3 Bucket")
        except Exception as e:
            # send an sms notification if the service is down
            message = f"Globus Transfer API error: {e}"
            if log(True):
                send_message(message)
            return {
                'statusCode': 200,
                'body': json.dumps(message)
            }

    if log(False):
        send_message("Dashboard Endpoint Activation test problem with S3 Bucket")
    if not summary:
        summary = "All endpoints active for at least 24 hours"
    return {
        'statusCode': 200,
        'body': json.dumps(summary)
    }
